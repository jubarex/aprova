Perfeito. Com esses ajustes, o **Aprova Command deixa de ser apenas o cockpit interno dos soldados** e passa a ter duas experiências conectadas:

- **Workspace da Aprova:** implantação, automação, exceções e visão do que precisa ser feito hoje.
- **Portal da Prefeitura:** central única para o cliente revisar formulários, responder pendências, enviar documentos, envolver responsáveis e aprovar versões.

O Pylon pode continuar como origem/registro do ticket, mas **o cliente não precisa mais acessar o portal do Pylon**. Pylon, WhatsApp e Command passam a alimentar o mesmo caso e as mesmas pendências.

Abaixo está a lista de features que precisam existir.

# 1. Identidade visual e design system com shadcn/ui

- [ ] **Interface construída com shadcn/ui**, usando seus componentes como padrão: `Button`, `Card`, `Badge`, `Tabs`, `Table`, `Dialog`, `Sheet`, `DropdownMenu`, `Select`, `Command`, `Tooltip`, `Toast`, `Alert`, `Skeleton` e `Progress`.
- [ ] Sistema visual consistente para **Aprova, prefeitura e agentes**, sem cada tela parecer um produto diferente.
- [ ] Tema claro como padrão, com tokens de cor, tipografia, espaçamento e estados centralizados.
- [ ] Componentes de domínio reutilizáveis:
  - `MunicipalityBadge`.
  - `ProcessStatusBadge`.
  - `AgentStatusBadge`.
  - `ChannelBadge`.
  - `PriorityBadge`.
  - `EvidenceChip`.
  - `ApprovalStatus`.
  - `PendingItemCard`.
  - `SLAIndicator`.
- [ ] Loading, empty state, erro, retry e skeleton em todas as telas principais.
- [ ] Layout responsivo, com boa experiência no desktop para a Aprova e no celular para a prefeitura.
- [ ] Acessibilidade: navegação por teclado, foco visível, contraste, labels e ausência de informação transmitida apenas por cor.
- [ ] O mapa medieval usa a mesma linguagem visual do shadcn em cards, filtros, drawers e indicadores; não deve parecer um jogo separado do restante do sistema.

# 2. Contexto inequívoco de cliente, município e processo

- [ ] **Context switcher global** no topo: `Prefeitura / Implantação / Processo`.
- [ ] Exibição permanente de:
  - Nome da prefeitura.
  - UF.
  - Implantação.
  - Processo atual, quando houver.
  - Ambiente: demonstração ou produção.
- [ ] Brasão/avatar e cor de identificação do município nos dados sintéticos.
- [ ] Breadcrumbs em todas as páginas internas:
  - `Santa Aurora → Implantação 2026 → Alvará de Funcionamento`.
- [ ] O nome do município deve aparecer em:
  - Cards de processo.
  - Soldados.
  - Pendências.
  - Intervenções.
  - Tickets.
  - Notificações.
  - Métricas.
  - Linha do tempo.
- [ ] Nenhum modal de ação pode abrir sem mostrar claramente **em qual cliente e processo a ação será executada**.
- [ ] Busca global por município, processo, ticket, responsável ou soldado.
- [ ] Filtros persistentes por cliente, implantação, estado, responsável e prioridade.
- [ ] Ao trocar de município, todos os dados e ações mudam de contexto, sem misturar pendências.
- [ ] Um usuário com acesso a mais de um município pode alternar entre eles; um usuário restrito entra diretamente no seu contexto.
- [ ] Confirmação reforçada para ações sensíveis:
  > “Aplicar alterações em Alvará de Funcionamento — Prefeitura de Santa Aurora?”

# 3. Home da Aprova: “O que eu tenho que fazer hoje?”

- [ ] Criar uma home chamada **Hoje**, orientada a ações e não apenas a indicadores.
- [ ] Cabeçalho com:
  - Nome do implantador.
  - Data.
  - Quantidade de clientes sob sua responsabilidade.
  - Total de ações que dependem dele.
- [ ] Fila priorizada de trabalho com:
  - Cliente.
  - Processo.
  - O que precisa ser feito.
  - Por que precisa ser feito.
  - Há quanto tempo está esperando.
  - Impacto do bloqueio.
  - Ação principal.
