# Veredito

**Classificação: APROVADO_COM_RESSALVAS para iniciar a implementação pela fatia 1 da especificação revisada.**

**Gate de implantação: FAIL.** Não existe aplicação executável neste repositório para validar ou implantar. Publicação em produção também está explicitamente fora do escopo da especificação.

Revisão realizada em **24/10/2026**, sobre a [especificação revisada 1.1](<Aprova Command — Especificação completa para desenvolvimento.md>), confrontada com `../desafios.txt`, a pesquisa de contexto e o inventário do workspace. O escopo autorizado nesta revisão foi melhorar o plano e avaliar prontidão; não implementar ou publicar o produto.

Resumo:

- O objetivo está alinhado ao desafio 2: coletar e validar regras sem depender de reuniões.
- As lacunas de contrato foram corrigidas no documento principal: versões/testes, estados, concorrência, canais, permissões, avaliação e entrega em fatias.
- A demo offline e a prova de generalização têm gates distintos. Replay não comprova análise de formulário desconhecido.
- A aprovação do plano não atesta código, segurança, desempenho ou prazo de entrega. Esses resultados continuam pendentes.

# Grilling

## Perguntas bloqueantes

Para iniciar a fatia 1, nenhuma pergunta adicional é necessária: os limites da demo local e seus contratos estão definidos.

Para liberar gates posteriores, faltam respostas com evidência:

- **Generalização:** qual provedor/modelo será configurado e qual o resultado das nove execuções reservadas de F? Sem inferência ao vivo, F permanece `not_run`.
- **Implantação local:** qual commit passou por instalação limpa, build, testes, reinício e roteiro? Nenhum existe como evidência nesta revisão.
- **Publicação compartilhada/produção:** qual ambiente, identidade, isolamento, operação e política de dados serão utilizados? Isso requer escopo posterior; não é requisito para começar a demo local.

## Perguntas importantes

- Qual equipe e janela de desenvolvimento estão disponíveis? O prazo do hackathon consta em `desafios.txt`, mas a capacidade de concluir o escopo não foi comprovada. A sequência agora permite entregar uma fatia explicitamente parcial.
- Quem revisará o gold e os resultados esperados dos testes de regras? O plano exige revisão independente da saída do próprio modelo antes do gate correspondente.

## Perguntas não bloqueantes

- Nomes definitivos, detalhes do tema medieval e polimento podem ser decididos após o fluxo funcional.

# Escopo

**Classificação do escopo: GRANDE.** O plano cobre domínio, IA, simuladores, banco, execução persistente, interface, avaliação e apresentação. Seria arriscado tratar tudo como uma única entrega.

## Plano fatiado

A seção 19 da especificação substitui as nove etapas horizontais por cinco fatias, cada uma com objetivo, áreas, exclusões, risco, aceite, verificação, dependências e ordem:

1. **Ciclo completo estreito:** um ticket/formulário, condição testável, candidata, duas aprovações, aplicação e fechamento pela UI; documentação e CI desde o início.
2. **Rodadas multicanal:** dossiê, lacunas, agrupamento, dois canais, prazos e persistência.
3. **Exceções e responsáveis:** indicação autorizada, repasse restrito, anexos, conflito, intervenção e retomada.
4. **Generalização medida:** inferência ao vivo em conjunto reservado; prova técnica antecipada assim que o intake existir.
5. **Demo e empacotamento:** mapa/lista, escala visual, métricas, instalação limpa e apresentação.

Fatias 1–2 entregam um marco parcial. Fatias 1–3 e 5 compõem a demo offline completa. A entrega integral exige também a fatia 4 aprovada.

# O que está bom

- Monólito modular com SQLite e worker local é coerente com uma demo sem infraestrutura externa.
- LLM propõe; políticas determinísticas controlam efeitos, aprovação e fechamento.
- Persistência, citações verificáveis, clareza separada de viabilidade e simulação identificada são bons fundamentos.
- O produto privilegia exceções e colaboração assíncrona, diretamente relacionadas ao problema do implantador.

