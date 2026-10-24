"""Gravações de replay (fixtures de teste) e roteiros dos cenários. Identificadas na UI como 'IA: replay offline'.

Não são instruções de produção por formulário (v2 §2.2): cada gravação é uma saída para uma entrada
conhecida; entrada diferente resulta em REPLAY_MISS. Os roteiros (SCENARIOS) trazem os textos exatos
que reproduzem cada gravação, para a demonstração e para os testes.
"""

from __future__ import annotations

from ..domain.forms import FormSchema, schema_hash
from . import replay

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


# ------------------------------------------------------------------ helpers


def cite(texts: dict[str, str], ref: str, quote: str) -> dict:
    t = texts[ref]
    i = t.index(quote)
    return {"source_ref": ref, "start": i, "end": i + len(quote), "quote": quote}


def req(summary, idx, clarity="clear", feas="supported", risk="low", nxt="propose_change"):
    return {"summary": summary, "evidence_indexes": idx, "clarity": clarity, "feasibility": feas, "risk": risk,
            "next_action": nxt}


def gap(request_index, question, kind="text", options=None, topic="geral"):
    return {"request_index": request_index, "question": question, "answer_kind": kind,
            "options": options or [], "topic": topic, "blocking": True}


def upd(ref, status, idx, note=""):
    return {"gap_ref": ref, "status": status, "evidence_indexes": idx, "note": note}


def op(operation, idx):
    return {"operation": operation, "evidence_indexes": idx}


def test(name, kind, inputs, expected, requirement=""):
    return {"name": name, "kind": kind, "inputs": inputs, "expected_codes": expected, "requirement": requirement}


def cs(rationale, ops, tests):
    return {"rationale": rationale, "operations": ops, "tests": tests}


def gq(g: dict) -> str:
    return g["question"]


def open_tuple(gaps: list[tuple[str, str]]) -> tuple[str, ...]:
    return tuple(f"{r}:{q}" for r, q in gaps)


# ------------------------------------------------------------------ cenário G

G_REPLY = (
    'Olá! Queremos que o campo "Ramo" passe a se chamar "Ramo de atividade". '
    "Para atividades de alimentação, a licença sanitária em PDF deve ser anexada obrigatoriamente."
)
SCENARIO_G_REPLY = G_REPLY  # compatibilidade com os testes da fatia 1


def _g_output() -> dict:
    t = {"TICKET": G_REPLY}
    q1 = 'o campo "Ramo" passe a se chamar "Ramo de atividade"'
    q2 = "Para atividades de alimentação, a licença sanitária em PDF deve ser anexada obrigatoriamente"
    return {
        "stage": "initial",
        "evidence": [cite(t, "TICKET", q1), cite(t, "TICKET", q2)],
        "requests": [req('Renomear o campo "Ramo" para "Ramo de atividade"', [0]),
                     req("Exigir licença sanitária em PDF quando o ramo for Alimentação", [1])],
        "change_set": cs(
            "Dois pedidos claros e suportados pelo catálogo: rótulo e anexo condicional.",
            [op({"op": "rename_label", "field_id": "ramo", "label": "Ramo de atividade"}, [0]),
             op({"op": "add_conditional_attachment", "rule_id": "exigir_licenca",
                 "field": {"id": "licenca", "section_id": "atividade", "type": "attachment",
                           "label": "Licença sanitária", "accepted_formats": ["application/pdf"]},
                 "when": {"op": "eq", "field_id": "ramo", "value": "alimentacao"}}, [1])],
            [test("01 alimentação com licença", "positivo",
                  {"ramo": "alimentacao", "razao_social": "Padaria Sol", "licenca": "lic.pdf"}, [],
                  "Alimentação com licença é aceita"),
             test("02 alimentação sem licença", "negativo", {"ramo": "alimentacao", "razao_social": "Padaria Sol"},
                  ["REGRA_exigir_licenca"], "Licença é obrigatória para alimentação"),
             test("03 outro ramo sem licença", "limite", {"ramo": "outro", "razao_social": "Oficina Lima"}, [],
                  "Licença não é exigida fora de alimentação")]),
    }