- [ ] Agrupamento por tipo de ação:
  - **Precisa da minha decisão.**
  - **Preciso revisar uma alteração.**
  - **Preciso aprovar uma versão.**
  - **Preciso assumir uma conversa.**
  - **Preciso encontrar um responsável.**
  - **Preciso destravar uma falha.**
  - **Preciso acompanhar uma aprovação da prefeitura.**
- [ ] Priorização considerando:
  - Processos completamente bloqueados.
  - Tempo parado.
  - Prazo da implantação.
  - Quantidade de processos afetados.
  - Risco da alteração.
  - Aprovações que podem ser concluídas rapidamente.
- [ ] Cada item deve ter uma ação clara:
  - Revisar.
  - Responder.
  - Aprovar.
  - Devolver.
  - Reatribuir.
  - Assumir.
  - Desbloquear e retomar.
- [ ] Possibilidade de resolver ações em lote somente quando forem equivalentes e de baixo risco.
- [ ] Seção **“Avançando sem você”** com os processos que os soldados estão conduzindo autonomamente.
- [ ] Seção **“Aguardando prefeitura”**, separada das tarefas da Aprova.
- [ ] Seção **“Concluídos hoje”**, mostrando progresso real do dia.
- [ ] Seção **“Prestes a travar”**, com processos próximos do limite de espera ou follow-up.
- [ ] Depois de concluir uma ação, abrir automaticamente a próxima pendência priorizada, sem obrigar o usuário a voltar à lista.
- [ ] Uma tarefa resolvida desaparece da fila e fica registrada na auditoria.
- [ ] Métricas resumidas no topo:
  - Minhas ações.
  - Processos bloqueados.
  - Aprovações pendentes.
  - Concluídos hoje.

# 4. Portal da Prefeitura dentro do Aprova Command

- [ ] Área própria para o cliente, com navegação mais simples que a da Aprova.
- [ ] A prefeitura não visualiza o mapa interno, métricas internas, prompts, custos, outros municípios ou comentários privados.
- [ ] Home do cliente com:
  - Nome da prefeitura.
  - Nome e papel do usuário.
  - Implantação.
  - Progresso geral.
  - Pendências que dependem dele.
  - Processos aguardando outras pessoas.
  - Aprovações pendentes.
  - Últimas atualizações.
- [ ] Menu recomendado:
  - **Início.**
  - **Minhas pendências.**
  - **Processos.**
  - **Documentos.**
  - **Responsáveis.**
  - **Aprovações.**
  - **Ajuda.**
- [ ] Todo conteúdo deve usar linguagem de negócio, evitando termos como “agente”, “run”, “payload” ou “estado técnico”.
- [ ] O cliente consegue responder às pendências diretamente no Command.
- [ ] As respostas feitas no portal atualizam o mesmo caso usado pelo WhatsApp e pelo Pylon.
- [ ] Nenhuma pendência respondida em um canal pode continuar aparecendo como aberta nos outros.
- [ ] O cliente consegue consultar o histórico do que já respondeu e enviou.
- [ ] O portal funciona bem no celular, principalmente para revisão, resposta e envio de anexos.

# 5. Experiência do cliente no Dia 1

Esta jornada precisa ser implementada como um fluxo guiado, não apenas como uma tela de login.

## 5.1 Convite e entrada

- [ ] A Aprova cadastra ou importa o responsável central.
- [ ] O sistema envia um convite por canal autorizado, com identificação clara:
  - Aprova.
  - Prefeitura.
  - Implantação.
  - Objetivo do acesso.
- [ ] Link de acesso seguro, com expiração e possibilidade de novo envio.
- [ ] No hackathon, autenticação simulada pode ser usada, mas o fluxo deve ser representado integralmente.
- [ ] Primeiro acesso com boas-vindas:
  > “Prefeitura de Santa Aurora, nesta etapa você revisará os formulários dos processos e indicará as adaptações necessárias.”
- [ ] Apresentação do papel do usuário: responder, delegar ou aprovar.
- [ ] Aceite/registro do acesso e canal preferido, quando necessário.

## 5.2 Onboarding inicial

