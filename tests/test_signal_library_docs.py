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
        assert "signal_library" not in (ROOT / name).read_text(encoding="utf-8"), name


def test_inspector_is_only_reached_by_admins():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("signal_inspector.render(") == 1 and source.count("import signal_inspector") == 1
    gate = 'if str((load_profile() or {}).get("role") or "") == "admin":'
    block = source[source.index(gate):source.index("signal_inspector.render(")]
    # Everything between the admin check and the call is indented under it (no dedent back to top level).
    lines = block.splitlines()[1:]
    assert lines and all(line.startswith("    ") or not line.strip() for line in lines)
    # The role itself is protected in the database: a signed-in session cannot change it.
    sql = (ROOT / "supabase_rls.sql").read_text(encoding="utf-8")
    assert "create trigger keep_profile_role" in sql and "new.role := old.role;" in sql
