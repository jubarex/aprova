"""CLI: python -m app.populate  — popula o banco local com dados de exemplo (idempotente)."""

import json

from .agent import fixtures
from .application import analysis, demo_state
from .application.seed import seed
from .config import load_settings
from .persistence.db import init_schema, make_engine, make_session_factory, tx

if __name__ == "__main__":
    st = load_settings()
    eng = make_engine(st)
    init_schema(eng)
    f = make_session_factory(eng)
    fixtures.register_all()
    analysis.STATE["adapter"] = st.ai_adapter
    with tx(f) as s:
        seed(s)
    print(json.dumps(demo_state.populate(f, st.attachment_dir), ensure_ascii=False))
