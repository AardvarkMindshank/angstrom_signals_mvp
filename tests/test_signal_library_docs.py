import pathlib

import signal_library as sl

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_catalogue_doc_lists_every_signal_version():
    text = (ROOT / "docs" / "signal_library_catalogue.md").read_text(encoding="utf-8")
    for d in sl.REGISTRY.latest():
        if not d.id.startswith("test."):
            assert f"`{d.key}`" in text, f"regenerate docs/signal_library_catalogue.md ({d.key} missing)"


def test_existing_readings_do_not_import_the_library():
    for name in ("scoring.py", "signals_v2.py", "alerts.py", "run_alerts.py", "evidence.py", "digest.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "signal_library" not in text and "signal_groups" not in text, name


def test_the_development_panels_are_gone_and_the_admin_role_stays_protected():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "signal_inspector.render(" not in source and "analysis_card" not in source
    # The role itself is protected in the database: a signed-in session cannot change it.
    sql = (ROOT / "supabase_rls.sql").read_text(encoding="utf-8")
    assert "create trigger keep_profile_role" in sql and "new.role := old.role;" in sql
