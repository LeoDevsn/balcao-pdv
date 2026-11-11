// DOM simulado + servidor HTTP real. Não controla navegador nem valida aparência.
import test from 'node:test';
import assert from 'node:assert/strict';
import {JSDOM,VirtualConsole} from 'jsdom';
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer} from 'node:net';
import {setTimeout as pause} from 'node:timers/promises';

async function waitFor(condition,label){for(let i=0;i<200;i++){if(condition())return;await pause(25);}throw new Error('Não concluiu: '+label);}

test('Venda por código e peso, erro recuperável, troco, estoque e fechamento',async t=>{
  const directory=await mkdtemp(join(tmpdir(),'balcao-ui-test-'));
  const probe=createServer();await new Promise(resolve=>probe.listen(0,'127.0.0.1',resolve));const port=probe.address().port;await new Promise(resolve=>probe.close(resolve));
  const child=spawn('python',['-X','utf8','-m','balcao','--server','--data-dir',directory,'--port',String(port)],{cwd:new URL('../',import.meta.url),stdio:['ignore','pipe','pipe'],windowsHide:true});
  let logs='';child.stdout.on('data',v=>logs+=v);child.stderr.on('data',v=>logs+=v);
  let dom;const base=`http://127.0.0.1:${port}`;
  t.after(async()=>{dom?.window.close();if(child.exitCode===null){child.kill();await new Promise(resolve=>child.once('exit',resolve));}await rm(directory,{recursive:true,force:true});});
  await waitFor(()=>logs.includes('Balcão disponível'),'servidor pronto');
  const errors=[],console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e.message));
  dom=new JSDOM(await readFile(new URL('../balcao/frontend/index.html',import.meta.url),'utf8'),{url:base,runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:console});
  const w=dom.window,doc=w.document;w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  let dropSaleResponse=false;
  w.fetch=async(path,options={})=>{const url=new URL(path,base).href,headers=new Headers(options.headers),cookie=await dom.cookieJar.getCookieString(url);if(cookie)headers.set('Cookie',cookie);const response=await fetch(url,{...options,headers});if(path==='/api/data')await pause(60);for(const value of response.headers.getSetCookie())await dom.cookieJar.setCookie(value,url);if(dropSaleResponse&&path==='/api/sales'&&response.ok){dropSaleResponse=false;throw new Error('Resposta perdida no teste');}return response;};
  w.eval(await readFile(new URL('../balcao/frontend/app.js',import.meta.url),'utf8'));
  const fill=(selector,value)=>{const el=doc.querySelector(selector);assert.ok(el,selector);el.value=value;el.dispatchEvent(new w.Event('input',{bubbles:true}));};
  const submit=selector=>doc.querySelector(selector).dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  const click=selector=>{assert.ok(doc.querySelector(selector),selector);doc.querySelector(selector).click();};
  const go=async(hash,selector)=>{w.location.hash=hash;await waitFor(()=>doc.querySelector(selector),hash);};
  await waitFor(()=>doc.querySelector('[data-form=setup]'),'primeiro acesso');
  fill('#f-name','Mercado de teste');fill('#f-password','senha-temporaria-123');submit('[data-form=setup]');
  await waitFor(()=>doc.querySelector('#f-search'),'venda vazia');
  await go('products','[data-action=new-product]');
  async function product(name,code,unit,price,stock){
    click('[data-action=new-product]');fill('#f-name',name);fill('#f-code',code);fill('#f-unit',unit);fill('#f-price',price);submit('[data-form=product]');
    await waitFor(()=>!doc.querySelector('[data-form=product]')&&[...doc.querySelectorAll('#product-table tr')].some(r=>r.textContent.includes(name)),'produto salvo e lista atualizada');
    const rows=[...doc.querySelectorAll('#product-table tr')],row=rows.find(r=>r.textContent.includes(name));assert.ok(row);
    row.querySelector('[data-action=adjust-stock]').click();fill('#f-quantity',stock);fill('#f-reason','Estoque de teste');submit('[data-form=stock]');
    await waitFor(()=>!doc.querySelector('#dialog').open,'estoque salvo');
  }
  await product('Arroz <teste>','7891001','un','6,49','10');
  await product('Banana','42','kg','12,00','5');
  assert.equal(doc.querySelector('img'),null);
  await go('cash','[data-form=open]');fill('#f-operator','Operador');fill('#f-opening','100');submit('[data-form=open]');
  await waitFor(()=>doc.querySelector('[data-form=close]'),'turno aberto');
  await go('sale','#f-search');
  fill('#f-search','7891001');submit('[data-form=quick]');await waitFor(()=>doc.querySelectorAll('.cart-item').length===1,'produto por código');
  fill('#f-search','42');submit('[data-form=quick]');await waitFor(()=>doc.querySelector('[data-form=weight]'),'produto pesado');
  fill('#f-weight','0,750');assert.match(doc.querySelector('#weight-preview').textContent,/9,00/);submit('[data-form=weight]');
  await waitFor(()=>doc.querySelectorAll('.cart-item').length===2,'peso adicionado');assert.match(doc.querySelector('#cart-footer').textContent,/15,49/);
  // Atalho real despachado ao controlador de teclado, sem um navegador.
  doc.dispatchEvent(new w.KeyboardEvent('keydown',{key:'F8',bubbles:true,cancelable:true}));await waitFor(()=>doc.querySelector('[data-form=payment]'),'pagamento pelo F8');
  fill('#f-received','1');submit('[data-form=payment]');await waitFor(()=>doc.querySelector('[data-form=payment] [data-error]').textContent.includes('menor'),'erro recuperável');
  assert.equal(doc.querySelector('#f-received').value,'1');
  dropSaleResponse=true;fill('#f-received','20');assert.match(doc.querySelector('#change-preview').textContent,/4,51/);submit('[data-form=payment]');
  await waitFor(()=>!doc.querySelector('#dialog').open&&doc.querySelector('#cart-footer').textContent.includes('Conferir a'),'resposta perdida preserva a mesma venda');
  assert.ok(JSON.parse(w.localStorage.getItem('balcao-cart')).pending.nonce);
  click('[data-action=checkout]');
  await waitFor(()=>doc.querySelector('.receipt'),'comprovante sem venda duplicada');assert.match(doc.querySelector('.receipt').textContent,/15,49/);assert.match(doc.querySelector('.receipt').textContent,/não fiscal/);
  click('[data-action=close-dialog]');
  assert.match(doc.querySelector('#cart-footer').textContent,/0,00/);
  await go('products','#product-table');const banana=[...doc.querySelectorAll('#product-table tr')].find(r=>r.textContent.includes('Banana'));assert.match(banana.textContent,/4,250/);
  await go('cash','[data-form=close]');fill('#f-counted','115,49');doc.querySelector('[data-form=close] [type=checkbox]').checked=true;submit('[data-form=close]');
  await waitFor(()=>doc.querySelector('[data-form=open]'),'caixa fechado');assert.match(doc.body.textContent,/0,00/);
  await go('history','[data-action=receipt]');assert.equal(doc.querySelectorAll('[data-action=receipt]').length,1);
  assert.deepEqual(errors,[]);
});