- [ ] Tutorial curto, com no máximo três pontos:
  1. Revise os formulários.
  2. Responda às pendências ou indique quem pode responder.
  3. Aprove a versão final.
- [ ] Explicação de que o cliente não precisa conhecer previamente toda a legislação ou preencher um formulário de configuração técnica.
- [ ] Exibição do responsável da Aprova e canal para pedir ajuda.
- [ ] Prazo orientativo e quantidade total de processos.
- [ ] Indicação clara de que os processos podem ser revisados progressivamente, sem terminar tudo no primeiro dia.

## 5.3 Primeira lista de processos

- [ ] Mostrar os processos recebidos, com estados:
  - Não iniciado.
  - Aguardando minha revisão.
  - Aguardando outro responsável.
  - Em ajuste pela Aprova.
  - Aguardando minha aprovação.
  - Concluído.
- [ ] Priorizar o primeiro processo sugerido.
- [ ] Permitir filtrar por setor, responsável e estado.
- [ ] Mostrar progresso por etapas, não apenas uma porcentagem inexplicável.

## 5.4 Primeira revisão do formulário

- [ ] Abrir o formulário diretamente no Command, sem redirecionar para o portal do Pylon.
- [ ] Preview fiel do formulário e de seus documentos exigidos.
- [ ] Explicação do objetivo da revisão.
- [ ] Opções claras:
  - **Está adequado.**
  - **Precisa de alterações.**
  - **Não sei responder.**
  - **Indicar responsável.**
- [ ] Se estiver adequado, registrar a validação daquela versão.
- [ ] Se precisar de alterações, abrir uma área de resposta livre e estruturada.
- [ ] Permitir escrever uma resposta extensa sem obrigar o cliente a separar manualmente cada pedido.
- [ ] Permitir anexar formulário antigo, documento, planilha, imagem ou áudio.
- [ ] Permitir comentar sobre um campo específico, quando o cliente souber identificar o ponto.
- [ ] Permitir salvar rascunho e continuar depois.
- [ ] Não perder a resposta se o usuário sair da tela.

## 5.5 Confirmação da resposta inicial

- [ ] Após o envio, apresentar uma confirmação:
  > “Recebemos sua revisão. A Aprova analisará os pontos e você será chamado apenas se houver alguma pendência.”
- [ ] O agente processa a resposta e gera o dossiê automaticamente.
- [ ] Se houver lacunas, criar uma rodada consolidada.
- [ ] Se a resposta estiver completa, avançar para alteração e aprovação sem enviar perguntas desnecessárias.
- [ ] O cliente acompanha o estado sem precisar abrir ticket ou perguntar pelo WhatsApp.

# 6. Central única de pendências da prefeitura

- [ ] Uma pendência possui dono, processo, assunto, prazo e estado.
- [ ] A central reúne pendências originadas no Command, WhatsApp ou Pylon.
- [ ] Tipos de pendência:
  - Responder esclarecimento.
  - Revisar interpretação.
  - Confirmar alteração.
  - Enviar documento.
  - Indicar responsável.
  - Resolver divergência.
  - Revisar formulário.
  - Aprovar versão.
- [ ] Pendências agrupadas por processo e rodada, não uma lista de mensagens soltas.
- [ ] Cada pendência explica:
  - O que é necessário.
  - Por que é necessário.
  - Qual decisão ou alteração será desbloqueada.
  - Quem solicitou.
  - Qual é o prazo.
- [ ] Responder por texto, anexo, áudio ou indicação de responsável.
- [ ] Possibilidade de responder parcialmente e continuar depois.
- [ ] Marcar “não sei” sem travar a interface; o sistema busca outro responsável ou aciona a Aprova.
- [ ] Pendências independentes podem ser delegadas a pessoas diferentes.
- [ ] O cliente vê o que depende dele e o que depende de outros setores.
- [ ] Lembretes são enviados somente para pendências ainda abertas.
- [ ] Ao responder, todas as visualizações são atualizadas de forma idempotente.

# 7. Unificação entre Command, WhatsApp e Pylon

