# Balcão

Caixa local para **mercearias e mercadinhos**, feito em Python e interface web. Primeira versão funcional: **0.1.1**.

[Baixar para Windows](https://github.com/LeoDevsn/balcao-pdv/releases/latest) · [Reportar problema](https://github.com/LeoDevsn/balcao-pdv/issues)

## O que funciona

- Cadastro de produtos por unidade ou por quilo, com código de etiqueta ou código interno.
- Leitor de código de barras que funciona como teclado e envia Enter ao terminar a leitura.
- Produtos pesados: informe o peso da balança, em kg, e o preço é calculado por peso. Ex.: **0,750 kg × R$ 12,00/kg = R$ 9,00**.
- Venda em dinheiro com cálculo de troco; registro de Pix ou cartão já recebidos e conferidos fora do aplicativo.
- Baixa de estoque na mesma transação da venda; bloqueio de estoque insuficiente e de preço alterado durante a operação.
- Recuperação de uma confirmação perdida sem registrar a venda duas vezes. Rascunho da venda guardado neste navegador.
- Abertura com fundo de troco, entradas, retiradas e fechamento com diferença entre dinheiro esperado e contado.
- Comprovante imprimível, histórico e cancelamento auditado no turno aberto, com retorno dos itens ao estoque após o operador confirmar a devolução do pagamento.
- Backup SQLite consistente, senha local e proteção de sessão/CSRF.

## Começar no Windows

1. Baixe **Balcao.exe** na página de releases e abra o arquivo. Não é necessário instalar Python ou Node.
2. O navegador abrirá o endereço local do aplicativo. Mantenha a pequena janela do Balcão aberta durante o uso.
3. No primeiro acesso, informe o nome do mercado e crie uma senha de pelo menos 10 caracteres.
4. Em **Produtos**, clique em **Novo produto**. Informe nome, código, forma de venda e preço por unidade ou quilo.
5. Clique em **Estoque** e registre a quantidade inicial e o motivo. Estoque negativo é bloqueado.
6. Em **Caixa**, abra o turno e informe o fundo de troco.
7. Em **Venda**, leia o código ou busque pelo nome. Produtos por quilo abrem o formulário de peso. Confira os itens e use **Receber pagamento**.
8. Ao encerrar, conte o dinheiro físico e feche o turno em **Caixa**. Baixe um backup e guarde uma cópia fora deste computador.

O executável ainda não possui assinatura digital de editor. Código-fonte e SHA-256 estão disponíveis na release para conferência.

### Leitores e balanças

O leitor deve digitar o código cadastrado e enviar Enter, com o campo de busca em foco. **F2** volta à busca; **F8** abre o recebimento. A validação com modelos físicos específicos ainda está pendente.

Esta versão aceita **peso digitado em kg**, com até três casas decimais. Não conecta diretamente a balanças e não decodifica etiquetas que embutem preço ou peso: cadastre o código simples do produto e informe o peso separadamente.

### Pagamentos e comprovantes

Pix e cartão são **registros de recebimento confirmado pelo operador**: não há QR Code Pix, integração bancária, maquininha ou estorno automático. Cancelar exige devolver o pagamento fora do aplicativo e confirmar a devolução. Dinheiro precisa ter saldo disponível no caixa para o cancelamento.

O comprovante é **não fiscal**. Não há NFC-e, SAT, NFS-e ou identificação fiscal do consumidor. Este MVP não substitui um emissor fiscal. A impressão usa o diálogo de impressão do navegador, sem comunicação direta ESC/POS.

## Dados e backup

Os dados ficam em `%LOCALAPPDATA%\BalcaoPDV`. Funcionam sem internet depois de baixar o aplicativo. O serviço escuta apenas em `127.0.0.1`; esta versão recusa acesso pela rede e não deve ser publicada na internet.

O backup inclui produtos, estoque, vendas, turnos e a senha **em hash**; não inclui a chave de sessão. Proteja esse arquivo. O rascunho da venda permanece no armazenamento do navegador; se ele estiver bloqueado, a interface avisa. Depois de uma tentativa sem resposta, use **Conferir a última tentativa**, sem criar outra venda.

Para restaurar nesta primeira versão: encerre o aplicativo, crie uma pasta vazia, copie o backup para ela com o nome `balcao.sqlite3` e inicie `Balcao.exe --data-dir "C:\Caminho\PastaRestaurada"`. Essa opção usa a pasta informada sem substituir a base anterior. A senha do backup será a senha do acesso restaurado. Ainda não há restauração pela interface.

Para redefinir uma senha esquecida, encerre o aplicativo e, usando Python instalado, rode `python -m balcao --reset-password` na pasta do projeto. É uma operação administrativa local; não há recuperação por e-mail.

## Executar pelo código

Requer Python 3.12 ou superior:

```powershell
python -m pip install .
python -m balcao
```

Somente servidor local, sem abrir janelas:

```powershell
python -m balcao --server --port 7470 --data-dir "C:\Dados\Balcao"
```

## Desenvolvimento e verificação

```powershell
python -m unittest discover -s tests -v
node --check balcao/frontend/app.js
npm ci
npm test
```

Node é usado apenas nos testes do front. Veja [QA.md](QA.md) para os testes executados e os limites da validação.

Para gerar o executável: instale `pyinstaller`, rode `python scripts/build_windows.py` e `python scripts/smoke_windows.py`. `python scripts/package_release.py` gera o ZIP de fontes.

## Escopo desta primeira versão

Um computador, um caixa e um acesso administrativo local. Ainda sem múltiplos operadores com permissões, caixa em rede, importação de catálogo, TEF, venda fiada, pagamento dividido, integração fiscal ou balança automática. As listas mostram as últimas 300 vendas, 100 turnos e 100 movimentações de estoque; os registros completos permanecem no banco e no backup.

Antes de substituir um PDV existente, faltam validar equipamentos reais, revisão visual em navegador e os fluxos necessários à operação específica do estabelecimento. Não houve homologação em uma mercearia real.

Licença MIT · Leonardo Santos. Fontes Public Sans sob SIL OFL, incluída na pasta das fontes.
