"""Real database tests for the Signal Groups storage SQL (design §7 acceptance requirement).

Starts a throwaway Postgres (initdb + pg_ctl), loads tests/pg/supabase_stub.sql, the real
sql/2026-11-04_signal_groups.sql (twice, to prove it is safe to re-run), then tests/pg/signal_groups_security.sql.
Skipped when no Postgres server binaries are installed.
"""

import glob
import json
import os
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _bin(name):
    found = shutil.which(name)
    if found:
        return found
    for path in sorted(glob.glob(f"/usr/lib/postgresql/*/bin/{name}"), reverse=True):
        return path
    return None


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def postgres():
    initdb, pg_ctl, psql = _bin("initdb"), _bin("pg_ctl"), _bin("psql")
    if not (initdb and pg_ctl and psql):
        pytest.skip("Postgres server binaries not installed")
    as_root = os.geteuid() == 0
    prefix = ["runuser", "-u", "postgres", "--"] if as_root else []
    if as_root and not shutil.which("runuser"):
        pytest.skip("running as root without runuser")
    work = tempfile.mkdtemp(prefix="pgtest-", dir="/var/tmp" if as_root else None)
    if as_root:
        shutil.chown(work, "postgres")
    data, port = os.path.join(work, "data"), _free_port()
    subprocess.run(prefix + [initdb, "-D", data, "-U", "postgres", "--auth=trust", "-E", "UTF8"],
                   check=True, capture_output=True)
    subprocess.run(prefix + [pg_ctl, "-D", data, "-l", os.path.join(work, "log"), "-w", "start",
                             "-o", f"-k {work} -p {port} -c listen_addresses=''"], check=True, capture_output=True)

    def run(path, *extra):
        return subprocess.run(prefix + [psql, "-h", work, "-p", str(port), "-U", "postgres", "-d", "postgres",
                                        "-v", "ON_ERROR_STOP=1", "-X", "-q", "-f", str(path), *extra],
                              capture_output=True, text=True)
    try:
        yield run
    finally:
        subprocess.run(prefix + [pg_ctl, "-D", data, "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(work, ignore_errors=True)


def _copy_readable(path):
    """psql under runuser cannot read files in root-owned folders: copy them somewhere world-readable."""
    tmp = tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, dir="/var/tmp")
    tmp.write(Path(path).read_text(encoding="utf-8"))
    tmp.close()
    os.chmod(tmp.name, 0o644)
    return tmp.name


def test_signal_group_storage_security(postgres):
    files = [ROOT / "tests" / "pg" / "supabase_stub.sql", ROOT / "sql" / "2026-11-04_signal_groups.sql",
             ROOT / "sql" / "2026-11-04_signal_groups.sql", ROOT / "tests" / "pg" / "signal_groups_security.sql"]
    for path in files:
        copy = _copy_readable(path)
        try:
            result = postgres(copy)
        finally:
            os.unlink(copy)
        assert result.returncode == 0, f"{path.name}:\n{result.stdout}\n{result.stderr}"
    assert "ALL SIGNAL GROUP SECURITY TESTS PASSED" in result.stdout


def test_starter_sql_installs_the_code_starters(postgres):
    """The starters file seeds exactly the starter JSON shipped in signal_groups/starters (and is re-runnable)."""
    import signal_groups as sg
    text = (ROOT / "sql" / "2026-11-04_signal_groups_starters.sql").read_text(encoding="utf-8")
    for alias in sg.STARTERS:
        body = json.dumps(sg.starter(alias), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert f"public.analysis_seed_starter('{alias}', $json${body}$json$::jsonb)" in text
    for _ in range(2):
        copy = _copy_readable(ROOT / "sql" / "2026-11-04_signal_groups_starters.sql")
        try:
            result = postgres(copy)
        finally:
            os.unlink(copy)
        assert result.returncode == 0, result.stderr