# Problemas encontrados

Os achados abaixo descrevem a versão recebida. **Corrigido no plano** significa que o contrato foi definido; não significa que foi implementado/testado.

| Problema | Gravidade / categoria | Por que importava | Correção e situação |
|---|---|---|---|
| Replay obrigatório versus formulário desconhecido | Alta / correção e avaliação | O modo padrão não poderia cumprir o teste eliminatório | Gates offline/generalização separados; F reservado e `not_run` sem inferência. Corrigido em abertura, §§2.1, 11, 16–17 e 20 |
| Estados enumerados sem contrato de transição | Alta / arquitetura | Rejeição, pausa, falha parcial, evidência tardia e reabertura ficariam à interpretação do implementador | Guardas, destinos, precedência e ciclos definidos em §§4.4–4.5; testes ainda pendentes |
| Idempotência somente declarada | Alta / dados e confiabilidade | Queda após efeito e antes do ACK poderia duplicar envio/aplicação | Inbox transacional, CAS, lease/token, outbox e recibo no receptor em §5.4; T01–T03/T14 especificados |
| Aprovação não vinculada a todo o artefato executável | Alta / dados e autorização | Candidata/base/testes poderiam mudar entre aprovação e aplicação | Snapshot/hash/suíte, invalidação de ambas, CAS da base e rechecagem no fechamento em §3.16 |
| Read-back usado como garantia insuficiente de validação | Alta / correção e produto | Persistir uma regra não prova seu comportamento | Casos positivos/negativos/limites obrigatórios antes da aprovação e após read-back, §3.15 |
| Schema e operações sem linguagem definida | Alta / arquitetura | Backend e frontend poderiam implementar semânticas divergentes | Schema v1, IDs, AST restrita, operações tipadas e limites em §3.15; schemas executáveis ficam para fatia 1 |
| Canal principal por caso e rodadas de múltiplos responsáveis | Alta / dados e produto | Preferência de um contato afetaria outro; resposta tardia poderia ser atribuída à rodada errada | Uma rodada ativa por caso, canal por destinatário, correlação explícita e triagem em §4.5 |
| Espera e ausência de resposta sem prazos | Média / produto e operação | O soldado poderia ficar parado indefinidamente ou enviar lembretes excessivos | Política global demonstrativa, relógio controlável, limites e intervenção em §4.5 |
| Papéis sem identidade do ator e endpoints sem guardas concretas | Alta na demo; crítica se publicada / segurança | Aprovação/reset e acesso municipal poderiam ser burlados pela API | Sessão sintética, escopo/papel no servidor, bind local e contratos HTTP em §§5.5 e 9.7; publicação continua excluída |
| Anexos e saídas do modelo sem limites operacionais | Alta / segurança | Arquivos inseguros, instruções maliciosas ou entradas excessivas poderiam provocar efeitos indevidos | Upload limitado, caminho interno, renderização segura, dados separados de instruções e validação de propostas em §§5.4–5.5/7.5 |
| Avaliação sem comparador/baseline/denominadores | Alta / testes | Números poderiam refletir seed, replay ou exclusão de falhas | Manifesto, gold, matching, baseline, metas e contagens em §16.3; nenhum resultado medido nesta revisão |
| Sequência tardia de integração/UI e documentação | Alta / escopo e manutenção | O primeiro fluxo completo só apareceria perto do fim | Cinco fatias verticais e README/INSTRUCTIONS/CI na primeira, §§18–19 |
| Mapa de 140 unidades sem critérios de uso | Média / UX | Excesso de atributos e cor como único sinal prejudicariam operação | Unidade compacta, painel de detalhe, lista/filtros, teclado, dados obsoletos e ensaio definidos em §10.9 |

Alternativa adotada em todos esses pontos: contratos pequenos verificáveis no monólito, sem acrescentar serviços distribuídos ou infraestrutura de produção ao hackathon.

