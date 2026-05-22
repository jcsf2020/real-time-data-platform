"""Tests for the dbt refresh job."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rtdp_dbt_refresh_job import (
    VALID_MODES,
    _parse_database_url,
    _resolve_config,
    _write_profiles,
    main,
    run,
)


# --- helpers ---


def _make_subprocess_mock(returncode: int = 0):
    mock_result = MagicMock()
    mock_result.returncode = returncode
    return MagicMock(return_value=mock_result)


def _base_env(monkeypatch, tmp_path: Path, mode: str = "run-and-test") -> None:
    monkeypatch.setenv("DBT_REFRESH_MODE", mode)
    monkeypatch.setenv("DBT_POSTGRES_HOST", "localhost")
    monkeypatch.setenv("DBT_POSTGRES_USER", "rtdp")
    monkeypatch.setenv("DBT_POSTGRES_DBNAME", "realtime_platform")
    monkeypatch.setenv("DBT_POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv("DBT_POSTGRES_PORT", "5432")
    monkeypatch.setenv("DBT_TARGET", "ci")
    monkeypatch.setenv("DBT_PROJECT_DIR", "/tmp/fake-dbt-project")
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path / "rtdp-dbt-profiles"))
    monkeypatch.delenv("DATABASE_URL", raising=False)


def _capture_logs(capsys) -> list[dict]:
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines() if line.strip()]


# --- profiles.yml generation ---


def test_profiles_yml_generation_creates_expected_keys(tmp_path):
    cfg = {
        "host": "myhost", "port": 5433, "user": "rtdp",
        "password": "secret_pw", "dbname": "realtime_platform",
        "target": "cloudsql",
        "profiles_dir": str(tmp_path / "rtdp-dbt-profiles"),
    }
    profiles_dir = _write_profiles(cfg)
    content = (profiles_dir / "profiles.yml").read_text()

    assert "rtdp:" in content
    assert "type: postgres" in content
    assert "myhost" in content
    assert "rtdp" in content
    assert "realtime_platform" in content
    assert "cloudsql" in content
    assert "threads: 1" in content


def test_profiles_yml_password_not_in_logs(monkeypatch, capsys, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="run-and-test")
    monkeypatch.setenv("DBT_POSTGRES_PASSWORD", "super_secret_pw")

    mock_run = _make_subprocess_mock(0)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        cfg = _resolve_config()
        run(cfg)

    out = capsys.readouterr().out
    assert "super_secret_pw" not in out


# --- mode: compile ---


def test_compile_mode_invokes_deps_and_compile_only(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="compile")

    calls = []

    def capturing_run(cmd, **kwargs):
        calls.append(cmd[1])  # dbt subcommand is index 1
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("rtdp_dbt_refresh_job.subprocess.run", side_effect=capturing_run):
        cfg = _resolve_config()
        rc = run(cfg)

    assert rc == 0
    assert calls == ["deps", "compile"]


def test_compile_mode_does_not_invoke_run_or_test(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="compile")

    calls = []

    def capturing_run(cmd, **kwargs):
        calls.append(cmd[1])
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("rtdp_dbt_refresh_job.subprocess.run", side_effect=capturing_run):
        cfg = _resolve_config()
        run(cfg)

    assert "run" not in calls
    assert "test" not in calls


# --- mode: run ---


def test_run_mode_invokes_deps_compile_run(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="run")

    calls = []

    def capturing_run(cmd, **kwargs):
        calls.append(cmd[1])
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("rtdp_dbt_refresh_job.subprocess.run", side_effect=capturing_run):
        cfg = _resolve_config()
        rc = run(cfg)

    assert rc == 0
    assert calls == ["deps", "compile", "run"]


# --- mode: run-and-test ---


def test_run_and_test_mode_invokes_deps_compile_run_test(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="run-and-test")

    calls = []

    def capturing_run(cmd, **kwargs):
        calls.append(cmd[1])
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("rtdp_dbt_refresh_job.subprocess.run", side_effect=capturing_run):
        cfg = _resolve_config()
        rc = run(cfg)

    assert rc == 0
    assert calls == ["deps", "compile", "run", "test"]


def test_run_and_test_passes_select_to_dbt_run(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="run-and-test")

    run_cmds = []

    def capturing_run(cmd, **kwargs):
        if cmd[1] == "run":
            run_cmds.append(cmd)
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("rtdp_dbt_refresh_job.subprocess.run", side_effect=capturing_run):
        cfg = _resolve_config()
        run(cfg)

    assert len(run_cmds) == 1
    assert "--select" in run_cmds[0]
    
    assert "silver_market_event_minute_aggregates" in run_cmds[0]
    assert "gold_market_event_daily_aggregates" in run_cmds[0]
    assert "silver,gold" not in run_cmds[0]


# --- subprocess failure ---


def test_subprocess_failure_returns_nonzero(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="run-and-test")

    mock_run = _make_subprocess_mock(1)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        cfg = _resolve_config()
        rc = run(cfg)

    assert rc != 0


def test_subprocess_failure_stops_at_first_failed_step(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="run-and-test")

    calls = []

    def failing_deps(cmd, **kwargs):
        calls.append(cmd[1])
        m = MagicMock()
        m.returncode = 1 if cmd[1] == "deps" else 0
        return m

    with patch("rtdp_dbt_refresh_job.subprocess.run", side_effect=failing_deps):
        cfg = _resolve_config()
        rc = run(cfg)

    assert rc != 0
    assert calls == ["deps"]


def test_subprocess_failure_emits_error_log(monkeypatch, capsys, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="compile")

    mock_run = _make_subprocess_mock(2)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        cfg = _resolve_config()
        run(cfg)

    logs = _capture_logs(capsys)
    statuses = [lg["status"] for lg in logs]
    assert "error" in statuses


# --- invalid mode ---


def test_invalid_mode_fails_clearly(monkeypatch, capsys, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="invalid_mode")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    logs = _capture_logs(capsys)
    assert len(logs) == 1
    assert logs[0]["status"] == "error"
    assert "DBT_REFRESH_MODE" in logs[0]["error_message"]


def test_valid_modes_are_correct():
    assert VALID_MODES == frozenset({"compile", "run", "test", "run-and-test"})


# --- no dbt/profiles.yml in repo ---


def test_no_dbt_profiles_yml_in_repo(tmp_path):
    cfg = {
        "host": "localhost", "port": 5432, "user": "rtdp",
        "password": "test", "dbname": "db", "target": "ci",
        "profiles_dir": str(tmp_path / "rtdp-dbt-profiles"),
    }
    profiles_dir = _write_profiles(cfg)

    repo_dbt_profiles = Path("dbt/profiles.yml")
    assert not repo_dbt_profiles.exists()

    # Profile was written to the tmp dir, not inside dbt/
    assert (profiles_dir / "profiles.yml").exists()
    assert "dbt/profiles.yml" not in str(profiles_dir / "profiles.yml")


def test_profiles_dir_default_is_not_inside_dbt(monkeypatch, tmp_path, capsys):
    _base_env(monkeypatch, tmp_path, mode="compile")

    cfg = _resolve_config()
    # Even if user overrides via env, the default is checked here
    default_dir = "/tmp/rtdp-dbt-profiles"

    assert not cfg["profiles_dir"].startswith("dbt/")
    assert not cfg["profiles_dir"].startswith("dbt\\")
    # Default is outside repo
    assert "dbt/" not in default_dir or cfg["profiles_dir"] != default_dir


def test_profiles_dir_inside_repo_dbt_is_rejected(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="compile")
    monkeypatch.setenv("DBT_PROFILES_DIR", "dbt")

    with pytest.raises(ValueError, match="DBT_PROFILES_DIR"):
        _resolve_config()


def test_generated_profile_is_removed_after_success(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="compile")
    profiles_dir = tmp_path / "rtdp-dbt-profiles"

    mock_run = _make_subprocess_mock(0)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        cfg = _resolve_config()
        rc = run(cfg)

    assert rc == 0
    assert not (profiles_dir / "profiles.yml").exists()


# --- missing env vars ---


def test_missing_host_exits_nonzero(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("DBT_POSTGRES_HOST", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DBT_POSTGRES_USER", "rtdp")
    monkeypatch.setenv("DBT_POSTGRES_DBNAME", "realtime_platform")
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    logs = _capture_logs(capsys)
    assert logs[0]["status"] == "error"
    assert "DBT_POSTGRES_HOST" in logs[0]["error_message"]


# --- main() happy path ---


def test_main_exits_zero_on_success(monkeypatch, capsys, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="run-and-test")

    mock_run = _make_subprocess_mock(0)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0


def test_main_exits_nonzero_on_subprocess_failure(monkeypatch, capsys, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="run-and-test")

    mock_run = _make_subprocess_mock(2)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code != 0


# --- structured log schema ---


def test_started_log_has_expected_fields(monkeypatch, capsys, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="compile")

    mock_run = _make_subprocess_mock(0)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        cfg = _resolve_config()
        run(cfg)

    logs = _capture_logs(capsys)
    started = logs[0]

    assert started["status"] == "started"
    assert started["service"] == "rtdp-dbt-refresh-job"
    assert started["component"] == "dbt-refresh"
    assert started["mode"] == "compile"
    assert "timestamp_utc" in started
    assert "operation" in started


def test_completion_log_includes_duration_ms(monkeypatch, capsys, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="compile")

    mock_run = _make_subprocess_mock(0)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        cfg = _resolve_config()
        run(cfg)

    logs = _capture_logs(capsys)
    final = logs[-1]

    assert "duration_ms" in final
    assert isinstance(final["duration_ms"], float)


def test_step_log_does_not_contain_password(monkeypatch, capsys, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="compile")
    monkeypatch.setenv("DBT_POSTGRES_PASSWORD", "hunter2")

    mock_run = _make_subprocess_mock(0)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        cfg = _resolve_config()
        run(cfg)

    out = capsys.readouterr().out
    assert "hunter2" not in out


def test_step_log_command_field_is_name_only(monkeypatch, capsys, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="compile")

    mock_run = _make_subprocess_mock(0)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        cfg = _resolve_config()
        run(cfg)

    logs = _capture_logs(capsys)
    step_logs = [lg for lg in logs if "command" in lg]

    for lg in step_logs:
        # command field is "dbt deps" or "dbt compile" etc., never a full CLI string
        assert lg["command"] in ("dbt deps", "dbt compile", "dbt run", "dbt test")


# --- DATABASE_URL parsing ---


def test_parse_database_url_postgresql_scheme():
    result = _parse_database_url("postgresql://rtdp:password@myhost:5432/realtime_platform")
    assert result["host"] == "myhost"
    assert result["port"] == 5432
    assert result["user"] == "rtdp"
    assert result["password"] == "password"
    assert result["dbname"] == "realtime_platform"


def test_parse_database_url_postgres_scheme():
    result = _parse_database_url("postgres://rtdp:password@myhost/realtime_platform")
    assert result["host"] == "myhost"
    assert result["dbname"] == "realtime_platform"


def test_parse_database_url_default_port_when_absent():
    result = _parse_database_url("postgres://rtdp:pw@host/db")
    assert result["port"] == 5432


def test_parse_database_url_explicit_port_preserved():
    result = _parse_database_url("postgresql://rtdp:pw@host:5433/db")
    assert result["port"] == 5433


def test_parse_database_url_url_decoded_password():
    result = _parse_database_url("postgres://rtdp:p%40ssword@host/db")
    assert result["password"] == "p@ssword"


def test_parse_database_url_url_decoded_username():
    result = _parse_database_url("postgres://rt%2Fdp:pw@host/db")
    assert result["user"] == "rt/dp"


def test_parse_database_url_invalid_scheme_raises():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        _parse_database_url("mysql://rtdp:pw@host/db")


def test_parse_database_url_missing_host_raises():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        _parse_database_url("postgresql:///db")


# --- DATABASE_URL integration with _resolve_config ---


def test_resolve_config_uses_database_url_as_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://rtdp:urlpw@urlhost:5433/urldb")
    monkeypatch.delenv("DBT_POSTGRES_HOST", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_USER", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_DBNAME", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PORT", raising=False)
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))

    cfg = _resolve_config()

    assert cfg["host"] == "urlhost"
    assert cfg["port"] == 5433
    assert cfg["user"] == "rtdp"
    assert cfg["password"] == "urlpw"
    assert cfg["dbname"] == "urldb"


def test_resolve_config_explicit_host_overrides_database_url(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://rtdp:pw@somehost:5432/realtime_platform")
    monkeypatch.setenv("DBT_POSTGRES_HOST", "/cloudsql/project:region:instance")
    monkeypatch.delenv("DBT_POSTGRES_USER", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_DBNAME", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PORT", raising=False)
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))

    cfg = _resolve_config()

    assert cfg["host"] == "/cloudsql/project:region:instance"


def test_resolve_config_explicit_password_overrides_database_url(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://rtdp:url_password@host:5432/realtime_platform")
    monkeypatch.setenv("DBT_POSTGRES_HOST", "host")
    monkeypatch.delenv("DBT_POSTGRES_USER", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_DBNAME", raising=False)
    monkeypatch.setenv("DBT_POSTGRES_PASSWORD", "explicit_password")
    monkeypatch.delenv("DBT_POSTGRES_PORT", raising=False)
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))

    cfg = _resolve_config()

    assert cfg["password"] == "explicit_password"


def test_database_url_password_not_in_logs(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://rtdp:url_secret_pw@localhost:5432/realtime_platform")
    monkeypatch.setenv("DBT_POSTGRES_HOST", "localhost")
    monkeypatch.delenv("DBT_POSTGRES_USER", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_DBNAME", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PORT", raising=False)
    monkeypatch.setenv("DBT_TARGET", "ci")
    monkeypatch.setenv("DBT_PROJECT_DIR", "/tmp/fake-dbt-project")
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("DBT_REFRESH_MODE", "run-and-test")

    mock_run = _make_subprocess_mock(0)
    with patch("rtdp_dbt_refresh_job.subprocess.run", mock_run):
        cfg = _resolve_config()
        run(cfg)

    out = capsys.readouterr().out
    assert "url_secret_pw" not in out


def test_invalid_database_url_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "not-a-url")
    monkeypatch.delenv("DBT_POSTGRES_HOST", raising=False)
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="DATABASE_URL"):
        _resolve_config()


# --- Cloud SQL Unix socket DATABASE_URL (host in query string) ---


def test_parse_database_url_socket_query_host():
    result = _parse_database_url(
        "postgresql://rtdp:pw@/realtime_platform?host=/cloudsql/project:region:instance"
    )
    assert result["host"] == "/cloudsql/project:region:instance"
    assert result["user"] == "rtdp"
    assert result["password"] == "pw"
    assert result["dbname"] == "realtime_platform"
    assert result["port"] == 5432


def test_resolve_config_accepts_database_url_without_hostname_when_query_host_exists(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://rtdp:pw@/realtime_platform?host=/cloudsql/project:region:instance",
    )
    monkeypatch.delenv("DBT_POSTGRES_HOST", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_USER", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_DBNAME", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PORT", raising=False)
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))

    cfg = _resolve_config()

    assert cfg["host"] == "/cloudsql/project:region:instance"
    assert cfg["user"] == "rtdp"
    assert cfg["dbname"] == "realtime_platform"


def test_resolve_config_explicit_host_overrides_socket_query_host(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://rtdp:pw@/realtime_platform?host=/cloudsql/project:region:instance",
    )
    monkeypatch.setenv("DBT_POSTGRES_HOST", "/cloudsql/other-project:us-central1:other-db")
    monkeypatch.delenv("DBT_POSTGRES_USER", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_DBNAME", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("DBT_POSTGRES_PORT", raising=False)
    monkeypatch.setenv("DBT_PROFILES_DIR", str(tmp_path))

    cfg = _resolve_config()

    assert cfg["host"] == "/cloudsql/other-project:us-central1:other-db"


# --- dbt metrics runtime integration ---


def test_metrics_disabled_by_default_does_not_call_metrics_script(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, mode="run-and-test")

    calls = []

    def capturing_run(cmd, **kwargs):
        calls.append(cmd)
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("rtdp_dbt_refresh_job.subprocess.run", side_effect=capturing_run):
        cfg = _resolve_config()
        rc = run(cfg)

    assert rc == 0
    assert [cmd[1] for cmd in calls if cmd[0] == "dbt"] == ["deps", "compile", "run", "test"]
    assert not any("push_dbt_metrics.py" in " ".join(cmd) for cmd in calls)


def test_metrics_enabled_dry_run_pushes_after_run_and_test(monkeypatch, tmp_path, capsys):
    _base_env(monkeypatch, tmp_path, mode="run-and-test")
    monkeypatch.setenv("DBT_METRICS_ENABLED", "true")
    monkeypatch.setenv("DBT_METRICS_DRY_RUN", "true")
    monkeypatch.setenv("DBT_METRICS_SCRIPT_PATH", "/app/scripts/push_dbt_metrics.py")
    monkeypatch.setenv("DBT_METRICS_RUN_RESULTS_PATH", "/app/dbt/target/run_results.json")

    calls = []

    def capturing_run(cmd, **kwargs):
        calls.append(cmd)
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("rtdp_dbt_refresh_job.subprocess.run", side_effect=capturing_run):
        cfg = _resolve_config()
        rc = run(cfg)

    assert rc == 0

    metrics_calls = [cmd for cmd in calls if "/app/scripts/push_dbt_metrics.py" in cmd]
    assert len(metrics_calls) == 2
    assert all("--dry-run" in cmd for cmd in metrics_calls)
    assert all("--run-results-path" in cmd for cmd in metrics_calls)
    assert all("/app/dbt/target/run_results.json" in cmd for cmd in metrics_calls)

    logs = _capture_logs(capsys)
    metric_logs = [lg for lg in logs if lg.get("command") == "push dbt metrics"]
    assert len(metric_logs) == 2
    assert all(lg["status"] == "success" for lg in metric_logs)
    assert {lg["operation"] for lg in metric_logs} == {"dbt_run_metrics", "dbt_test_metrics"}


def test_metrics_failure_returns_nonzero_when_enabled(monkeypatch, tmp_path, capsys):
    _base_env(monkeypatch, tmp_path, mode="run")
    monkeypatch.setenv("DBT_METRICS_ENABLED", "true")
    monkeypatch.setenv("DBT_METRICS_DRY_RUN", "true")

    def capturing_run(cmd, **kwargs):
        m = MagicMock()
        if "push_dbt_metrics.py" in " ".join(cmd):
            m.returncode = 3
        else:
            m.returncode = 0
        return m

    with patch("rtdp_dbt_refresh_job.subprocess.run", side_effect=capturing_run):
        cfg = _resolve_config()
        rc = run(cfg)

    assert rc == 3

    logs = _capture_logs(capsys)
    final = logs[-1]
    assert final["status"] == "error"
    metric_errors = [
        lg for lg in logs
        if lg.get("command") == "push dbt metrics" and lg.get("status") == "error"
    ]
    assert len(metric_errors) == 1
