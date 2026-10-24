"""Catálogo de operações e aplicação atômica de um ChangeSet (plano v2 §6.2).

Aplica em ordem sobre uma cópia da base, valida o resultado inteiro e só então
devolve a candidata. Nunca há aplicação parcial.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from .forms import (
    AttachmentField,
    Condition,
    Effect,
    FormSchema,
    NumberField,
    Option,
    Reject,
    Require,
    Rule,
    Section,
    SelectField,
    StrictModel,
    TextField,
    condition_refs,
    validate_schema,
)


class OpBase(StrictModel):
    evidence_ids: list[str] = Field(default_factory=list)
    human_decision_id: str | None = None


class RenameLabel(OpBase):
    op: Literal["rename_label"] = "rename_label"
    field_id: str
    label: str


class SetHelp(OpBase):
    op: Literal["set_help"] = "set_help"
    field_id: str
    help_text: str


class NewField(StrictModel):
    id: str
    section_id: str
    type: Literal["text", "number", "select", "attachment"]
    label: str
    help_text: str = ""
    required: bool = False
    options: list[Option] = Field(default_factory=list)
    accepted_formats: list[str] = Field(default_factory=list)
    max_size_bytes: int = 10 * 1024 * 1024


class AddField(OpBase):
    op: Literal["add_field"] = "add_field"
    field: NewField


class SetOptions(OpBase):
    op: Literal["set_options"] = "set_options"
    field_id: str
    options: list[Option]


class SetRequired(OpBase):
    op: Literal["set_required"] = "set_required"
    field_id: str
    required: bool


class AddAttachment(OpBase):
    op: Literal["add_attachment"] = "add_attachment"
    field: NewField


class AddConditionalAttachment(OpBase):
    op: Literal["add_conditional_attachment"] = "add_conditional_attachment"
    field: NewField
    rule_id: str
    when: Condition


class AddValidation(OpBase):
    op: Literal["add_validation"] = "add_validation"
    rule_id: str
    when: Condition
    effect: Effect


class DeactivateField(OpBase):
    op: Literal["deactivate_field"] = "deactivate_field"
    field_id: str


class AddSection(OpBase):
    op: Literal["add_section"] = "add_section"
    section: Section


class MoveField(OpBase):
    op: Literal["move_field"] = "move_field"
    field_id: str
    section_id: str


Operation = Annotated[
    Union[
        RenameLabel,
        SetHelp,
        AddField,
        SetOptions,
        SetRequired,
        AddAttachment,
        AddConditionalAttachment,
        AddValidation,
        DeactivateField,
        AddSection,
        MoveField,
    ],
    Field(discriminator="op"),
]


class ChangeSetError(ValueError):
    pass


CATALOG: dict[str, dict] = {
    "rename_label": {"available": True, "inputs": ["field_id", "label"], "approval": "dupla"},
    "set_help": {"available": True, "inputs": ["field_id", "help_text"], "approval": "dupla"},
    "add_field": {"available": True, "inputs": ["field"], "approval": "dupla"},
    "set_options": {"available": True, "inputs": ["field_id", "options"], "approval": "dupla"},
    "set_required": {"available": True, "inputs": ["field_id", "required"], "approval": "dupla"},
    "add_attachment": {"available": True, "inputs": ["field"], "approval": "dupla"},
    "add_conditional_attachment": {
        "available": True,
        "inputs": ["field", "rule_id", "when"],
        "approval": "dupla",
    },
    "add_validation": {"available": True, "inputs": ["rule_id", "when", "effect"], "approval": "dupla"},
    "deactivate_field": {"available": True, "inputs": ["field_id"], "approval": "dupla"},
    "add_section": {"available": True, "inputs": ["section"], "approval": "dupla"},
    "move_field": {"available": True, "inputs": ["field_id", "section_id"], "approval": "dupla"},
    "delete_field": {"available": False, "reason": "exclusão física é unsupported no simulador; use deactivate_field"},
}


def _build_field(nf: NewField):
    common = dict(
        id=nf.id, section_id=nf.section_id, label=nf.label, help_text=nf.help_text, required=nf.required
    )
    if nf.type == "text":
        return TextField(**common)
    if nf.type == "number":
        return NumberField(**common)
    if nf.type == "select":
        return SelectField(**common, options=nf.options)
    return AttachmentField(**common, accepted_formats=nf.accepted_formats, max_size_bytes=nf.max_size_bytes)


def _get(schema: FormSchema, fid: str):
    f = schema.field(fid)
    if f is None:
        raise ChangeSetError(f"campo {fid} inexistente")
    return f


def _apply_one(s: FormSchema, op) -> None:
    if isinstance(op, RenameLabel):
        _get(s, op.field_id).label = op.label
    elif isinstance(op, SetHelp):
        _get(s, op.field_id).help_text = op.help_text
    elif isinstance(op, (AddField, AddAttachment, AddConditionalAttachment)):
        if isinstance(op, (AddAttachment, AddConditionalAttachment)) and op.field.type != "attachment":
            raise ChangeSetError("anexo exige field.type=attachment")
        if s.field(op.field.id) is not None:
            raise ChangeSetError(f"campo {op.field.id} já existe")
        s.fields.append(_build_field(op.field))
        if isinstance(op, AddConditionalAttachment):
            s.rules.append(Rule(id=op.rule_id, when=op.when, effect=Require(field_id=op.field.id)))
    elif isinstance(op, SetOptions):
        f = _get(s, op.field_id)
        if not isinstance(f, SelectField):
            raise ChangeSetError(f"campo {op.field_id} não é select")
        removed = {o.id for o in f.options} - {o.id for o in op.options}
        for r in s.rules:
            used = _literal_option_uses(r, op.field_id)
            if used & removed:
                raise ChangeSetError(f"opção referenciada pela regra {r.id} não pode ser removida")
        f.options = op.options
    elif isinstance(op, SetRequired):
        _get(s, op.field_id).required = op.required
    elif isinstance(op, AddValidation):
        s.rules.append(Rule(id=op.rule_id, when=op.when, effect=op.effect))
    elif isinstance(op, DeactivateField):
        f = _get(s, op.field_id)
        for r in s.rules:
            refs = condition_refs(r.when)
            if isinstance(r.effect, Require):
                refs.add(r.effect.field_id)
            if op.field_id in refs:
                raise ChangeSetError(f"campo {op.field_id} referenciado pela regra {r.id}")
        f.active = False
    elif isinstance(op, AddSection):
        s.sections.append(op.section)
    elif isinstance(op, MoveField):
        _get(s, op.field_id).section_id = op.section_id


def _literal_option_uses(rule: Rule, field_id: str) -> set[str]:
    out: set[str] = set()

    def walk(c) -> None:
        if hasattr(c, "args"):
            for a in c.args:
                walk(a)
        elif hasattr(c, "arg"):
            walk(c.arg)
        elif getattr(c, "field_id", None) == field_id:
            if hasattr(c, "values"):
                out.update(v for v in c.values if isinstance(v, str))
            elif isinstance(getattr(c, "value", None), str):
                out.add(c.value)

    walk(rule.when)
    return out


def apply_operations(base: FormSchema, operations: list) -> FormSchema:
    """Devolve a candidata ou levanta ChangeSetError; a base nunca é alterada."""
    candidate = base.model_copy(deep=True)
    for i, op in enumerate(operations):
        try:
            _apply_one(candidate, op)
        except ChangeSetError as e:
            raise ChangeSetError(f"operação {i + 1} ({op.op}): {e}") from e
    # revalida o resultado inteiro (força checagem de tipos pydantic)
    candidate = FormSchema.model_validate(candidate.model_dump())
    errors = validate_schema(candidate)
    if errors:
        raise ChangeSetError("; ".join(errors))
    return candidate


def operation_sources_ok(operations: list) -> list[str]:
    """Cada operação precisa de fonte (evidence_ids ou human_decision_id)."""
    return [
        f"operação {i + 1} ({op.op}) sem fonte"
        for i, op in enumerate(operations)
        if not op.evidence_ids and not op.human_decision_id
    ]


def diff_schemas(base: FormSchema, cand: FormSchema) -> list[dict]:
    """Diff legível, por campo e por regra, para UI e Portal."""
    out: list[dict] = []
    b = {f.id: f for f in base.fields}
    c = {f.id: f for f in cand.fields}
    for fid, f in c.items():
        if fid not in b:
            out.append({"kind": "campo_adicionado", "field_id": fid, "label": f.label, "after": f.model_dump(mode="json")})
            continue
        before, after = b[fid].model_dump(mode="json"), f.model_dump(mode="json")
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                out.append(
                    {"kind": "campo_alterado", "field_id": fid, "label": f.label, "attr": key,
                     "before": before.get(key), "after": after.get(key)}
                )
    br = {r.id: r for r in base.rules}
    for r in cand.rules:
        if r.id not in br:
            out.append({"kind": "regra_adicionada", "rule_id": r.id, "after": r.model_dump(mode="json")})
        elif br[r.id] != r:
            out.append({"kind": "regra_alterada", "rule_id": r.id,
                        "before": br[r.id].model_dump(mode="json"), "after": r.model_dump(mode="json")})
    cr = {r.id for r in cand.rules}
    for rid in br:
        if rid not in cr:
            out.append({"kind": "regra_removida", "rule_id": rid})
    return out
