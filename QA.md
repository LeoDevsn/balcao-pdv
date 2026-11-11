# Verificação da versão 0.1.1

## Executado

- 18 testes Python: centavos, peso e arredondamento; estoque insuficiente; quantidade inteira; preço alterado; Pix/cartão sem confirmação; repetição de venda mesmo após fechar o turno; concorrência de vendas; cancelamento e estoque; diferença no fechamento; turno antigo; backup e integridade SQLite; autenticação, limite de tentativas, CSRF e acesso somente local.
- Um teste de interface em DOM simulado com servidor HTTP real: primeiro acesso, produtos por unidade e quilo, estoque inicial, abertura, leitura por código, cálculo de peso, F8, valor insuficiente com campos preservados, troco, confirmação perdida e nova tentativa sem venda duplicada, comprovante, baixa por peso e fechamento.
- Dependências do front auditadas na instalação: nenhuma vulnerabilidade reportada.
- Detector Impeccable: `[]`. O resolvedor não seguiu `/static/style.css` como arquivo relativo; o CSS foi fornecido diretamente como alvo. Esse resultado é uma checagem mecânica de fonte, sem aprovação visual.

## Limites

O host de acesso ao navegador estava indisponível. DOM e HTTP não comprovam aparência, foco de diálogos no navegador, impressão, operação por toque ou comportamento a 200% de zoom. Não se afirma aprovação visual ou conformidade WCAG. Regras responsivas e estados de foco existem no código; a revisão renderizada permanece pendente.

Sem teste com leitor, balança ou impressora físicos; sem homologação fiscal ou de adquirente. Nenhum pagamento real realizado. Peso é digitado. Pix/cartão são registros de recebimentos conferidos fora do aplicativo.

Não houve uso em uma loja real. A publicação corresponde a um MVP inicial, não a uma certificação de operação comercial.
