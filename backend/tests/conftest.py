import pytest

from app.agent import replay
from app.application import changes
from app.application.seed import seed
from app.config import Settings
from app.persistence.db import init_schema, make_engine, make_session_factory, tx


@pytest.fixture()
def env(tmp_path):
    replay.clear()
    changes.FAULTS.clear()
    settings = Settings("demo", "offline_replay", f"sqlite:///{(tmp_path / 't.db').as_posix()}",
                        tmp_path / "att")
    engine = make_engine(settings)
    init_schema(engine)
    factory = make_session_factory(engine)
    with tx(factory) as s:
        seed(s)
    yield factory
    engine.dispose()
