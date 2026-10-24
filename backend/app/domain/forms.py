"""Schema de formulário, avaliador de condições e hash canônico (plano v2 §6 e §7.1).

Sem I/O: este módulo não importa FastAPI, SQLAlchemy nem SDK de LLM.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_FIELDS = 100
MAX_RULES = 50
MAX_DEPTH = 8
MAX_NODES = 100


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- campos


class Section(StrictModel):
    id: str
    label: str


class Option(StrictModel):
    id: str
    label: str


class FieldBase(StrictModel):
    id: str
    section_id: str
    label: str
    help_text: str = ""
    required: bool = False
    active: bool = True


class TextField(FieldBase):
    type: Literal["text"] = "text"


class NumberField(FieldBase):
    type: Literal["number"] = "number"


class SelectField(FieldBase):
    type: Literal["select"] = "select"
    options: list[Option]


class AttachmentField(FieldBase):
    type: Literal["attachment"] = "attachment"
    accepted_formats: list[str] = Field(default_factory=list)
    max_size_bytes: int = 10 * 1024 * 1024


FormField = Annotated[
    Union[TextField, NumberField, SelectField, AttachmentField],
    Field(discriminator="type"),
]


# ------------------------------------------------------------- condições

Literal_ = Union[str, int, float, bool]


class Compare(StrictModel):
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte"]
    field_id: str
    value: Literal_ | None = None
    other_field_id: str | None = None

    @model_validator(mode="after")
    def _um_operando(self) -> "Compare":
        if (self.value is None) == (self.other_field_id is None):
            raise ValueError("informe value ou other_field_id, nunca ambos")
        return self


class In(StrictModel):
    op: Literal["in"] = "in"
    field_id: str
    values: list[Literal_] = Field(min_length=1)


class Exists(StrictModel):
    op: Literal["exists"] = "exists"
    field_id: str


class And(StrictModel):
    op: Literal["and"] = "and"
    args: list["Condition"] = Field(min_length=1)


class Or(StrictModel):
    op: Literal["or"] = "or"
    args: list["Condition"] = Field(min_length=1)


class Not(StrictModel):
    op: Literal["not"] = "not"
    arg: "Condition"


Condition = Annotated[
    Union[Compare, In, Exists, And, Or, Not], Field(discriminator="op")
]
And.model_rebuild()
Or.model_rebuild()
Not.model_rebuild()


class Require(StrictModel):
    op: Literal["require"] = "require"
    field_id: str


class Reject(StrictModel):
    op: Literal["reject"] = "reject"
    code: str
    message: str


Effect = Annotated[Union[Require, Reject], Field(discriminator="op")]


class Rule(StrictModel):
    id: str
    when: Condition
    effect: Effect


class FormSchema(StrictModel):
    schema_version: Literal[1] = 1
    sections: list[Section] = Field(default_factory=list)
    fields: list[FormField] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)

    def field(self, field_id: str) -> FormField | None:
        return next((f for f in self.fields if f.id == field_id), None)


# ------------------------------------------------------------ validação


def condition_refs(cond: Any) -> set[str]:
    """IDs de campo referenciados por uma condição."""
    if isinstance(cond, (And, Or)):
        return set().union(*(condition_refs(a) for a in cond.args))
    if isinstance(cond, Not):
        return condition_refs(cond.arg)
    refs = {cond.field_id}
    other = getattr(cond, "other_field_id", None)
    if other:
        refs.add(other)
    return refs


def _depth_nodes(cond: Any) -> tuple[int, int]:
    if isinstance(cond, (And, Or)):
        subs = [_depth_nodes(a) for a in cond.args]
        return 1 + max(d for d, _ in subs), 1 + sum(n for _, n in subs)
    if isinstance(cond, Not):
        d, n = _depth_nodes(cond.arg)
        return 1 + d, 1 + n
    return 1, 1


def validate_schema(schema: FormSchema) -> list[str]:
    """Erros de integridade do schema inteiro; lista vazia significa válido."""
    errors: list[str] = []
    if len(schema.fields) > MAX_FIELDS:
        errors.append(f"mais de {MAX_FIELDS} campos")
    if len(schema.rules) > MAX_RULES:
        errors.append(f"mais de {MAX_RULES} regras")
    section_ids = [s.id for s in schema.sections]
    if len(set(section_ids)) != len(section_ids):
        errors.append("IDs de seção duplicados")
    field_ids = [f.id for f in schema.fields]
    if len(set(field_ids)) != len(field_ids):
        errors.append("IDs de campo duplicados")
    rule_ids = [r.id for r in schema.rules]
    if len(set(rule_ids)) != len(rule_ids):
        errors.append("IDs de regra duplicados")
    for f in schema.fields:
        if f.section_id not in section_ids:
            errors.append(f"campo {f.id}: seção {f.section_id} inexistente")
        if isinstance(f, SelectField):
            oids = [o.id for o in f.options]
            if len(set(oids)) != len(oids):
                errors.append(f"campo {f.id}: opções duplicadas")
    by_id = {f.id: f for f in schema.fields}
    for r in schema.rules:
        depth, nodes = _depth_nodes(r.when)
        if depth > MAX_DEPTH or nodes > MAX_NODES:
            errors.append(f"regra {r.id}: condição excede limites")
        refs = condition_refs(r.when)
        if isinstance(r.effect, Require):
            refs.add(r.effect.field_id)
        for ref in refs:
            f = by_id.get(ref)
            if f is None:
                errors.append(f"regra {r.id}: campo {ref} inexistente")
            elif not f.active:
                errors.append(f"regra {r.id}: campo {ref} inativo")
        errors.extend(_type_errors(r, by_id))
    return errors


def _type_errors(rule: Rule, by_id: dict[str, Any]) -> list[str]:
    errs: list[str] = []

    def walk(c: Any) -> None:
        if isinstance(c, (And, Or)):
            for a in c.args:
                walk(a)
            return
        if isinstance(c, Not):
            walk(c.arg)
            return
        f = by_id.get(c.field_id)
        if f is None or isinstance(c, Exists):
            return
        if isinstance(c, In):
            for v in c.values:
                _check_literal(rule.id, f, v, errs)
        elif isinstance(c, Compare) and c.value is not None:
            _check_literal(rule.id, f, c.value, errs)
            if c.op in {"gt", "gte", "lt", "lte"} and f.type != "number":
                errs.append(f"regra {rule.id}: {c.op} exige campo numérico")

    walk(rule.when)
    return errs


def _check_literal(rule_id: str, f: Any, v: Any, errs: list[str]) -> None:
    if f.type == "number":
        ok = isinstance(v, (int, float)) and not isinstance(v, bool)
    elif f.type == "text":
        ok = isinstance(v, str)
    elif f.type == "select":
        ok = isinstance(v, str) and v in {o.id for o in f.options}
    else:
        ok = False  # anexo não é comparável
    if not ok:
        errs.append(f"regra {rule_id}: valor {v!r} incompatível com campo {f.id}")


# ------------------------------------------------------------ avaliação


def _present(values: dict[str, Any], fid: str) -> bool:
    return values.get(fid) is not None and values.get(fid) != ""


def eval_condition(cond: Any, values: dict[str, Any]) -> bool:
    """Ausente ou nulo produz falso nas comparações (inclusive neq) e em exists."""
    if isinstance(cond, And):
        return all(eval_condition(a, values) for a in cond.args)
    if isinstance(cond, Or):
        return any(eval_condition(a, values) for a in cond.args)
    if isinstance(cond, Not):
        return not eval_condition(cond.arg, values)
    if isinstance(cond, Exists):
        return _present(values, cond.field_id)
    if not _present(values, cond.field_id):
        return False
    left = values[cond.field_id]
    if isinstance(cond, In):
        return left in cond.values
    if cond.other_field_id is not None:
        if not _present(values, cond.other_field_id):
            return False
        right = values[cond.other_field_id]
    else:
        right = cond.value
    if type(left) is not type(right) and not (
        isinstance(left, (int, float))
        and isinstance(right, (int, float))
        and not isinstance(left, bool)
        and not isinstance(right, bool)
    ):
        return False  # sem coerção texto/número
    return {
        "eq": lambda: left == right,
        "neq": lambda: left != right,
        "gt": lambda: left > right,
        "gte": lambda: left >= right,
        "lt": lambda: left < right,
        "lte": lambda: left <= right,
    }[cond.op]()


class ValidationIssue(StrictModel):
    code: str
    field_id: str | None = None
    message: str


def validate_input(schema: FormSchema, values: dict[str, Any]) -> list[ValidationIssue]:
    """Aplica obrigatórios e regras; usado no preview, nos testes e após aplicar."""
    issues: list[ValidationIssue] = []
    active = {f.id: f for f in schema.fields if f.active}
    for fid in values:
        if fid not in active:
            issues.append(
                ValidationIssue(code="CAMPO_INATIVO", field_id=fid, message="campo inexistente ou inativo")
            )
    for f in active.values():
        if f.required and not _present(values, f.id):
            issues.append(
                ValidationIssue(code="OBRIGATORIO", field_id=f.id, message=f"{f.label} é obrigatório")
            )
    for r in schema.rules:
        if not eval_condition(r.when, values):
            continue
        if isinstance(r.effect, Require):
            if not _present(values, r.effect.field_id):
                label = active[r.effect.field_id].label if r.effect.field_id in active else r.effect.field_id
                issues.append(
                    ValidationIssue(
                        code=f"REGRA_{r.id}", field_id=r.effect.field_id, message=f"{label} é obrigatório"
                    )
                )
        else:
            issues.append(ValidationIssue(code=r.effect.code, message=r.effect.message))
    return issues


# ------------------------------------------------------------------ hash


def _normalize(obj: Any) -> Any:
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError("número não finito")
        return int(obj) if obj.is_integer() else obj
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    return obj


def canonical_bytes(schema: FormSchema) -> bytes:
    data = _normalize(schema.model_dump(mode="json"))
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def schema_hash(schema: FormSchema) -> str:
    return hashlib.sha256(canonical_bytes(schema)).hexdigest()


def short_hash(h: str) -> str:
    return h[:8]
