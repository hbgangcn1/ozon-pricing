# -*- coding: utf-8 -*-
"""
根目录的pytest配置文件
用于排除非测试文件 + pytest-xdist worker schema 隔离
"""

import asyncio
import gc
import os
import sys
import types
import weakref
from pathlib import Path

import pytest

os.environ["E2E_TEST"] = "1"
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-do-not-use-in-production")


# D13 v2 (Oracle option g): Reuse pytest-asyncio session loop instead of
# minting a new one when Python 3.13 reports "no current event loop". A new
# loop would orphan asyncpg Futures bound to the original session loop and
# cause "attached to a different loop" errors during fixture teardown.
_PYTEST_ASYNCIO_LOOP_REFS: list = []


def _is_alive_pytest_asyncio_loop(loop: object) -> bool:
    return (
        isinstance(loop, asyncio.AbstractEventLoop)
        and getattr(loop, "__pytest_asyncio", False)
        and not loop.is_closed()
    )


def _remember_pytest_asyncio_loop(loop: object) -> object:
    if _is_alive_pytest_asyncio_loop(loop):
        _PYTEST_ASYNCIO_LOOP_REFS.append(weakref.ref(loop))
    return loop


def _select_pytest_asyncio_loop():
    seen_ids: set = set()

    for loop_ref in reversed(_PYTEST_ASYNCIO_LOOP_REFS):
        loop = loop_ref()
        if loop is None:
            continue
        loop_id = id(loop)
        if loop_id in seen_ids:
            continue
        seen_ids.add(loop_id)
        if _is_alive_pytest_asyncio_loop(loop):
            return loop

    for obj in gc.get_objects():
        obj_id = id(obj)
        if obj_id in seen_ids:
            continue
        seen_ids.add(obj_id)
        if _is_alive_pytest_asyncio_loop(obj):
            _remember_pytest_asyncio_loop(obj)
            return obj

    return None


def _rebind_pytest_asyncio_loop(policy=None):
    loop = _select_pytest_asyncio_loop()
    if loop is None:
        return None
    loop_policy = policy or asyncio.get_event_loop_policy()
    loop_policy.set_event_loop(loop)
    return loop


def _install_pytest_asyncio_py313_loop_fallback() -> None:
    """D13 v2: Compat shim for pytest-asyncio 0.26 on Python 3.13.

    On Python 3.13 ``asyncio.get_event_loop()`` raises when the policy's
    per-thread slot is None instead of auto-creating. This breaks
    pytest-asyncio's ``_get_event_loop_no_warn`` between tests when
    ``_provide_clean_event_loop`` momentarily unbinds the session loop.

    D13 v1 created a brand-new loop on RuntimeError but that left in-flight
    asyncpg Futures bound to the original session loop, raising
    "attached to a different loop" during async fixture teardown.

    D13 v2 instead REUSES the existing pytest-asyncio-tagged session loop
    (recorded via the autouse fixture below + GC fallback), and only mints
    a new loop as a last resort. We also wrap ``_provide_clean_event_loop``
    so it re-binds the session loop after each per-test cleanup, making the
    RuntimeError path rare.
    """
    try:
        import pytest_asyncio.plugin as pap
    except ImportError:
        return

    if getattr(pap, "_py313_loop_fallback_installed", False):
        return

    original_get_loop = getattr(pap, "_get_event_loop_no_warn", None)
    if original_get_loop is None:
        # pytest-asyncio dropped this private API; shim no longer applicable.
        # Mark installed so we don't re-attempt every import.
        setattr(pap, "_py313_loop_fallback_installed", True)
        return
    original_clean_loop = getattr(pap, "_provide_clean_event_loop", None)
    make_pytest_loop = getattr(pap, "_make_pytest_asyncio_loop", None)

    def _shim(policy=None):
        loop_policy = policy or asyncio.get_event_loop_policy()
        try:
            loop = original_get_loop(loop_policy)
        except RuntimeError as exc:
            if "There is no current event loop" not in str(exc):
                raise
            loop = _rebind_pytest_asyncio_loop(loop_policy)
            if loop is None:
                loop = loop_policy.new_event_loop()
                if make_pytest_loop is not None:
                    loop = make_pytest_loop(loop)
                loop_policy.set_event_loop(loop)
        _remember_pytest_asyncio_loop(loop)
        return loop

    def _provide_clean_event_loop_and_rebind() -> None:
        if original_clean_loop is not None:
            original_clean_loop()
        _rebind_pytest_asyncio_loop()

    pap._get_event_loop_no_warn = _shim
    if original_clean_loop is not None:
        setattr(pap, "_provide_clean_event_loop", _provide_clean_event_loop_and_rebind)
    setattr(pap, "_py313_loop_fallback_installed", True)


# Install at import time so the shim is active before any test fixture runs.
_install_pytest_asyncio_py313_loop_fallback()


@pytest.fixture(scope="session", autouse=True)
def _bind_pytest_asyncio_session_loop(request):
    # D13 v2: capture pytest-asyncio's session loop early so the shim can
    # reuse it on Python 3.13 no-current-loop RuntimeError between tests.
    try:
        loop = request.getfixturevalue("_session_event_loop")
    except pytest.FixtureLookupError:
        yield
        return

    _remember_pytest_asyncio_loop(loop)
    _rebind_pytest_asyncio_loop()

    yield

    if _is_alive_pytest_asyncio_loop(loop):
        asyncio.get_event_loop_policy().set_event_loop(loop)


def pytest_ignore_collect(collection_path, config):
    _ = config
    if isinstance(collection_path, Path):
        if collection_path.suffix == ".txt":
            return True
    else:
        if str(collection_path).endswith(".txt"):
            return True
    return None