# ------------------------------------------------------------------ cenário A (resposta confusa, delta)

A_REPLY = (
    'Pessoal, o campo "Razão social" deve se chamar "Razão social ou nome fantasia". '
    "Queremos exigir um comprovante de endereço, mas só para alguns ramos. "
    'O campo "Ramo" está confuso, ajustem. '
    "Aquele formulário antigo tinha mais campos, voltem como era. "
    "E a Secretaria de Obras precisa dizer se a baixa exige certidão de obras."
)
A_Q = {
    "G1": "Para quais ramos o comprovante de endereço deve ser obrigatório?",
    "G2": 'O que deve mudar no campo "Ramo": nome, opções ou obrigatoriedade?',
    "G3": "Quais campos do formulário antigo devem voltar?",
    "G4": "A baixa de inscrição exige certidão de obras?",
}
A_S1 = 'O comprovante de endereço é só para Alimentação e Comércio. O campo Ramo deve se chamar "Ramo de atividade".'
A_S2 = "Nenhum campo do formulário antigo precisa voltar, podem ignorar esse pedido."
A_S3 = "Para baixa de inscrição não é exigida certidão de obras."


def _a_initial() -> dict:
    t = {"TICKET": A_REPLY}
    qs = ['o campo "Razão social" deve se chamar "Razão social ou nome fantasia"',
          "Queremos exigir um comprovante de endereço, mas só para alguns ramos",
          'O campo "Ramo" está confuso, ajustem', "Aquele formulário antigo tinha mais campos, voltem como era",
          "E a Secretaria de Obras precisa dizer se a baixa exige certidão de obras"]
    return {
        "stage": "initial", "evidence": [cite(t, "TICKET", q) for q in qs],
        "requests": [
            req('Renomear "Razão social" para "Razão social ou nome fantasia"', [0]),
            req("Exigir comprovante de endereço para alguns ramos", [1], "partial", "supported_with_conditions", "low", "clarify"),
            req('Ajustar o campo "Ramo" (alteração não especificada)', [2], "ambiguous", "unknown", "low", "clarify"),
            req("Restaurar campos do formulário antigo", [3], "ambiguous", "requires_product_review", "medium", "clarify"),
            req("Confirmar exigência de certidão de obras (outro setor)", [4], "partial", "unknown", "low", "find_owner")],
        "gaps": [gap(1, A_Q["G1"], "choose_options", ["Alimentação", "Comércio", "Outro", "Todos"], "fazenda"),
                 gap(2, A_Q["G2"], "text", [], "fazenda"), gap(3, A_Q["G3"], "text", [], "fazenda"),
                 gap(4, A_Q["G4"], "yes_no", [], "obras")],
    }


def _a_after_s1() -> dict:
    t = {"S1": A_S1}
    return {"stage": "reconcile",
            "evidence": [cite(t, "S1", "só para Alimentação e Comércio"), cite(t, "S1", '"Ramo de atividade"')],
            "gap_updates": [upd("G1", "answered", [0]), upd("G2", "answered", [1])]}


def _a_after_s2() -> dict:
    t = {"S2": A_S2}
    return {"stage": "reconcile", "evidence": [cite(t, "S2", "Nenhum campo do formulário antigo precisa voltar")],
            "gap_updates": [upd("G3", "answered", [0], "Pedido retirado pelo próprio solicitante")]}