# Code judo possível

- Uma rodada ativa por caso evita um coordenador de múltiplas rodadas concorrentes no MVP.
- Polling local substitui a necessidade de WebSocket; SVG/CSS mantém a metáfora visual sem engine.
- Preview, testes e aplicação compartilham o mesmo avaliador determinístico de condições.
- O mesmo serviço de políticas atende API e worker; não criar atalhos de aprovação/fechamento para a demo.

# O que eu apagaria ou interromperia

- Interromper a promessa de que replay prova generalização e a interpretação de “especificação completa” como “produto pronto”.
- Adiar mapa elaborado, telas secundárias e multimodalidade até existir o ciclo completo estreito.
- Evitar duplicação de instruções entre código e INSTRUCTIONS e schemas divergentes entre backend/frontend.
- Manter integrações reais, microsserviços e publicação produtiva fora desta entrega.

# O que precisa mudar antes de produção

1. Implementar e verificar o produto; hoje existem documentos e assets da pesquisa, não aplicação.
2. Cumprir o gate local com evidências por commit, sem marcar testes não executados como aprovados.
3. Abrir escopo de publicação: identidade/autorização, isolamento, dados, segredos, operação, backups/restauração e migração/rollback. Nenhum ambiente de hospedagem foi escolhido ou implantado.

# Verificações obrigatórias

## Mínimo obrigatório

| Gate | Evidência atual | Parecer |
|---|---|---|
| Especificação para iniciar fatia 1 | Contratos, limites e aceite corrigidos no documento | **CONCERNS**: pode iniciar; qualidade ao vivo e prazo continuam a validar |
| Aplicação executável/build/migrações | Ausentes no inventário | **FAIL** |
| Testes de domínio, integração, T01–T16 e E2E | Descritos; não há suíte implementada para executar | **FAIL** |
| Demo local sem credenciais | Fluxo especificado; sem execução verificável | **FAIL** |
| Generalização F | Protocolo definido; sem modelo configurado nem avaliação | **NOT RUN** |
| UX, performance e apresentação | Critérios definidos; sem interface ou ensaio | **MANUAL CHECK NEEDED** após implementação |
| Publicação em rede/produção | Fora do escopo e sem controles/infra implementados | **FAIL** |

Painel solicitado pela skill `gate-check`, adaptado de jogo para aplicação operacional:

| Perspectiva | Revisão independente do plano recebido | Resultado para liberação da demo |
|---|---|---|
| Produto | CONCERNS: faltavam testes de regras, canal por contato e protocolo de avaliação | NOT READY |
| Técnica | CONCERNS: faltavam contratos de estado, concorrência, versões e autorização | NOT READY |
| Produção/escopo | CONCERNS: sequência horizontal e escopo excessivo para promessa única | NOT READY |
| Visual/UX | CONCERNS: hierarquia das 140 unidades e estados de operação incompletos | NOT READY |

Os contratos foram incorporados à revisão 1.1. O painel não executou um produto nem certificou uma interface inexistente.

Uma segunda revisão técnica da revisão 1.1 considerou **READY para iniciar a fatia 1**, sem bloqueios de planejamento, e confirmou **NOT READY para implantação**. Foram incorporados os ajustes finais de arestas de estado, recuperação de falha permanente, rechecagem de versão vigente no fechamento e escopo/ordem de validação de chaves idempotentes HTTP; T15/T16 cobrem as duas últimas condições. O parecer geral mantém CONCERNS para a entrega completa porque inferência, prazo e execução ainda não têm evidência.

Verificações documentais executadas: inventário de arquivos, leitura integral da especificação por blocos, confronto com requisitos locais, `git diff --check`, parse dos exemplos JSON, conferência de numeração/referências de seções, delimitadores de código e UTF-8. Não houve teste funcional da aplicação, pois não há aplicação/test runner neste workspace.

