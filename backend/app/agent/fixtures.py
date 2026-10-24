"""Gravações de replay (fixtures de teste). Identificadas na UI como 'IA: replay offline'.

Não são instruções de produção por formulário (v2 §2.2): cada uma é uma saída gravada
para uma entrada conhecida; entrada diferente resulta em REPLAY_MISS.
"""

from __future__ import annotations

from ..domain.forms import FormSchema, schema_hash
from . import replay

SCENARIO_G_REPLY = (
    'Olá! Queremos que o campo "Ramo" passe a se chamar "Ramo de atividade". '
    "Para atividades de alimentação, a licença sanitária em PDF deve ser anexada obrigatoriamente."
)

BASE_ISS = {
    "schema_version": 1,
    "sections": [{"id": "atividade", "label": "Atividade"}],
    "fields": [
        {"id": "ramo", "type": "select", "section_id": "atividade", "label": "Ramo", "required": True,
         "options": [{"id": "alimentacao", "label": "Alimentação"}, {"id": "comercio", "label": "Comércio"},
                     {"id": "outro", "label": "Outro"}]},
        {"id": "razao_social", "type": "text", "section_id": "atividade", "label": "Razão social", "required": True},
    ],
    "rules": [],
}


def base_schema() -> FormSchema:
    return FormSchema.model_validate(BASE_ISS)


def _at(text: str, quote: str) -> tuple[int, int]:
    i = text.index(quote)
    return i, i + len(quote)


def scenario_g_output() -> dict:
    t = SCENARIO_G_REPLY
    q1 = 'o campo "Ramo" passe a se chamar "Ramo de atividade"'
    q2 = "Para atividades de alimentação, a licença sanitária em PDF deve ser anexada obrigatoriamente"
    s1, e1 = _at(t, q1)
    s2, e2 = _at(t, q2)
    common = dict(clarity="clear", feasibility="supported", risk="low", next_action="propose_change")
    return {
        "schema_version": 1,
        "change_requests": {"action_type": "propose_change_requests", "requests": [
            {"summary": 'Renomear o campo "Ramo" para "Ramo de atividade"',
             "citation": {"source": "ticket_initial_reply", "start": s1, "end": e1, "quote": q1}, **common},
            {"summary": "Exigir licença sanitária em PDF quando o ramo for Alimentação",
             "citation": {"source": "ticket_initial_reply", "start": s2, "end": e2, "quote": q2}, **common},
        ]},
        "change_set": {"action_type": "propose_change_set",
                       "rationale": "Dois pedidos claros e suportados pelo catálogo: rótulo e anexo condicional.",
                       "operations": [
                           {"operation": {"op": "rename_label", "field_id": "ramo", "label": "Ramo de atividade"},
                            "citation_indexes": [0]},
                           {"operation": {"op": "add_conditional_attachment", "rule_id": "exigir_licenca",
                                          "field": {"id": "licenca", "section_id": "atividade", "type": "attachment",
                                                    "label": "Licença sanitária",
                                                    "accepted_formats": ["application/pdf"]},
                                          "when": {"op": "eq", "field_id": "ramo", "value": "alimentacao"}},
                            "citation_indexes": [1]},
                       ],
                       "tests": [
                           {"name": "01 alimentação com licença", "kind": "positivo",
                            "inputs": {"ramo": "alimentacao", "razao_social": "Padaria Sol", "licenca": "lic.pdf"},
                            "expected_codes": [], "requirement": "Alimentação com licença é aceita"},
                           {"name": "02 alimentação sem licença", "kind": "negativo",
                            "inputs": {"ramo": "alimentacao", "razao_social": "Padaria Sol"},
                            "expected_codes": ["REGRA_exigir_licenca"],
                            "requirement": "Licença é obrigatória para alimentação"},
                           {"name": "03 outro ramo sem licença", "kind": "limite",
                            "inputs": {"ramo": "outro", "razao_social": "Oficina Lima"},
                            "expected_codes": [], "requirement": "Licença não é exigida fora de alimentação"},
                       ]},
    }


def register_all() -> None:
    replay.register("scenario-G-v1", replay.AnalysisInput(SCENARIO_G_REPLY, schema_hash(base_schema())),
                    scenario_g_output())