def _a_final() -> dict:
    t = {"TICKET": A_REPLY, "S1": A_S1, "S3": A_S3}
    return {
        "stage": "reconcile",
        "evidence": [cite(t, "TICKET", 'o campo "Razão social" deve se chamar "Razão social ou nome fantasia"'),
                     cite(t, "S1", "só para Alimentação e Comércio"), cite(t, "S1", '"Ramo de atividade"'),
                     cite(t, "S3", "não é exigida certidão de obras")],
        "gap_updates": [upd("G4", "answered", [3])],
        "change_set": cs(
            "Respostas completas: rótulos e comprovante condicional para Alimentação e Comércio.",
            [op({"op": "rename_label", "field_id": "razao_social", "label": "Razão social ou nome fantasia"}, [0]),
             op({"op": "rename_label", "field_id": "ramo", "label": "Ramo de atividade"}, [2]),
             op({"op": "add_conditional_attachment", "rule_id": "exigir_comprovante",
                 "field": {"id": "comprovante", "section_id": "atividade", "type": "attachment",
                           "label": "Comprovante de endereço", "accepted_formats": ["application/pdf"]},
                 "when": {"op": "in", "field_id": "ramo", "values": ["alimentacao", "comercio"]}}, [1])],
            [test("01 comércio com comprovante", "positivo",
                  {"ramo": "comercio", "razao_social": "Loja Aurora", "comprovante": "c.pdf"}, []),
             test("02 comércio sem comprovante", "negativo", {"ramo": "comercio", "razao_social": "Loja Aurora"},
                  ["REGRA_exigir_comprovante"]),
             test("03 outro ramo sem comprovante", "limite", {"ramo": "outro", "razao_social": "Oficina"}, [])]),
    }


# ------------------------------------------------------------------ cenário B (indicação de responsável)

B_REPLY = (
    'Precisamos que o campo "Razão social" se chame "Nome empresarial". '
    "Também será preciso anexar o alvará sanitário para alimentação, mas quem sabe qual documento vale é a Vigilância."
)
B_Q = {"G1": "Qual documento sanitário deve ser anexado e para quais ramos?"}
B_DOC = "Para empresas de alimentação, exigir o alvará sanitário emitido pela Vigilância, com validade de 12 meses."
B_S1 = "Segue o documento de referência da Vigilância."


def _b_initial() -> dict:
    t = {"TICKET": B_REPLY}
    qs = ['o campo "Razão social" se chame "Nome empresarial"',
          "Também será preciso anexar o alvará sanitário para alimentação, mas quem sabe qual documento vale é a Vigilância"]
    return {"stage": "initial", "evidence": [cite(t, "TICKET", q) for q in qs],
            "requests": [req('Renomear "Razão social" para "Nome empresarial"', [0]),
                         req("Anexar alvará sanitário para alimentação", [1], "partial", "supported_with_conditions",
                             "low", "find_owner")],
            "gaps": [gap(1, B_Q["G1"], "document", [], "vigilancia")]}


def _b_final() -> dict:
    t = {"TICKET": B_REPLY, "S1": B_S1, "S2": B_DOC}
    return {"stage": "reconcile",
            "evidence": [cite(t, "TICKET", 'o campo "Razão social" se chame "Nome empresarial"'),
                         cite(t, "S2", "exigir o alvará sanitário emitido pela Vigilância")],
            "gap_updates": [upd("G1", "answered", [1])],
            "change_set": cs(
                "O técnico da Vigilância confirmou o documento: alvará sanitário para alimentação.",
                [op({"op": "rename_label", "field_id": "razao_social", "label": "Nome empresarial"}, [0]),
                 op({"op": "add_conditional_attachment", "rule_id": "exigir_alvara_sanitario",
                     "field": {"id": "alvara_sanitario", "section_id": "atividade", "type": "attachment",
                               "label": "Alvará sanitário", "accepted_formats": ["application/pdf"]},
                     "when": {"op": "eq", "field_id": "ramo", "value": "alimentacao"}}, [1])],
                [test("01 alimentação com alvará", "positivo",
                      {"ramo": "alimentacao", "razao_social": "Bar Central", "alvara_sanitario": "a.pdf"}, []),
                 test("02 alimentação sem alvará", "negativo", {"ramo": "alimentacao", "razao_social": "Bar Central"},
                      ["REGRA_exigir_alvara_sanitario"]),
                 test("03 comércio sem alvará", "limite", {"ramo": "comercio", "razao_social": "Loja"}, [])])}


# ------------------------------------------------------------------ cenário C (Pylon + WhatsApp, uma consolidação)