## Ideal

Após o gate mínimo: ensaiar restauração e falhas em mais de um ambiente; testar usabilidade com implantador; avaliar entradas adicionais reservadas. Piloto real é necessário para alegações de redução de reuniões ou tempo de implantação; benchmark sintético não sustenta esse resultado.

## Verificação do próprio parecer

1. **[TOOL ACTION] Há código executável que foi ignorado?** Releitura do inventário mostrou somente especificação, pesquisa, desafios e assets de visualização; não há backend/frontend da aplicação, manifest de dependências, migração ou suíte.
2. **[TOOL ACTION] F ainda exige generalização em replay?** Rebusca e leitura de §§2.1, 11/F, 16.3, 17 e 20 confirmaram a separação e `not_run` sem inferência ao vivo.
3. **As correções documentais fabricaram PASS de implantação?** Não. Checklists permanecem pendentes e nenhum teste funcional é alegado como executado.
4. **Há requisito de produção indevidamente bloqueando desenvolvimento local?** Não. O destino local e a fatia 1 podem avançar; publicação tem gate separado.
5. **Qual o menor caminho para uma nova avaliação favorável?** Implementar ciclo completo; exercitar persistência/políticas/testes; empacotar e comprovar instalação/demo. Acrescentar F ao vivo para a alegação de generalização.

Chain-of-Verification: **5 perguntas verificadas — gate de implantação permanece FAIL.**

# Riscos se ignorar

- Aplicar uma regra diferente da aprovada, duplicar efeitos após reinício ou fechar ticket com evidência pendente.
- Demonstrar generalização inexistente e métricas infladas por replay/seed.
- Gastar a janela do hackathon em telas e não obter um fluxo verificável.
- Publicar uma ferramenta de troca livre de personas como se tivesse autenticação real.

# Decisão técnica

- **Boa escolha?** Sim, como demo local de coordenação assíncrona com políticas explícitas.
- **É assim que sistemas grandes fariam?** Os invariantes de versão, autorização e idempotência são pertinentes; a escala real ainda não foi testada.
- **Overengineering?** A infraestrutura proposta é enxuta; o volume funcional precisa dos marcos definidos.
- **Underengineering?** Os contratos inicialmente eram insuficientes; agora estão descritos, mas dependem da implementação.
- **Seguir, simplificar ou parar?** Seguir pela fatia 1 e preservar o recorte local. Não publicar.
- **O que tende a falhar primeiro?** Integração/concorrência e qualidade de inferência, seguidas do prazo para completar toda a apresentação.

# Notas

Avaliação qualitativa do plano, sem atribuir notas numéricas sem evidência:

- Correção, arquitetura e dados: contratos revisados; execução pendente.
- Simplicidade e manutenção: direção adequada, desde que respeitadas as fatias.
- Segurança: suficiente como direção de demo local; inadequada para declarar prontidão produtiva.
- Testabilidade: cenários, regressões e limiares definidos; testes ainda inexistentes.
- Observabilidade: logs/heartbeat/recibos especificados; operação não verificada.
- Pronto para produção: **não**.

As consultas técnicas foram limitadas a fontes primárias: [SQLite: isolamento](https://www.sqlite.org/isolation.html), [SQLite: foreign keys](https://www.sqlite.org/foreignkeys.html), [SQLAlchemy: dialeto SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html), [OWASP: uploads](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) e [OWASP: prompt injection](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html). As decisões específicas de limites e políticas da demo são escolhas de projeto, não resultados dessas fontes.

# Decisão final

**Pode seguir com a implementação em fatias após os ajustes documentais já realizados. Não está pronto para implantação.**

O próximo passo concreto é a fatia 1: ciclo completo pequeno pela interface, com regra testável, candidata imutável, dupla aprovação, aplicação recuperável, read-back e fechamento. Reavaliar a liberação com evidências reais desse produto; não é necessário redesenhar toda a solução antes de começar.