- [ ] Uma única `PendingItem` por necessidade real, independentemente do canal.
- [ ] A mesma pendência pode ser entregue em vários canais, mas não duplicada no domínio.
- [ ] Resposta pelo portal encerra ou atualiza a pendência no WhatsApp e no Pylon.
- [ ] Resposta pelo WhatsApp atualiza o portal.
- [ ] Comentário no Pylon atualiza o mesmo caso.
- [ ] Consolidação de respostas complementares.
- [ ] Detecção de respostas divergentes.
- [ ] Registro do canal de origem de cada evidência.
- [ ] Preferência de canal por usuário.
- [ ] Possibilidade de escolher “responder no portal” a partir de uma notificação de WhatsApp.
- [ ] Links de notificações levam diretamente à pendência específica, não à home genérica.
- [ ] O Pylon deixa de ser o portal do cliente; quando mantido, funciona como sistema de ticket e sincronização interna.
- [ ] Resumos e estados relevantes podem continuar sendo sincronizados ao ticket do Pylon.

# 8. Revisão e alteração de formulários pelo cliente

- [ ] Preview do formulário vigente.
- [ ] Visualização de alterações propostas pela Aprova.
- [ ] Diff antes/depois em linguagem compreensível:
  - Nome alterado.
  - Campo incluído.
  - Campo removido.
  - Obrigatoriedade alterada.
  - Documento incluído.
  - Condição alterada.
- [ ] Cada alteração mostra a justificativa e a evidência relacionada.
- [ ] O cliente pode:
  - Concordar.
  - Discordar.
  - Comentar.
  - Pedir esclarecimento.
  - Indicar responsável.
- [ ] Discordância reabre somente os pontos afetados, não todo o processo.
- [ ] Alterações posteriores geram nova versão.
- [ ] O cliente sempre sabe qual versão está revisando.
- [ ] Nenhuma alteração é publicada silenciosamente.

# 9. Gestão de responsáveis pela própria prefeitura

- [ ] Diretório de responsáveis por processo e setor.
- [ ] Responsável central consegue convidar outros participantes.
- [ ] Delegação de um processo inteiro ou apenas de um assunto.
- [ ] Indicação de contato quando o usuário não souber responder.
- [ ] Registro de quem indicou, para quê e com qual escopo.
- [ ] Controle de quem pode responder e quem pode aprovar.
- [ ] Convites e autorizações registrados.
- [ ] Possibilidade de transferir uma pendência sem perder histórico.
- [ ] Visualização de lacunas de responsável:
  - Processo sem responsável.
  - Assunto sem especialista.
  - Processo sem aprovador.
- [ ] Retomada automática do processo após a resposta do novo responsável.

# 10. Aprovações no portal

- [ ] Área específica para aprovações pendentes.
- [ ] Exibir formulário, versão, alterações e evidências.
- [ ] Declaração clara do que a aprovação significa.
- [ ] Aprovação com identidade, timestamp e registro.
- [ ] Possibilidade de rejeitar/devolver com comentário.
- [ ] Apenas usuários com papel de aprovador podem aprovar.
- [ ] Aprovação municipal separada da aprovação da Aprova.
- [ ] Alteração material invalida as aprovações afetadas.
- [ ] Certificado/comprovante simples da aprovação disponível para consulta.
- [ ] Histórico completo de versões aprovadas.

# 11. Notificações e comunicação com o cliente

- [ ] Central de notificações dentro do portal.
- [ ] Notificações para:
  - Novo processo disponível para revisão.
  - Nova pendência.
  - Documento solicitado.
  - Alteração pronta para revisão.
  - Aprovação necessária.
  - Resposta recebida de outro setor.
  - Processo concluído.
- [ ] Preferência de canal e frequência.
- [ ] Resumo consolidado em vez de uma notificação por pergunta.
- [ ] Lembretes progressivos e política de follow-up.
- [ ] Nenhuma notificação duplicada por múltiplos canais sem necessidade.
- [ ] Identificação do município e processo em todas as mensagens.
- [ ] Link direto para a ação.
- [ ] Opção de pausa, canal alternativo ou ajuda humana.

# 12. Features do agente que precisam suportar o novo portal