C_REPLY = (
    'Na licença de obra, o campo "Razão social" deve se chamar "Requerente". '
    "Também precisamos exigir a ART para obras acima de certa área, mas definam com o responsável de Obras."
)
C_Q = {"G1": "A partir de quantos m² a ART deve ser obrigatória?",
       "G2": "Envie o modelo de ART aceito pela Secretaria de Obras."}
C_S1 = "A ART é obrigatória para obras acima de 100 m²."
C_S2 = "Segue o modelo da ART."
C_DOC = "Modelo de ART aceito: formulário do CREA, assinado pelo responsável técnico."


def _c_initial() -> dict:
    t = {"TICKET": C_REPLY}
    qs = ['o campo "Razão social" deve se chamar "Requerente"',
          "Também precisamos exigir a ART para obras acima de certa área, mas definam com o responsável de Obras"]
    return {"stage": "initial", "evidence": [cite(t, "TICKET", q) for q in qs],
            "requests": [req('Renomear "Razão social" para "Requerente"', [0]),
                         req("Exigir ART acima de uma área", [1], "partial", "supported_with_conditions", "low", "clarify")],
            "gaps": [gap(1, C_Q["G1"], "number", [], "obras"), gap(1, C_Q["G2"], "document", [], "obras")]}


def _c_after_pylon() -> dict:
    t = {"S1": C_S1}
    return {"stage": "reconcile", "evidence": [cite(t, "S1", "obrigatória para obras acima de 100 m²")],
            "gap_updates": [upd("G1", "answered", [0])]}


def _c_final_both() -> dict:
    t = {"TICKET": C_REPLY, "S1": C_S1, "S2": C_S2, "S3": C_DOC}
    return _c_final(t, True)


def _c_final(t: dict, with_g1: bool) -> dict:
    ev = [cite(t, "TICKET", 'o campo "Razão social" deve se chamar "Requerente"'),
          cite(t, "S1", "obrigatória para obras acima de 100 m²"), cite(t, "S3", "formulário do CREA")]
    return {"stage": "reconcile", "evidence": ev,
            "gap_updates": ([upd("G1", "answered", [1])] if with_g1 else []) + [upd("G2", "answered", [2])],
            "change_set": cs(
                "Decisão (Pylon) e documento (WhatsApp) consolidados: ART acima de 100 m².",
                [op({"op": "rename_label", "field_id": "razao_social", "label": "Requerente"}, [0]),
                 op({"op": "add_field", "field": {"id": "area_m2", "section_id": "atividade", "type": "number",
                                                  "label": "Área da obra (m²)"}}, [1]),
                 op({"op": "add_conditional_attachment", "rule_id": "exigir_art",
                     "field": {"id": "art", "section_id": "atividade", "type": "attachment", "label": "ART",
                               "accepted_formats": ["application/pdf"]},
                     "when": {"op": "gt", "field_id": "area_m2", "value": 100}}, [1, 2])],
                [test("01 acima de 100 m² com ART", "positivo",
                      {"ramo": "outro", "razao_social": "Construtora", "area_m2": 150, "art": "art.pdf"}, []),
                 test("02 acima de 100 m² sem ART", "negativo",
                      {"ramo": "outro", "razao_social": "Construtora", "area_m2": 150}, ["REGRA_exigir_art"]),
                 test("03 exatamente 100 m² sem ART", "limite",
                      {"ramo": "outro", "razao_social": "Construtora", "area_m2": 100}, [])])}


# ------------------------------------------------------------------ cenário D (conflito entre fontes)

D_REPLY = 'Queremos que o alvará exija a licença sanitária.'
D_Q = {"G1": "A licença sanitária deve ser exigida para todos os ramos ou apenas para Alimentação?"}
D_S1 = "A licença sanitária é obrigatória para todos os ramos."
D_S2 = "Na verdade é somente para Alimentação."
D_S3 = "Decisão do secretário: a licença sanitária vale somente para Alimentação."


