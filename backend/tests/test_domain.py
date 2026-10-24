import pytest

from app.domain.changeset import (
    AddConditionalAttachment,
    ChangeSetError,
    NewField,
    RenameLabel,
    SetOptions,
    apply_operations,
    diff_schemas,
    operation_sources_ok,
)
from app.domain.forms import (
    Compare,
    Exists,
    FormSchema,
    In,
    Not,
    canonical_bytes,
    eval_condition,
    schema_hash,
    validate_input,
    validate_schema,
)
from app.domain.states import CaseState as S, InvalidTransition, all_edges, transition

BASE = FormSchema.model_validate(
    {
        "schema_version": 1,
        "sections": [{"id": "atividade", "label": "Atividade"}],
        "fields": [
            {
                "id": "ramo", "type": "select", "section_id": "atividade", "label": "Ramo",
                "required": True,
                "options": [{"id": "alimentacao", "label": "Alimentação"}, {"id": "outro", "label": "Outro"}],
            },
            {"id": "area", "type": "number", "section_id": "atividade", "label": "Área"},
        ],
        "rules": [],
    }
)

LICENCA = NewField(id="licenca", section_id="atividade", type="attachment", label="Licença sanitária",
                   accepted_formats=["application/pdf"])


def candidate():
    op = AddConditionalAttachment(
        field=LICENCA, rule_id="exigir_licenca",
        when=Compare(op="eq", field_id="ramo", value="alimentacao"), evidence_ids=["ev1"],
    )
    return apply_operations(BASE, [op])


def test_ausente_e_falso_inclusive_neq_e_exists():
    assert eval_condition(Compare(op="neq", field_id="ramo", value="x"), {}) is False
    assert eval_condition(Exists(field_id="ramo"), {}) is False
    assert eval_condition(Not(arg=Compare(op="eq", field_id="ramo", value="x")), {}) is True


def test_sem_coercao_texto_numero():
    assert eval_condition(Compare(op="eq", field_id="area", value=10), {"area": "10"}) is False
    assert eval_condition(Compare(op="gte", field_id="area", value=10), {"area": 10.0}) is True


def test_in_e_outro_campo():
    assert eval_condition(In(field_id="ramo", values=["a", "b"]), {"ramo": "b"})
    c = Compare(op="gt", field_id="area", other_field_id="min")
    assert eval_condition(c, {"area": 5, "min": 3}) and not eval_condition(c, {"area": 5})


def test_compare_exige_um_operando():
    with pytest.raises(ValueError):
        Compare(op="eq", field_id="a", value=1, other_field_id="b")
    with pytest.raises(ValueError):
        Compare(op="eq", field_id="a")


def test_regra_exige_licenca_positivo_negativo_limite():
    s = candidate()
    assert not validate_schema(s)
    assert validate_input(s, {"ramo": "outro"}) == []
    msgs = validate_input(s, {"ramo": "alimentacao"})
    assert [i.field_id for i in msgs] == ["licenca"]
    assert validate_input(s, {"ramo": "alimentacao", "licenca": "arquivo.pdf"}) == []


def test_obrigatorio_incondicional_continua():
    assert [i.code for i in validate_input(BASE, {})] == ["OBRIGATORIO"]


def test_base_nao_e_alterada_e_nao_aplica_parcial():
    h = schema_hash(BASE)
    ok = RenameLabel(field_id="ramo", label="Ramo de atividade", evidence_ids=["e"])
    bad = RenameLabel(field_id="nao_existe", label="x", evidence_ids=["e"])
    with pytest.raises(ChangeSetError):
        apply_operations(BASE, [ok, bad])
    assert schema_hash(BASE) == h


def test_remover_opcao_referenciada_bloqueia():
    s = candidate()
    op = SetOptions(field_id="ramo", options=[{"id": "outro", "label": "Outro"}], evidence_ids=["e"])
    with pytest.raises(ChangeSetError):
        apply_operations(s, [op])


def test_hash_canonico_estavel_e_sensivel():
    a, b = candidate(), candidate()
    assert schema_hash(a) == schema_hash(b)
    assert canonical_bytes(a) == canonical_bytes(b)
    c = apply_operations(a, [RenameLabel(field_id="ramo", label="Outro rótulo", evidence_ids=["e"])])
    assert schema_hash(a) != schema_hash(c)


def test_operacao_sem_fonte_e_reportada():
    op = RenameLabel(field_id="ramo", label="x")
    assert operation_sources_ok([op])


def test_diff_lista_campo_e_regra():
    kinds = {d["kind"] for d in diff_schemas(BASE, candidate())}
    assert kinds == {"campo_adicionado", "regra_adicionada"}


def test_transicao_invalida_sem_efeito():
    with pytest.raises(InvalidTransition):
        transition(S.INTAKE, "apply_receipt")
    assert transition(S.WAITING_IMPLANTER_APPROVAL, "implanter_approved") == S.APPLYING


def test_toda_aresta_tem_destino_conhecido():
    for origem, ev, dest in all_edges():
        assert transition(origem, ev) == dest


def test_completed_nao_tem_saida():
    assert not [e for (o, e, _) in all_edges() if o == S.COMPLETED]