- [ ] Interpretar respostas enviadas pelo portal com a mesma engine usada para WhatsApp/Pylon.
- [ ] Converter respostas livres em intenções, alterações e lacunas.
- [ ] Gerar rodadas agrupadas por próxima etapa.
- [ ] Atualizar pendências existentes em vez de criar duplicatas.
- [ ] Reconhecer respostas parciais.
- [ ] Resolver múltiplas lacunas com um único documento.
- [ ] Detectar quando uma ação já foi concluída por outro canal.
- [ ] Preparar resumo para o cliente em linguagem simples.
- [ ] Escalar pedidos de consultoria ou conflitos.
- [ ] Não exigir instruções específicas por formulário.
- [ ] Trabalhar com formulários desconhecidos usando schema, contexto e catálogo genérico.
- [ ] Manter o processo persistente mesmo com dias entre interações.

# 13. Visão completa do processo para a Aprova

- [ ] Linha do tempo única com:
  - Ticket.
  - Revisão do cliente.
  - Mensagens.
  - Pendências.
  - Documentos.
  - Alterações.
  - Intervenções.
  - Aprovações.
  - Aplicação.
- [ ] Separar claramente:
  - Comunicação com o cliente.
  - Notas internas.
  - Decisões do agente.
  - Ações humanas.
- [ ] Exibir quem está impedindo o avanço:
  - Aprova.
  - Responsável atual.
  - Outro setor.
  - Aprovador.
  - Falha técnica.
- [ ] Exibir próxima ação e próximo evento esperado.
- [ ] Exibir versão atual do formulário.
- [ ] Exibir lacunas abertas e alterações prontas.
- [ ] Possibilidade de o implantador assumir qualquer conversa ou pendência.
- [ ] Retomada do soldado depois da intervenção.

# 14. Mapa e gestão de múltiplos clientes

- [ ] Mapa agrupado primeiro por prefeitura, depois por processo.
- [ ] Cada território exibe nome do cliente, progresso e quantidade de bloqueios.
- [ ] Filtro para “meus clientes”.
- [ ] Visão alternativa em tabela com ordenação e filtros.
- [ ] Cards de processo sempre mostram o cliente.
- [ ] Identificação visual consistente entre mapa, lista e detalhe.
- [ ] Drill-down:
  - Município → implantação → processo → pendência/alteração.
- [ ] Indicadores de clientes que precisam de atenção hoje.
- [ ] Não exigir que o implantador percorra o mapa para descobrir suas tarefas; a home “Hoje” continua sendo o ponto de entrada operacional.

# 15. Gestão de documentos

- [ ] Repositório de documentos por município e processo.
- [ ] Versionamento de anexos.
- [ ] Visualização de origem: portal, WhatsApp ou Pylon.
- [ ] Relação entre documento, pendência, alteração e aprovação.
- [ ] Documentos podem responder múltiplas pendências.
- [ ] Indicação de processamento: recebido, analisando, analisado, precisa revisão.
- [ ] Download e preview quando suportado.
- [ ] Não permitir que anexos executem instruções ou alterem políticas do agente.
- [ ] Exclusão/retificação conforme política definida para o produto real.

# 16. Auditoria, segurança e privacidade

- [ ] Separação rigorosa dos dados por município.
- [ ] Controle de acesso por papel:
  - Administrador Aprova.
  - Implantador.
  - Aprovador Aprova.
  - Responsável central.
  - Responsável de processo.
  - Colaborador setorial.
  - Aprovador municipal.
- [ ] Usuário da prefeitura nunca acessa outro município.
- [ ] Notas internas da Aprova nunca aparecem no portal.
- [ ] Registro de toda visualização ou alteração sensível necessária à auditoria.
- [ ] Histórico de mensagens, decisões, versões e aprovações.
- [ ] Confirmação de identidade para aprovações.
- [ ] Links de convite com expiração.
- [ ] Minimização de dados nos fixtures.
- [ ] Rótulo de dados sintéticos no hackathon.
- [ ] Nenhum segredo ou credencial real no repositório.

# 17. Métricas e acompanhamento

## Para a Aprova

- [ ] Processos concluídos.
- [ ] Processos aguardando Aprova versus prefeitura.
- [ ] Minhas ações concluídas hoje.
- [ ] Tempo médio em cada estado.
- [ ] Rodadas por processo.
- [ ] Intervenções por processo.
- [ ] Processos sem responsável.
- [ ] Processos reabertos.
- [ ] Tempo até a primeira revisão do formulário.
- [ ] Canal da resposta: Command, WhatsApp ou Pylon.
- [ ] Completude das respostas por canal.

