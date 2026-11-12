"""Fixtures shared by the test suites of Gentrex's commands."""

import os
import uuid

import pytest
import sqlalchemy as sa

from gentrex.load import run

# Database servers to test on besides SQLite, which needs none.
_SERVER_URLS = os.environ.get("GENTREX_TEST_DATABASE_URLS", "").split()


def _backend(url: str) -> str:
    return sa.engine.make_url(url).get_backend_name()


@pytest.fixture(params=["sqlite://", *_SERVER_URLS], ids=_backend)
def engine(request, tmp_path):
    """An engine on a database of its own, which is dropped afterwards."""
    if request.param == "sqlite://":
        yield run.make_engine(f"sqlite:///{tmp_path / 'gentrex.db'}")
        return
    admin = run.make_engine(request.param)
    name = f"test_{uuid.uuid4().hex}"
    with admin.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(sa.text(f"CREATE DATABASE {name}"))
    url = admin.url.set(database=name).render_as_string(hide_password=False)
    engine = run.make_engine(url)
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(sa.text(f"DROP DATABASE {name}"))
    admin.dispose()
