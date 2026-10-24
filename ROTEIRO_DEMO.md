# Roteiro de apresentação — Aprova Command

**Desafio 2:** coletar e validar a regra de negócio de ~100 processos sem depender de reunião.
**Indicador que o produto mexe:** idas e vindas até a regra estar completa (rodadas agrupadas) e cobertura auditável (fonte + teste + dupla aprovação).

> Tudo é **demonstração com dados sintéticos**: IA em *replay offline* (gravações identificadas), extração de anexos simulada, sem integração real com Pylon/WhatsApp. Os rótulos ficam visíveis na tela.

## Antes de começar

`.\scripts\demo.ps1` sobe tudo já populado e abre o navegador. Para recomeçar do zero: `.\scripts\demo.ps1 -Reset`.
Entre como **Rui Prado (implantador)**. Para o lado da prefeitura: *Trocar persona* → **Ana Souza**.

## Roteiro curto (3 min)

1. **Hoje** (Rui). “O que eu preciso fazer hoje”: tarefas por prazo, cada uma com o cliente, o motivo e a ação. Mostre atrasados e em risco no topo, depois as decisões.
2. Abra **Aprovar pela Aprova a versão … de ISS-012** (cenário G). No painel *O que está acontecendo*: o que, por quê, próximo passo e com quem está a bola. Aba **Dossiê**: cada pedido com a **citação literal** da fonte. Aba **Formulário e testes**: o diff, testes positivo/negativo/limite, hash da candidata.
3. **Aprovar pela Aprova** → aplicação, leitura de volta do motor e fechamento. O caso vira *Concluído* (aba Linha do tempo mostra cada recibo).
4. **Portal da prefeitura** (Ana, em largura de celular): *Seu próximo passo*, “Por que perguntamos”, resposta, e “Recebido. O que acontece agora”.
5. **Métricas**: cobertura auditável, rodadas, N/A quando não há denominador.

## Roteiro completo (5 min) — acrescente

6. **Cenário A** (ISS-030): cinco pedidos misturados viram um pacote de 3 lacunas para a Ana; resposta parcial não encerra nada; “ok” é ignorado; a rodada seguinte (João, Obras) leva **só o que falta**. Aba *Rodadas e lacunas* mostra “por que assim”.
7. **Pylon + WhatsApp + Portal no mesmo caso**: aba *Conversas*. A resposta do Portal aparece espelhada no Pylon (sem virar evidência duplicada).
8. **Cenário B** (VIG-002): ninguém cobre a Vigilância; Ana indica Carlos; *Autorizar este assunto* repassa só o tema sanitário.
9. **Cenário D** (ISS-012 de Serra Alta): “todos” vs “somente alimentação” → lacuna **disputada**, o sistema não escolhe; a decisão humana retoma.
10. **Cenário E**: pedido fora do playbook → intervenção com contexto; a decisão vira evidência.
11. **Cronograma** e **Clientes**: 70 processos por prefeitura, atrasos com texto e hachura.

## Perguntas prováveis

- **“A IA aprova?”** Não. A IA propõe; o backend valida citações, catálogo, permissões e transições. Duas aprovações humanas distintas, sobre o mesmo hash.
- **“E se editarem depois de aprovar?”** Editar candidata/testes invalida as duas aprovações (teste automatizado).
- **“Funciona com texto novo?”** No modo replay, texto fora das gravações vira `REPLAY_MISS` (nada é inventado). A generalização (cenário F) exige inferência ao vivo com credenciais e está como *não executada*.
- **“Onde estão as instruções do agente?”** `INSTRUCTIONS.md` e a pasta `INSTRUCTIONS/`; cada análise registra o id e o hash das instruções carregadas.

## Contingência

*Demonstração → Restaurar* (digite RESETAR) e *Popular com dados de exemplo*; ou `.\scripts\demo.ps1 -Reset`. `python -m app.evaluation --gate offline` reproduz os cenários por script.
