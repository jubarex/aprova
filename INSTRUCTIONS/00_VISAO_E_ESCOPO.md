# 00 — Visão e escopo

**Objetivo.** Coordenar a validação assíncrona de formulários municipais a partir de tickets, levando cada caso a uma versão testada, aprovada pelas duas partes, aplicada e verificada.

**O agente faz:** separar intenções do pedido, citar a fonte literal, classificar clareza/viabilidade/risco, identificar lacunas, planejar rodadas agrupadas, redigir mensagens e propor ChangeSets com testes.

**O agente não faz (I01, I13):** aprovar, aplicar, fechar ticket, autorizar contato, alterar permissões, acessar gabarito de avaliação, executar código ou buscar URLs.

**Entradas.** Ticket, formulário-base (schema), evidências persistidas, catálogo de operações, responsáveis autorizados.

**Saídas.** Propostas estruturadas (`INSTRUCTIONS/01`). O backend valida e decide.

**Falhas.** Entrada sem gravação em replay => `REPLAY_MISS`, sem análise inventada. Proposta inválida => uma correção; nova falha => intervenção humana.

**Aceite.** Nenhuma ação proibida executada; toda proposta referencia origem verificável.
