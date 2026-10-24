"""Anexos: validação, armazenamento seguro e artefatos derivados (v2 §12.2).

Arquivo incompleto nunca vira evidência. Extração de áudio/imagem é SIMULADA (sidecar) e identificada.
PDF sem extração fica guardado para revisão humana; nunca é tratado como interpretado.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..persistence.flow_models import Attachment, DerivedArtifact, HumanDecision, Message
from ..persistence.models import ValidationCase
from .common import AppError, audit
from .messaging import looks_like_injection

MAX_BYTES = 10 * 1024 * 1024
MAX_PER_MESSAGE = 5
EXT = {"txt": "text/plain", "md": "text/markdown", "json": "application/json", "pdf": "application/pdf",
       "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "wav": "audio/wav", "mp3": "audio/mpeg"}
TEXTUAL = {"txt", "md", "json"}
SIMULATED = {"png", "jpg", "jpeg", "wav", "mp3"}


def _magic_ok(ext: str, data: bytes) -> bool:
    head = data[:16]
    if ext in TEXTUAL:
        if b"\x00" in data:
            return False
        try:
            txt = data.decode("utf-8")
        except UnicodeDecodeError:
            return False
        low = txt.lstrip().lower()[:200]
        if low.startswith(("<!doctype html", "<html", "<svg", "<?xml")):
            return False
        if ext == "json":
            try:
                json.loads(txt)
            except ValueError:
                return False
        return True
    if ext == "pdf":
        return head.startswith(b"%PDF")
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == "wav":
        return head[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if ext == "mp3":
        return head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")
    return False


def validate(filename: str, data: bytes) -> str:
    name = filename or ""
    if not name or "/" in name or "\\" in name or ".." in name or "\x00" in name:
        raise AppError("UPLOAD_REJECTED", "nome de arquivo inválido", 422)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in EXT:
        raise AppError("UPLOAD_REJECTED", "tipo de arquivo não permitido (ZIP, HTML e SVG são recusados)", 422)
    if len(data) > MAX_BYTES:
        raise AppError("PAYLOAD_TOO_LARGE", "arquivo maior que 10 MiB", 413)
    if len(data) == 0:
        raise AppError("UPLOAD_REJECTED", "arquivo vazio", 422)
    if data[:2] == b"PK":
        raise AppError("UPLOAD_REJECTED", "arquivos compactados são recusados", 422)
    if not _magic_ok(ext, data):
        raise AppError("UPLOAD_REJECTED", "o conteúdo não corresponde à extensão", 422)
    return ext


def store(s: Session, att_dir: Path, case: ValidationCase, message: Message, filename: str, data: bytes,
          sidecar_text: str | None = None) -> Attachment:
    count = s.scalar(select(func.count()).select_from(Attachment).where(Attachment.message_id == message.id))
    if (count or 0) >= MAX_PER_MESSAGE:
        raise AppError("UPLOAD_REJECTED", "no máximo 5 arquivos por mensagem", 422)
    ext = validate(filename, data)
    att_dir.mkdir(parents=True, exist_ok=True)
    internal = uuid.uuid4().hex
    staging = att_dir / f".{internal}.part"
    staging.write_bytes(data)
    os.replace(staging, att_dir / internal)  # promoção atômica; nome interno aleatório fora de qualquer raiz pública
    sha = hashlib.sha256(data).hexdigest()
    att = Attachment(case_id=case.id, municipality_id=case.municipality_id, message_id=message.id,
                     filename=os.path.basename(filename), internal_name=internal, content_type=EXT[ext],
                     size=len(data), sha256=sha, status="stored")
    s.add(att)
    s.flush()
    if ext in TEXTUAL:
        text = data.decode("utf-8")
        s.add(DerivedArtifact(attachment_id=att.id, case_id=case.id, text=text, adapter="native_text",
                              simulated=False, status="ok", source_hash=sha))
        att.status = "extracted"
        flagged = looks_like_injection(text)
    elif ext in SIMULATED and sidecar_text:
        s.add(DerivedArtifact(attachment_id=att.id, case_id=case.id, text=sidecar_text,
                              adapter="simulated_sidecar", simulated=True, status="ok", source_hash=sha))
        att.status = "extracted"
        flagged = looks_like_injection(sidecar_text)
    else:
        # PDF sem extração, ou imagem/áudio sem sidecar: nunca texto vazio tratado como sucesso
        s.add(DerivedArtifact(attachment_id=att.id, case_id=case.id, text="", adapter="none", simulated=False,
                              status="unsupported", source_hash=sha))
        att.status = "needs_review"
        flagged = False
    if flagged:
        from .common import open_intervention
        art = s.scalar(select(DerivedArtifact).where(DerivedArtifact.attachment_id == att.id))
        art.status = "unsupported"  # conteúdo suspeito não vira evidência
        att.status = "needs_review"
        open_intervention(s, case, code="INSTRUCAO_SUSPEITA", urgency=1,
                          reason=f"O anexo {att.filename} contém instruções dirigidas ao sistema. Foi tratado como texto, sem efeito.",
                          needed="Revisar o anexo")
    audit(s, actor=message.actor_id or "sistema", action="attachment_stored", case=case,
          detail={"attachment_id": att.id, "status": att.status, "sha256": sha[:12], "simulated": ext in SIMULATED},
          why=f"{att.filename} guardado ({att.status})")
    return att


def review(s: Session, case: ValidationCase, att: Attachment, actor: str, relevant: bool, text: str = "") -> HumanDecision:
    """Evidência pendente só deixa de bloquear por processamento ou decisão humana fundamentada."""
    if att.case_id != case.id:
        raise AppError("NOT_FOUND", "anexo fora do escopo", 404)
    if len(text.strip()) < 3:
        raise AppError("RATIONALE_REQUIRED", "informe a justificativa da revisão", 422)
    att.status = "reviewed"
    body = (f"Revisão humana do anexo {att.filename}: " + (text if relevant else f"irrelevante para o caso. {text}"))
    hd = HumanDecision(case_id=case.id, actor_id=actor, kind="review_attachment", text=body,
                       payload={"attachment_id": att.id, "relevant": relevant}, consolidated=not relevant)
    s.add(hd)
    audit(s, actor=actor, action="attachment_reviewed", case=case, detail={"attachment_id": att.id, "relevant": relevant},
          why=text)
    return hd