## Para a prefeitura

- [ ] Progresso da implantação.
- [ ] Minhas pendências.
- [ ] Pendências por setor.
- [ ] Processos aguardando Aprova.
- [ ] Aprovações pendentes.
- [ ] Processos concluídos.

- [ ] Nenhuma métrica de impacto real deve ser inferida de dados sintéticos.

# 18. Simuladores e demonstração

- [ ] Simulador de WhatsApp integrado à mesma central de pendências.
- [ ] Simulador de Pylon sem exigir que o cliente use seu portal.
- [ ] Motor de formulários simulado com preview e versionamento.
- [ ] Seletor de persona:
  - Implantador.
  - Responsável central da prefeitura.
  - Responsável setorial.
  - Aprovador municipal.
- [ ] Reset reproduzível dos cenários.
- [ ] Dados sintéticos para pelo menos duas prefeituras.
- [ ] Cenário completo do Dia 1.
- [ ] Cenário de resposta pelo portal.
- [ ] Cenário de resposta pelo WhatsApp refletida no portal.
- [ ] Cenário de delegação para outro setor.
- [ ] Cenário de divergência entre canais.
- [ ] Cenário de aprovação e read-back.
- [ ] Modo replay claramente identificado.
- [ ] Tela de apresentação sem controles técnicos desnecessários.

# 19. Novos fluxos obrigatórios de ponta a ponta

Além dos fluxos anteriores, estes precisam passar nos testes:

## Fluxo 1 — Dia 1 da prefeitura

```text
Convite → primeiro acesso → onboarding → lista de processos →
abrir formulário → solicitar alterações → anexar documento →
enviar revisão → agente gerar dossiê → pendências centralizadas
```

## Fluxo 2 — Resposta centralizada

```text
Pendência criada pelo agente → aparece no portal e WhatsApp →
cliente responde no portal → pendência atualizada nos dois canais →
soldado continua sem fazer nova pergunta duplicada
```

## Fluxo 3 — Delegação

```text
Cliente não sabe responder → indica responsável setorial →
novo usuário acessa somente o escopo delegado → responde →
processo original retoma
```

## Fluxo 4 — Dia de trabalho do implantador

```text
Abrir “Hoje” → ver ações por cliente → revisar alteração →
resolver intervenção → aprovar versão → próxima tarefa →
processos atualizados no mapa
```

## Fluxo 5 — Revisão e aprovação pelo portal

```text
Cliente recebe nova versão → visualiza diff e justificativas →
comenta ou aprova → Aprova aprova → aplicação → read-back → conclusão
```

# 20. Prioridade de implementação

Para não sacrificar o núcleo, a ordem deve ser:

## P0 — Indispensável

1. shadcn/ui e layout base.
2. Contexto global de município/processo.
3. Home **Hoje** para o implantador.
4. Portal da Prefeitura.
5. Fluxo do Dia 1.
6. Central de pendências.
7. Resposta pelo portal.
8. Sincronização entre portal, WhatsApp e Pylon.
9. Preview e revisão de formulário.
10. Delegação de responsáveis.
11. Aprovações pelo portal.
12. Visão completa do processo.
13. Auditoria e permissões.
14. Cenários E2E dos novos fluxos.

## P1 — Depois do P0 estável

1. Mapa medieval aprimorado.
2. Ações em lote.
3. Métricas avançadas.
4. Preferências sofisticadas de notificação.
5. Repositório documental avançado.
6. Certificado de aprovação mais elaborado.
7. Personalização visual por município.
8. Animações e polimento do mapa.

**Resumo da nova visão:** o Aprova Command passa a ser o lugar onde a prefeitura trabalha e a Aprova comanda. O cliente entra no Dia 1, entende o que precisa revisar, responde suas pendências e acompanha seus processos; o implantador abre a home e sabe exatamente **em qual cliente precisa agir, por quê e qual é a próxima ação**. WhatsApp e Pylon continuam conectados ao mesmo fluxo, mas deixam de ser pontos de fragmentação.
