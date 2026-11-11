# Balcão

<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
Operadores e proprietários de mercearias e mercadinhos, conforme pedido do usuário.

## Product Purpose
Registrar vendas no balcão, movimentar estoque e conferir o dinheiro do turno.

## Operating Context
Atendimento frequente, busca de produtos e conferência de valores durante uma venda.

## Capabilities and Constraints
O usuário confirmou dois tipos: produtos cadastrados lidos por código na etiqueta e produtos pesados com valor proporcional ao peso. Primeira entrega funcional, em desenvolvimento. Escopo adotado para iniciar: um computador e um caixa, banco local, teclado e leitor que digita códigos. O peso é digitado a partir do visor da balança nesta entrega; integração automática e modelo de balança continuam em aberto. Sem integração fiscal, adquirente ou recebimento automático de Pix/cartão. Comprovante não fiscal.

## Stack
Decisão provisória de implementação: Python, Flask, Waitress, SQLite e JavaScript sem framework, para instalar no Windows sem exigir Node no uso diário. Não é uma preferência de tecnologia declarada pelo usuário.

## Voice
Português brasileiro, ações diretas e valores monetários legíveis. Sem jargão de infraestrutura na operação do caixa.
