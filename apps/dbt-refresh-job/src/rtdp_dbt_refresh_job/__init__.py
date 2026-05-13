"""dbt refresh job: run dbt compile/run/test against Cloud SQL via env vars."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SERVICE = "rtdp-dbt-refresh-job"
_COMPONENT = "dbt-refresh"

VALID_MODES = frozenset({"compile", "run", "test", "run-and-test"})


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_log(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True), flush=True)


def _resolve_config() -> dict:
    """Read and validate env vars. Raises ValueError on missing or invalid values."""
    mode = os.getenv("DBT_REFRESH_MODE", "run-and-test")
    if mode not in VALID_MODES:
        raise ValueError(
            f"Invalid DBT_REFRESH_MODE={mode!r}. Valid modes: {sorted(VALID_MODES)}"
        )

    try:
        port = int(os.getenv("DBT_POSTGRES_PORT", "5432"))
    except ValueError:
        raw = os.getenv("DBT_POSTGRES_PORT")
        raise ValueError(f"DBT_POSTGRES_PORT must be an integer, got: {raw!r}")

    host = os.getenv("DBT_POSTGRES_HOST", "")
    user = os.getenv("DBT_POSTGRES_USER", "")
    dbname = os.getenv("DBT_POSTGRES_DBNAME", "")

    missing = [k for k, v in {
        "DBT_POSTGRES_HOST": host,
        "DBT_POSTGRES_USER": user,
        "DBT_POSTGRES_DBNAME": dbname,
    }.items() if not v]

    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")

    profiles_dir = os.getenv("DBT_PROFILES_DIR", "/tmp/rtdp-dbt-profiles")
    repo_dbt_dir = (Path.cwd() / "dbt").resolve()
    resolved_profiles_dir = Path(profiles_dir).resolve()

    if resolved_profiles_dir == repo_dbt_dir or resolved_profiles_dir.is_relative_to(repo_dbt_dir):
        raise ValueError("DBT_PROFILES_DIR must not point inside the repository dbt/ directory")

    return {
        "mode": mode,
        "host": host,
        "port": port,
        "user": user,
        "password": os.getenv("DBT_POSTGRES_PASSWORD", ""),
        "dbname": dbname,
        "target": os.getenv("DBT_TARGET", "cloudsql"),
        "project_dir": os.getenv("DBT_PROJECT_DIR", "/app/dbt"),
        "profiles_dir": profiles_dir,
    }


def _write_profiles(cfg: dict) -> Path:
    """Write a temporary profiles.yml from env vars. Returns the directory Path."""
    profiles_dir = Path(cfg["profiles_dir"])
    profiles_dir.mkdir(parents=True, exist_ok=True)

    content = (
        f"rtdp:\n"
        f"  target: {cfg['target']}\n"
        f"  outputs:\n"
        f"    {cfg['target']}:\n"
        f"      type: postgres\n"
        f"      host: \"{cfg['host']}\"\n"
        f"      port: {cfg['port']}\n"
        f"      user: \"{cfg['user']}\"\n"
        f"      password: \"{cfg['password']}\"\n"
        f"      dbname: \"{cfg['dbname']}\"\n"
        f"      schema: public\n"
        f"      threads: 1\n"
    )
    (profiles_dir / "profiles.yml").write_text(content)
    return profiles_dir


def _dbt_cmd(name: str, project_dir: str, profiles_dir: str, target: str, extra: list[str] | None = None) -> list[str]:
    cmd = ["dbt", name, "--project-dir", project_dir, "--profiles-dir", profiles_dir]
    if name != "deps":
        cmd += ["--target", target]
    if extra:
        cmd += extra
    return cmd


def _run_dbt_step(
    cmd: list[str],
    command_name: str,
    operation: str,
    mode: str,
    target: str,
) -> int:
    """Run one dbt subprocess step. Emits a step-level log. Returns exit code."""
    t0 = time.monotonic()
    result = subprocess.run(cmd)
    duration_ms = round((time.monotonic() - t0) * 1000, 3)

    if result.returncode == 0:
        emit_log({
            "command": command_name,
            "component": _COMPONENT,
            "duration_ms": duration_ms,
            "mode": mode,
            "operation": operation,
            "service": _SERVICE,
            "status": "success",
            "target": target,
            "timestamp_utc": utc_now_iso(),
        })
    else:
        emit_log({
            "command": command_name,
            "component": _COMPONENT,
            "duration_ms": duration_ms,
            "error_message": f"{command_name} exited with code {result.returncode}",
            "error_type": "SubprocessError",
            "mode": mode,
            "operation": operation,
            "service": _SERVICE,
            "status": "error",
            "target": target,
            "timestamp_utc": utc_now_iso(),
        })

    return result.returncode


def run(cfg: dict) -> int:
    """Orchestrate the dbt refresh flow. Returns exit code."""
    mode = cfg["mode"]
    target = cfg["target"]
    project_dir = cfg["project_dir"]

    t0_total = time.monotonic()
    emit_log({
        "component": _COMPONENT,
        "mode": mode,
        "operation": f"dbt_{mode.replace('-', '_')}",
        "service": _SERVICE,
        "status": "started",
        "target": target,
        "timestamp_utc": utc_now_iso(),
    })

    profiles_dir: Path | None = None
    exit_code = 0
    caught_exc: Exception | None = None

    try:
        profiles_dir = _write_profiles(cfg)
        pdir = str(profiles_dir)

        steps: list[tuple[str, str, str, list[str]]] = [
            ("deps", "dbt deps", "dbt_deps", []),
        ]

        if mode == "compile":
            steps.append(("compile", "dbt compile", "dbt_compile", []))
        elif mode == "run":
            steps.append(("run", "dbt run", "dbt_run", ["--select", "silver,gold"]))
        elif mode == "test":
            steps.append(("test", "dbt test", "dbt_test", []))
        elif mode == "run-and-test":
            steps.append(("compile", "dbt compile", "dbt_compile", []))
            steps.append(("run", "dbt run", "dbt_run", ["--select", "silver,gold"]))
            steps.append(("test", "dbt test", "dbt_test", []))

        for dbt_name, cmd_name, operation, extra in steps:
            rc = _run_dbt_step(
                _dbt_cmd(dbt_name, project_dir, pdir, target, extra or None),
                cmd_name,
                operation,
                mode,
                target,
            )
            if rc != 0:
                exit_code = rc
                break

    except Exception as exc:
        caught_exc = exc
        exit_code = 1

    finally:
        if profiles_dir is not None:
            try:
                (profiles_dir / "profiles.yml").unlink(missing_ok=True)
            except OSError:
                pass

    final_log: dict = {
        "component": _COMPONENT,
        "duration_ms": round((time.monotonic() - t0_total) * 1000, 3),
        "mode": mode,
        "operation": f"dbt_{mode.replace('-', '_')}",
        "service": _SERVICE,
        "status": "success" if exit_code == 0 else "error",
        "target": target,
        "timestamp_utc": utc_now_iso(),
    }
    if caught_exc is not None:
        final_log["error_message"] = str(caught_exc)
        final_log["error_type"] = type(caught_exc).__name__

    emit_log(final_log)
    return exit_code


def main() -> None:
    try:
        cfg = _resolve_config()
    except ValueError as exc:
        emit_log({
            "component": _COMPONENT,
            "error_message": str(exc),
            "error_type": type(exc).__name__,
            "operation": "dbt_startup",
            "service": _SERVICE,
            "status": "error",
            "timestamp_utc": utc_now_iso(),
        })
        sys.exit(1)

    sys.exit(run(cfg))