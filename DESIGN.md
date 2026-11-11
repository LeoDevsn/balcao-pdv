---
name: Balcão
description: Frente de caixa clara, direta e voltada ao atendimento no balcão.
colors:
  primary: "#b02626"
  primary-deep: "#8d1b1b"
  ink: "#242525"
  muted: "#585b60"
  paper: "#ffffff"
  ground: "#f1f2f3"
  line: "#d5d7d9"
  focus: "#215ea6"
  success: "#176744"
  warning: "#79500a"
typography:
  title:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Public Sans, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0em"
rounded:
  control: "6px"
  panel: "12px"
spacing:
  compact: "8px"
  standard: "16px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
---

## Overview

Modo Operate. O campo de trabalho prioriza código, produto, quantidade, peso e valor. A referência adotada para começar foi a clareza de um catálogo de supermercado: nome legível, preço alinhado e vermelho reservado à ação principal. É uma decisão inicial de implementação, ainda sem aprovação visual do usuário.

Impeccable forneceu o índice 7 da exploração de direção (`seed:32c7691787eed214`). Foram consideradas referências de etiquetas, formulários comerciais, feira de bairro, livros de estoque, embalagens de cooperativa, sinalização e catálogos. A direção de catálogo informa hierarquia e economia, sem reproduzir anúncios ou inventar ofertas. Não houve comps gerados ou seleção visual pelo usuário.

## Colors

Tokens extraídos de `balcao/frontend/style.css`. Fundo cinza frio e áreas brancas para ambientes comerciais iluminados; vermelho para concluir operações, azul para foco, texto e valores em grafite. Alertas e situações são descritos em texto além da cor.

## Typography

Public Sans local, pesos 400/600/700, SIL OFL. Corpo 15px; título 24px; total da venda 32px. Valores usam numerais tabulares. Nome dos produtos pode quebrar linha; códigos e preço não devem competir com o total.

## Layout

Navegação superior: Venda, Produtos, Caixa, Histórico. Venda com catálogo e busca à esquerda, comprovante em construção à direita. Produtos e Caixa usam tabela/área principal e formulário de operação ao lado. Em 760px as áreas empilham; em 1000px busca e quantidade reorganizam. Tabelas mantêm rolagem horizontal para preservar colunas. Revisão renderizada pendente.

## Elevation & Depth

Painéis delimitados por borda simples. Sombra apenas em diálogo e aviso temporário. Nenhum efeito decorativo de vidro, gradiente ou sombra em cartões.

## Shapes

Controles com raio de 6px; regiões de trabalho 12px. Diálogos reservados ao peso de um item, confirmação financeira, ajuste de estoque e comprovante.

## Components

Busca não recria o formulário a cada tecla. F2 acessa a busca; F8 abre pagamento. Peso tem prévia de subtotal. Valor insuficiente preserva os campos. Uma tentativa financeira sem resposta fica bloqueada para conferência da mesma venda. Botões têm estado ocupado, desabilitado e foco visível. `prefers-reduced-motion` desativa transições. Impressão mostra apenas o comprovante não fiscal.

## Do's and Don'ts

Usar verbos de operação e especificar unidade/quilo. Manter valores alinhados. Pedir confirmação do recebimento externo antes de registrar Pix/cartão. Não afirmar integração com balança, gateway ou emissão fiscal. Não trocar a composição de caixa por um painel de métricas. Não tratar testes de DOM ou detector de código como aprovação visual.
