"""Seed sintético idempotente: não apaga progresso (v2 §13.2)."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent import fixtures
from ..clock import business_now
from ..persistence.models import (
    Actor, Municipality, ProcessDefinition, RoleAssignment, Secretariat,
)
from .cases import store_version

MUNICIPALITIES = [
    ("mun_vr", "Prefeitura de Vale do Ribeiro", "VR", "Vale do Ribeiro", 1),
    ("mun_sa", "Prefeitura de Serra Alta", "SA", "Serra Alta", 2),
]
SECRETARIATS = {
    "mun_vr": [("sec_vr_faz", "Secretaria de Fazenda"), ("sec_vr_obr", "Secretaria de Obras"),
               ("sec_vr_vig", "Vigilância Sanitária")],
    "mun_sa": [("sec_sa_faz", "Secretaria de Fazenda"), ("sec_sa_edu", "Secretaria de Educação")],
}
# (id, código, nome, secretaria, onda, prazo em dias)
PROCESSES = {
    "mun_vr": [("proc_vr_iss012", "ISS-012", "Alvará de funcionamento", "sec_vr_faz", 1, 5),
               ("proc_vr_iss030", "ISS-030", "Baixa de inscrição", "sec_vr_faz", 1, 2),
               ("proc_vr_obr004", "OBR-004", "Licença de obra", "sec_vr_obr", 2, 12),
               ("proc_vr_vig002", "VIG-002", "Licença sanitária", "sec_vr_vig", 2, 15)],
    "mun_sa": [("proc_sa_iss012", "ISS-012", "Alvará de funcionamento", "sec_sa_faz", 1, 6),
               ("proc_sa_edu001", "EDU-001", "Matrícula escolar", "sec_sa_edu", 2, 14)],
}
ACTORS = [
    ("act_rui", "Rui Prado (implantador)", "implantador", None, None),
    ("act_ana", "Ana Souza", "contato", "mun_vr", "sec_vr_faz"),
    ("act_joao", "João Lima", "contato", "mun_vr", "sec_vr_obr"),
    ("act_marcos", "Marcos Reis", "contato", "mun_sa", "sec_sa_faz"),
    ("act_luiza", "Luiza Prado", "contato", "mun_sa", "sec_sa_faz"),
]


FILLER_NAMES = [
    "Certidão negativa de débitos", "Parcelamento de dívida ativa", "IPTU: segunda via", "ITBI: avaliação",
    "Alvará de publicidade", "Licença ambiental simplificada", "Poda de árvore", "Coleta de entulho",
    "Habite-se", "Desmembramento de lote", "Certidão de número", "Alvará de eventos", "Feira livre: cadastro",
    "Taxa de lixo: isenção", "Transporte escolar: inscrição", "Matrícula: transferência", "Auxílio funeral",
    "Isenção de ISS para MEI", "Vistoria de bombeiros", "Licença para toldo", "Uso do solo: consulta",
    "Denúncia de obra irregular", "Ocupação de calçada", "Cemitério: concessão", "Certidão de óbito: segunda via",
    "Cadastro imobiliário", "Alteração de endereço", "Baixa de alvará", "Renovação de alvará", "Autorização de show",
]


def _filler(mid: str, secs: list[tuple[str, str]], total: int, existing: int) -> list[tuple]:
    """Processos sintéticos restantes (até `total`), distribuídos em ondas; nenhum vence nos primeiros 4 dias."""
    out = []
    n = total - existing
    for i in range(n):
        sec_id, sec_name = secs[i % len(secs)]
        code = f"{sec_id.split('_')[-1].upper()[:3]}-{100 + i:03d}"
        name = FILLER_NAMES[i % len(FILLER_NAMES)] + ("" if i < len(FILLER_NAMES) else f" ({i // len(FILLER_NAMES) + 1})")
        wave = 1 + (i * 4) // n
        due = 4 + (i * 44) // n
        out.append((f"proc_{mid.split('_')[-1]}_f{i:03d}", code, name, sec_id, wave, due))
    return out


def seed(s: Session) -> None:
    fixtures.register_all()
    now = business_now()
    for mid, name, short, city, slot in MUNICIPALITIES:
        if not s.get(Municipality, mid):
            s.add(Municipality(id=mid, name=name, short=short, city=city, color_slot=slot,
                               start_date=now - timedelta(days=10), target_date=now + timedelta(days=45)))
    s.flush()
    for mid, secs in SECRETARIATS.items():
        for sid, sname in secs:
            if not s.get(Secretariat, sid):
                s.add(Secretariat(id=sid, municipality_id=mid, name=sname))
    s.flush()
    for aid, name, kind, mid, sec in ACTORS:
        if not s.get(Actor, aid):
            s.add(Actor(id=aid, name=name, kind=kind, municipality_id=mid, secretariat_id=sec,
                        preferred_channel="whatsapp"))
    s.flush()
    for mid, procs in PROCESSES.items():
        extra = _filler(mid, SECRETARIATS[mid], 70, len(procs))
        for pid, code, pname, sec, wave, due_days in procs + extra:
            if s.get(ProcessDefinition, pid):
                continue
            p = ProcessDefinition(id=pid, municipality_id=mid, secretariat_id=sec, code=code, name=pname,
                                  wave=wave, due_date=now + timedelta(days=due_days))
            s.add(p)
            s.flush()
            v = store_version(s, p, fixtures.base_schema(), None)
            p.current_version_id = v.id
    s.flush()

    def role(actor, role_name, process=None, muni=None, topic=None):
        q = select(RoleAssignment).where(RoleAssignment.actor_id == actor, RoleAssignment.role == role_name,
                                         RoleAssignment.process_id == process, RoleAssignment.municipality_id == muni,
                                         RoleAssignment.topic == topic)
        if not s.scalar(q):
            s.add(RoleAssignment(actor_id=actor, role=role_name, process_id=process, municipality_id=muni, topic=topic))

    role("act_rui", "implanter")
    role("act_rui", "aprova_approver")
    for p in ("proc_vr_iss012", "proc_vr_iss030", "proc_vr_obr004", "proc_vr_vig002"):
        role("act_ana", "municipal_approver", p, "mun_vr")
    role("act_ana", "responder", None, "mun_vr", "fazenda")
    # João responde sobre Obras, mas NÃO aprova: capacidade de responder != aprovar
    role("act_joao", "responder", None, "mun_vr", "obras")
    for p in ("proc_sa_iss012", "proc_sa_edu001"):
        role("act_marcos", "municipal_approver", p, "mun_sa")
    role("act_marcos", "responder", None, "mun_sa", None)
    role("act_luiza", "responder", None, "mun_sa", "fazenda")