def _d_initial() -> dict:
    t = {"TICKET": D_REPLY}
    return {"stage": "initial", "evidence": [cite(t, "TICKET", "o alvará exija a licença sanitária")],
            "requests": [req("Exigir licença sanitária no alvará", [0], "partial", "supported_with_conditions",
                             "medium", "clarify")],
            "gaps": [gap(0, D_Q["G1"], "choose_options", ["Todos os ramos", "Apenas Alimentação"], "fazenda")]}


def _d_conflict() -> dict:
    t = {"S1": D_S1, "S2": D_S2}
    return {"stage": "reconcile",
            "evidence": [cite(t, "S1", "obrigatória para todos os ramos"), cite(t, "S2", "somente para Alimentação")],
            "gap_updates": [upd("G1", "disputed", [0, 1], "Duas fontes se contradizem sobre o escopo")]}


def _d_first() -> dict:
    """Só a primeira fonte chegou: a lacuna é respondida e a candidata nasce com o escopo 'todos'."""
    t = {"TICKET": D_REPLY, "S1": D_S1}
    return {"stage": "reconcile",
            "evidence": [cite(t, "TICKET", "o alvará exija a licença sanitária"),
                         cite(t, "S1", "obrigatória para todos os ramos")],
            "gap_updates": [upd("G1", "answered", [1])],
            "change_set": cs("Resposta única recebida: licença sanitária obrigatória para todos os ramos.",
                             [op({"op": "add_attachment", "field": {"id": "licenca_sanitaria", "section_id": "atividade",
                                  "type": "attachment", "label": "Licença sanitária",
                                  "accepted_formats": ["application/pdf"]}}, [0, 1]),
                              op({"op": "set_required", "field_id": "licenca_sanitaria", "required": True}, [1])],
                             [test("01 com licença", "positivo", {"ramo": "outro", "razao_social": "Loja", "licenca_sanitaria": "l.pdf"}, []),
                              test("02 sem licença", "negativo", {"ramo": "outro", "razao_social": "Loja"}, ["OBRIGATORIO"])])}


def _d_late_conflict() -> dict:
    """Evidência contraditória chega depois: a lacuna respondida volta a ser disputada."""
    t = {"S1": D_S1, "S2": D_S2}
    return {"stage": "reconcile",
            "evidence": [cite(t, "S1", "obrigatória para todos os ramos"), cite(t, "S2", "somente para Alimentação")],
            "gap_updates": [upd("G1", "disputed", [0, 1], "Nova fonte contradiz a resposta anterior")]}


def _d_final() -> dict:
    t = {"TICKET": D_REPLY, "S3": D_S3}
    return {"stage": "reconcile",
            "evidence": [cite(t, "TICKET", "o alvará exija a licença sanitária"),
                         cite(t, "S3", "somente para Alimentação")],
            "gap_updates": [upd("G1", "answered", [1])],
            "change_set": cs("Decisão humana define o escopo: somente Alimentação.",
                             [op({"op": "add_conditional_attachment", "rule_id": "exigir_licenca_sanitaria",
                                  "field": {"id": "licenca_sanitaria", "section_id": "atividade", "type": "attachment",
                                            "label": "Licença sanitária", "accepted_formats": ["application/pdf"]},
                                  "when": {"op": "eq", "field_id": "ramo", "value": "alimentacao"}}, [0, 1])],
                             [test("01 alimentação com licença", "positivo",
                                   {"ramo": "alimentacao", "razao_social": "Cantina", "licenca_sanitaria": "l.pdf"}, []),
                              test("02 alimentação sem licença", "negativo",
                                   {"ramo": "alimentacao", "razao_social": "Cantina"},
                                   ["REGRA_exigir_licenca_sanitaria"]),
                              test("03 comércio sem licença", "limite", {"ramo": "comercio", "razao_social": "Loja"}, [])])}


# ------------------------------------------------------------------ cenário E (fora do playbook)

E_REPLY = "Qual a melhor prática para o campo de identificação do aluno? Podem recomendar o que for melhor."
E_S1 = 'Recomendado pelo implantador: renomear o campo "Razão social" para "Nome completo do aluno".'


