# 03 — Rodadas e canais

**Objetivo.** Reduzir idas e vindas: agrupar o que falta em poucas rodadas e tratar Pylon, WhatsApp e Portal como um único caso.

**Quem decide o quê.**
- O agente identifica lacunas (`gaps`) e responde se uma resposta as encerra (`gap_updates`).
- O **backend** planeja a rodada: agrupa por destinatário, escolhe canais, publica, controla prazos e lembretes. O agente nunca envia mensagem.

**Planejamento (backend, determinístico).**
1. Pega as lacunas abertas e bloqueantes, na ordem em que surgiram.
2. O destinatário é o responsável autorizado cujo assunto (`topic`) cobre a primeira lacuna; assunto exato vence escopo amplo.
3. A rodada inclui todas as lacunas que o mesmo destinatário pode responder (antecipa dependências previsíveis). Itens de outro setor ficam para a rodada seguinte.
4. Uma rodada ativa por caso. A mensagem tem: o que entendemos, objetivo, itens numerados, canais e prazo. Nunca uma mensagem por pergunta.
5. Sem responsável para o assunto: o caso vai para `WAITING_OWNER`; o implantador autoriza alguém ou recebe uma indicação.

**Canais.** Primeira rodada: Pylon, WhatsApp e Portal com conteúdo equivalente e o mesmo `case_id/round_id`. Preferência explícita do contato prevalece; senão a primeira evidência substantiva define o canal principal, e os outros canais continuam aceitando complementos. “Ok”, “depois vejo” e recibo não encerram a espera.

**Respostas.** Rajadas são consolidadas 2 s após a última mensagem (teto de 10 s). Mensagem sem rodada inequívoca vai para triagem; nunca é atribuída à rodada mais recente.

**Prazos (relógio de negócio).** Lembrete em 24 h e 48 h; intervenção em 72 h. Pausa suspende e a retomada preserva o saldo, sem rajada. No máximo dois lembretes por rodada; lembrete não é nova rodada.

**Aceite.** Cenários A, B, C; T02, T07, T08, T11.
