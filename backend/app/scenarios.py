"""Roteiros dos cenários de produto (v2 §15.1). Cada passo reproduz exatamente uma gravação de replay.

O roteiro serve à demonstração (botão "executar passo") e aos testes. Texto livre fora do roteiro resulta
em REPLAY_MISS no modo offline: nunca se inventa análise.
"""

from __future__ import annotations

from .agent import fixtures as fx

SCENARIOS: dict[str, dict] = {
    "A": {
        "title": "A — Resposta confusa", "process_id": "proc_vr_iss030", "ticket_title": "Ajustes na baixa de inscrição",
        "reply": fx.A_REPLY, "mode": "offline_e_ao_vivo",
        "description": "Cinco pedidos misturados (rótulo, anexo condicional incompleto, campo ambíguo, formulário antigo e "
                       "outro setor). Intenções separadas com citação, um pacote de lacunas e a próxima rodada só com o que falta.",
        "steps": [
            {"id": "a1", "label": "Ana responde parte das perguntas (WhatsApp)", "type": "message", "actor": "act_ana",
             "channel": "whatsapp", "text": fx.A_S1},
            {"id": "a2", "label": "Ana responde só “ok” (não encerra nada)", "type": "message", "actor": "act_ana",
             "channel": "whatsapp", "text": "ok, obrigada", "expect": "ignored"},
            {"id": "a3", "label": "Ana responde o restante (Portal)", "type": "message", "actor": "act_ana",
             "channel": "portal", "text": fx.A_S2},
            {"id": "a4", "label": "João (Obras) responde a rodada seguinte (Portal)", "type": "message",
             "actor": "act_joao", "channel": "portal", "text": fx.A_S3},
        ],
    },
    "B": {
        "title": "B — Indicação de responsável", "process_id": "proc_vr_vig002", "ticket_title": "Licença sanitária: ajustes",
        "reply": fx.B_REPLY, "mode": "offline_e_ao_vivo",
        "description": "Ninguém autorizado cobre a Vigilância. Ana indica o técnico Carlos; só o assunto sanitário é "
                       "transferido, o implantador autoriza e o documento enviado por Carlos retoma o caso.",
        "steps": [
            {"id": "b1", "label": "Ana indica Carlos Menezes (Vigilância)", "type": "referral", "actor": "act_ana",
             "name": "Carlos Menezes", "sector": "Vigilância Sanitária", "alias": "Carlão da Vigilância", "topic": "vigilancia"},
            {"id": "b2", "label": "Implantador autoriza Carlos só para o assunto sanitário", "type": "authorize_referral"},
            {"id": "b3", "label": "Carlos envia o documento (WhatsApp)", "type": "message", "actor": "@referral",
             "channel": "whatsapp", "text": fx.B_S1,
             "attachment": {"filename": "referencia_vigilancia.txt", "content": fx.B_DOC}},
        ],
    },
    "C": {
        "title": "C — Pylon e WhatsApp na mesma rodada", "process_id": "proc_vr_obr004",
        "ticket_title": "Licença de obra: ART", "reply": fx.C_REPLY, "mode": "offline_e_ao_vivo",
        "description": "A decisão chega pelo Pylon e o documento complementar pelo WhatsApp. Uma consolidação, "
                       "sem pergunta duplicada; a candidata cita as duas fontes.",
        "steps": [
            {"id": "c1", "label": "João decide pelo Pylon", "type": "message", "actor": "act_joao", "channel": "pylon",
             "text": fx.C_S1},
            {"id": "c2", "label": "João envia o modelo da ART pelo WhatsApp", "type": "message", "actor": "act_joao",
             "channel": "whatsapp", "text": fx.C_S2,
             "attachment": {"filename": "modelo_art.txt", "content": fx.C_DOC}},
        ],
    },
    "D": {
        "title": "D — Fontes contraditórias", "process_id": "proc_sa_iss012", "ticket_title": "Licença sanitária no alvará",
        "reply": fx.D_REPLY, "mode": "offline_e_ao_vivo",
        "description": "“Obrigatório para todos” versus “somente alimentação”: a lacuna fica disputada e o sistema não "
                       "escolhe uma fonte; a decisão humana resolve e o fluxo retoma.",
        "steps": [
            {"id": "d1", "label": "Marcos: obrigatório para todos", "type": "message", "actor": "act_marcos",
             "channel": "whatsapp", "text": fx.D_S1},
            {"id": "d2", "label": "Luiza: somente alimentação", "type": "message", "actor": "act_luiza",
             "channel": "portal", "text": fx.D_S2},
            {"id": "d3", "label": "Implantador decide: somente alimentação", "type": "decision",
             "kind": "resolve_conflict", "text": fx.D_S3},
        ],
    },
    "E": {
        "title": "E — Fora do playbook", "process_id": "proc_sa_edu001", "ticket_title": "Recomendação para matrícula",
        "reply": fx.E_REPLY, "mode": "offline_e_ao_vivo",
        "description": "Pedido de recomendação sem playbook aplicável abre intervenção com contexto; a decisão humana vira "
                       "evidência e o fluxo retoma.",
        "steps": [
            {"id": "e1", "label": "Implantador registra a recomendação", "type": "decision", "kind": "provide_answer",
             "text": fx.E_S1},
        ],
    },
    "G": {
        "title": "G — Ciclo completo", "process_id": "proc_vr_iss012", "ticket_title": "Ajustes no formulário de alvará",
        "reply": fx.G_REPLY, "mode": "offline_e_ao_vivo",
        "description": "Ticket claro → candidata e testes → duas aprovações → aplicação, verificação e fechamento. "
                       "Edição posterior invalida ambas as aprovações.",
        "steps": [],
    },
}


def public_view() -> list[dict]:
    return [{"id": k, **{x: v for x, v in sc.items() if x != "reply"}, "reply": sc["reply"]} for k, sc in SCENARIOS.items()]