def _e_initial() -> dict:
    t = {"TICKET": E_REPLY}
    return {"stage": "initial", "evidence": [cite(t, "TICKET", "Qual a melhor prática")],
            "requests": [req("Recomendar a melhor prática para o campo de identificação", [0], "ambiguous", "unknown",
                             "medium", "escalate")],
            "intervention": {"code": "FORA_DO_PLAYBOOK", "urgency": 2,
                             "reason": "Pedido de recomendação sem playbook aplicável: o agente não inventa uma regra.",
                             "needed_decision": "Decidir o que recomendar para o campo de identificação do aluno"}}


def _e_final() -> dict:
    t = {"TICKET": E_REPLY, "S1": E_S1}
    return {"stage": "reconcile",
            "evidence": [cite(t, "TICKET", "Qual a melhor prática"), cite(t, "S1", '"Nome completo do aluno"')],
            "change_set": cs("A decisão humana vira a evidência da alteração.",
                             [op({"op": "rename_label", "field_id": "razao_social", "label": "Nome completo do aluno"},
                                 [0, 1])],
                             [test("01 identificação preenchida", "positivo", {"ramo": "outro", "razao_social": "Ana"}, []),
                              test("02 identificação ausente", "negativo", {"ramo": "outro"}, ["OBRIGATORIO"])])}


# ------------------------------------------------------------------ registro


def register_all() -> None:
    bh = schema_hash(base_schema())

    def R(fid, reply, stage, sources, gaps, out):
        replay.register(fid, replay.AnalysisInput(reply, bh, stage, tuple(sources), open_tuple(gaps)), out)

    R("G-initial", G_REPLY, "initial", [], [], _g_output())
    allA = [(r, q) for r, q in A_Q.items()]
    R("A-initial", A_REPLY, "initial", [], [], _a_initial())
    R("A-s1", A_REPLY, "reconcile", [A_S1], allA, _a_after_s1())
    R("A-s2", A_REPLY, "reconcile", [A_S1, A_S2], [("G3", A_Q["G3"]), ("G4", A_Q["G4"])], _a_after_s2())
    R("A-final", A_REPLY, "reconcile", [A_S1, A_S2, A_S3], [("G4", A_Q["G4"])], _a_final())
    R("B-initial", B_REPLY, "initial", [], [], _b_initial())
    R("B-final", B_REPLY, "reconcile", [B_S1, B_DOC], [("G1", B_Q["G1"])], _b_final())
    R("C-initial", C_REPLY, "initial", [], [], _c_initial())
    R("C-pylon", C_REPLY, "reconcile", [C_S1], [("G1", C_Q["G1"]), ("G2", C_Q["G2"])], _c_after_pylon())
    R("C-both", C_REPLY, "reconcile", [C_S1, C_S2, C_DOC], [("G1", C_Q["G1"]), ("G2", C_Q["G2"])], _c_final_both())
    R("C-doc-after-pylon", C_REPLY, "reconcile", [C_S1, C_S2, C_DOC], [("G2", C_Q["G2"])],
      _c_final({"TICKET": C_REPLY, "S1": C_S1, "S2": C_S2, "S3": C_DOC}, False))
    R("D-initial", D_REPLY, "initial", [], [], _d_initial())
    R("D-conflict", D_REPLY, "reconcile", [D_S1, D_S2], [("G1", D_Q["G1"])], _d_conflict())
    R("D-first", D_REPLY, "reconcile", [D_S1], [("G1", D_Q["G1"])], _d_first())
    R("D-late", D_REPLY, "reconcile", [D_S1, D_S2], [], _d_late_conflict())
    R("D-final", D_REPLY, "reconcile", [D_S1, D_S2, D_S3], [("G1", D_Q["G1"])], _d_final())
    R("E-initial", E_REPLY, "initial", [], [], _e_initial())
    R("E-final", E_REPLY, "reconcile", [E_S1], [], _e_final())
