"""Visão do Portal da prefeitura: linguagem simples, sem jargão interno (adendo v2.1 §5)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.forms import (
    And, Compare, Exists, FormSchema, In, Not, Or, Require, validate_input,
)
from ..persistence.models import (
    Actor, Approval, ChangeSet, FormVersion, Municipality, ProcessDefinition, Secretariat, ValidationCase,
)
from .cases import load_schema
from .changes import build_diff, suite_cases
from .common import AppError, has_role
from .views import deadline_dto, municipality_dto, state_axis

OPS = {"eq": "for", "neq": "não for", "gt": "for maior que", "gte": "for maior ou igual a",
       "lt": "for menor que", "lte": "for menor ou igual a"}


def _label(schema: FormSchema, fid: str) -> str:
    f = schema.field(fid)
    return f.label if f else fid


def _value_label(schema: FormSchema, fid: str, value) -> str:
    f = schema.field(fid)
    if f is not None and f.type == "select":
        for o in f.options:
            if o.id == value:
                return o.label
    return str(value)


def describe_condition(c, schema: FormSchema) -> str:
    if isinstance(c, And):
        return " e ".join(describe_condition(a, schema) for a in c.args)
    if isinstance(c, Or):
        return " ou ".join(describe_condition(a, schema) for a in c.args)
    if isinstance(c, Not):
        return f"não ({describe_condition(c.arg, schema)})"
    if isinstance(c, Exists):
        return f"“{_label(schema, c.field_id)}” estiver preenchido"
    if isinstance(c, In):
        vals = ", ".join(_value_label(schema, c.field_id, v) for v in c.values)
        return f"“{_label(schema, c.field_id)}” for um destes: {vals}"
    right = (f"“{_label(schema, c.other_field_id)}”" if c.other_field_id
             else _value_label(schema, c.field_id, c.value))
    return f"“{_label(schema, c.field_id)}” {OPS[c.op]} {right}"


def friendly_changes(base: FormSchema, cand: FormSchema, diff: list[dict]) -> list[dict]:
    out = []
    for d in diff:
        if d["kind"] == "campo_alterado" and d["attr"] == "label":
            out.append({"kind": "rotulo", "text": f"O campo “{d['before']}” passa a se chamar “{d['after']}”.",
                        "before": d["before"], "after": d["after"]})
        elif d["kind"] == "campo_alterado" and d["attr"] == "required":
            out.append({"kind": "obrigatorio", "text": f"O campo “{d['label']}” passa a ser "
                        f"{'obrigatório' if d['after'] else 'opcional'}."})
        elif d["kind"] == "campo_alterado" and d["attr"] == "help_text":
            out.append({"kind": "ajuda", "text": f"O texto de ajuda de “{d['label']}” foi alterado."})
        elif d["kind"] == "campo_adicionado":
            tipo = {"attachment": "anexo", "text": "texto", "number": "número", "select": "lista"}[d["after"]["type"]]
            out.append({"kind": "campo_novo", "text": f"Novo campo: “{d['label']}” ({tipo})."})
        elif d["kind"] == "regra_adicionada":
            r = next(r for r in cand.rules if r.id == d["rule_id"])
            when = describe_condition(r.when, cand)
            if isinstance(r.effect, Require):
                out.append({"kind": "regra", "text": f"Quando {when}, “{_label(cand, r.effect.field_id)}” passa a ser obrigatório."})
            else:
                out.append({"kind": "regra", "text": f"Quando {when}, o sistema mostra: {r.effect.message}"})
        elif d["kind"] == "campo_alterado":
            out.append({"kind": "outro", "text": f"“{d['label']}”: {d['attr']} foi alterado."})
    return out


def friendly_examples(s: Session, cs: ChangeSet, cand: FormSchema) -> list[dict]:
    ex = []
    for c in suite_cases(s, cs.id):
        parts = []
        for fid, v in c.inputs.items():
            f = cand.field(fid)
            if f is None or f.type == "text":
                continue
            parts.append(f"{_label(cand, fid)}: {'(arquivo anexado)' if f.type == 'attachment' else _value_label(cand, fid, v)}")
        issues = validate_input(cand, c.inputs)
        result = "O formulário é aceito." if not issues else "O sistema avisa: " + "; ".join(i.message for i in issues)
        ex.append({"title": c.name.split(" ", 1)[-1], "when": "; ".join(parts) or "Dados básicos preenchidos",
                   "result": result})
    return ex


def approval_view(s: Session, cs: ChangeSet, actor: Actor) -> dict:
    if actor.municipality_id != cs.municipality_id:
        raise AppError("NOT_FOUND", "recurso fora do escopo", 404)
    process = s.get(ProcessDefinition, cs.process_id)
    case = s.get(ValidationCase, cs.case_id)
    base = load_schema(s.get(FormVersion, cs.base_version_id))
    cand = FormSchema.model_validate_json(cs.candidate_content)
    m = s.get(Municipality, cs.municipality_id)
    sec = s.get(Secretariat, process.secretariat_id) if process.secretariat_id else None
    mine = [a for a in s.scalars(select(Approval).where(Approval.change_set_id == cs.id,
                                                       Approval.approver_role == "municipal"))]
    return {
        "change_set_id": cs.id, "municipality": municipality_dto(m), "secretariat": sec.name if sec else None,
        "process": {"code": process.code, "name": process.name},
        "version_label": cs.candidate_hash[:8], "case_version": case.version,
        "can_decide": case.state == "WAITING_MUNICIPAL_APPROVAL" and has_role(s, actor, "municipal_approver", process),
        "case_state": case.state, "changes": friendly_changes(base, cand, build_diff(s, cs)),
        "examples": friendly_examples(s, cs, cand),
        "why": "Você é a pessoa que responde por este processo. Nada é publicado sem a sua aprovação.",
        "decided": [{"decision": a.decision, "at": a.created_at.isoformat(), "valid": a.invalidated_at is None}
                    for a in mine],
        "deadline": deadline_dto(process.due_date),
    }


def home(s: Session, actor: Actor) -> dict:
    m = s.get(Municipality, actor.municipality_id)
    sec = s.get(Secretariat, actor.secretariat_id) if actor.secretariat_id else None
    todo, waiting, done = [], [], []
    for c in s.scalars(select(ValidationCase).where(ValidationCase.municipality_id == actor.municipality_id)):
        p = s.get(ProcessDefinition, c.process_id)
        if not has_role(s, actor, "municipal_approver", p) and not has_role(s, actor, "responder", p):
            continue
        cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == c.id).order_by(ChangeSet.created_at.desc()))
        item = {"case_id": c.id, "process": {"code": p.code, "name": p.name},
                "deadline": deadline_dto(p.due_date, done=c.state == "COMPLETED"), "state": c.state,
                "change_set_id": cs.id if cs else None}
        if c.state in ("WAITING_ANY_CHANNEL", "WAITING_PRIMARY_CHANNEL"):
            continue  # as perguntas abertas já aparecem em "Seu próximo passo" e "Para hoje"
        if c.state == "WAITING_MUNICIPAL_APPROVAL" and has_role(s, actor, "municipal_approver", p):
            item |= {"kind": "approval", "title": f"Aprovar a alteração de {p.code} · {p.name}",
                     "why": "Sem a sua aprovação a alteração não pode ser publicada."}
            todo.append(item)
        elif c.state == "COMPLETED":
            item |= {"kind": "done", "title": f"{p.code} · {p.name}", "why": "Alteração publicada e conferida."}
            done.append(item)
        else:
            item |= {"kind": "waiting", "title": f"{p.code} · {p.name}",
                     "why": "A equipe da Aprova está cuidando desta etapa; você será avisado se precisarmos de algo."}
            waiting.append(item)
    from .flow_views import portal_items
    questions = portal_items(s, actor)
    q_items = [{"case_id": q["case_id"], "process": q["process"], "deadline": q["deadline"], "state": "QUESTION",
                "change_set_id": None, "kind": "question", "item_id": q["id"],
                "title": q["question"], "why": q["why"]} for q in questions]
    todo = q_items + todo
    next_step = todo[0] if todo else None
    return {"municipality": municipality_dto(m), "person": {"id": actor.id, "name": actor.name},
            "secretariat": sec.name if sec else None, "next_step": next_step, "today": todo,
            "waiting": waiting, "done": done}