def _mock_redis_cache_module() -> None:
    try:
        if "redis_cache" not in sys.modules:
            return
        mod = sys.modules["redis_cache"]
        if not hasattr(mod, "_original_get_redis_client"):
            setattr(
                mod,
                "_original_get_redis_client",
                getattr(mod, "get_redis_client", None),
            )
        if not hasattr(mod, "_original_init_redis_client"):
            setattr(
                mod,
                "_original_init_redis_client",
                getattr(mod, "init_redis_client", None),
            )
        setattr(mod, "get_redis_client", lambda: None)
        setattr(mod, "REDIS_AVAILABLE", False)
        setattr(mod, "init_redis_client", lambda *a, **k: False)
        if hasattr(mod, "_redis_client"):
            setattr(mod, "_redis_client", None)
    except (KeyError, AttributeError):
        pass


def _build_fake_backup_system(backup_dir: str = "backups") -> types.SimpleNamespace:
    return types.SimpleNamespace(
        is_running=False,
        backup_dir=backup_dir,
        db_path="pricing_system.db",
        backup_interval_hours=6,
        max_backups=28,
        backup_thread=None,
        create_backup=lambda: True,
        restore_from_backup=lambda *a, **k: True,
        delete_backup=lambda *a, **k: True,
        verify_backup=lambda *a, **k: True,
        read_backup_file=lambda *a, **k: b"fake_backup_data",
        get_backup_stats=lambda: None,
        cleanup_old_backups=lambda: None,
        get_backup_file_path=lambda *a, **k: "fake_path",
        start_auto_backup=lambda: None,
        stop_auto_backup=lambda: None,
        manual_backup=lambda: True,
        list_backups=lambda: [],
    )


def _mock_auto_backup_module() -> None:
    try:
        import auto_backup
    except ImportError:
        return
    auto_backup.backup_system = _build_fake_backup_system()
    auto_backup.create_manual_backup = lambda: True
    auto_backup.restore_database = lambda *a, **k: True
    auto_backup.delete_backup_file = lambda *a, **k: True
    auto_backup.verify_backup_file = lambda *a, **k: True
    auto_backup.read_backup_file = lambda *a, **k: b"fake_data"
    auto_backup.list_backup_files = lambda: []
    auto_backup.get_auto_backup_settings = lambda: {
        "enabled": False,
        "interval_hours": 24,
        "max_backups": 10,
    }
    auto_backup.get_backup_info = lambda: None
    auto_backup.update_auto_backup_settings = lambda *a, **k: None
    auto_backup.start_backup_service = lambda: None
    auto_backup.stop_backup_service = lambda: None


def _mock_postgres_backup_service_module() -> None:
    try:
        import postgres_backup_service
    except (ImportError, AttributeError):
        return
    try:
        if hasattr(postgres_backup_service, "backup_system"):
            postgres_backup_service.backup_system = _build_fake_backup_system(
                backup_dir="backups/postgres"
            )

        function_overrides = {
            "restore_database": lambda *a, **k: True,
            "create_manual_backup": lambda: True,
            "delete_backup_file": lambda *a, **k: True,
            "verify_backup_file": lambda *a, **k: True,
            "read_backup_file": lambda *a, **k: b"fake_data",
            "list_backup_files": lambda: [],
            "get_auto_backup_settings": lambda: {
                "enabled": False,
                "interval_hours": 24,
                "max_backups": 10,
            },
            "get_backup_info": lambda: None,
            "update_auto_backup_settings": lambda *a, **k: None,
            "start_backup_service": lambda: None,
            "stop_backup_service": lambda: None,
        }
        for name, fn in function_overrides.items():
            if hasattr(postgres_backup_service, name):
                setattr(postgres_backup_service, name, fn)
    except AttributeError:
        pass


def _master_setup_test_schemas() -> None:
    """Master-only: drop stale `test_*` schemas + create `test_master`.

    Loads .env so POSTGRES_PASSWORD is available before importing the
    isolation helpers (POSTGRES_CONFIG is read at module import).
    """
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent / ".env")
    except ImportError:
        pass

    from tests._db_isolation import (
        create_all_in_schema,
        create_worker_schema,
        drop_test_schemas,
        worker_schema_name,
    )

    drop_test_schemas()
    schema = worker_schema_name()
    create_worker_schema(schema)
    create_all_in_schema(schema)


def pytest_sessionstart(session):
    _install_pytest_asyncio_py313_loop_fallback()
    _mock_redis_cache_module()
    _mock_auto_backup_module()
    _mock_postgres_backup_service_module()

    if hasattr(session.config, "workerinput"):
        return
    _master_setup_test_schemas()


def pytest_sessionfinish(session, exitstatus):
    _ = exitstatus
    if hasattr(session.config, "workerinput"):
        return

    try:
        from tests._db_isolation import drop_test_schemas

        drop_test_schemas()
    except Exception as exc:
        print(f"[pytest_sessionfinish] drop_test_schemas FAILED: {exc}")

    try:
        import psycopg2

        with psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            dbname=os.environ.get("POSTGRES_DB", "logistics"),
            user=os.environ.get("POSTGRES_USER", "logistics_user"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
        ) as conn:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(
                    r"""
                    DELETE FROM public.users
                    WHERE username LIKE 'test\_%' ESCAPE '\'
                       OR username LIKE 'e2e%'
                    """
                )
            conn.commit()
    except Exception as exc:
        print(f"[pytest_sessionfinish] public.users sweep FAILED: {exc}")
