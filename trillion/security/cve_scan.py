"""
Dependency CVE scanning — a thin wrapper around pip-audit.

Threat: supply-chain compromise. A vulnerable (or malicious) transitive
dependency. This runs pip-audit with a stripped env, parses the JSON, and
persists a result sidecar so the security shield can surface it. A missing
scanner is recorded as an error result, not a crash.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .subprocess_env import shell_minimal

_SIDECAR = Path(__file__).parent.parent.parent / "data" / "cve_scan.json"


def run_scan() -> dict:
    """Run pip-audit, persist and return the result."""
    result = {
        "cve_count": None,
        "findings": [],
        "scanner_version": None,
        "error_message": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "json", "--progress-spinner", "off"],
            capture_output=True, text=True, timeout=180, env=shell_minimal(),
        )
        out = (proc.stdout or "").strip()
        if not out and proc.returncode != 0:
            # pip-audit not installed / failed to run
            err = (proc.stderr or "").strip()[:300]
            result["error_message"] = err or "pip-audit not available"
        else:
            data = json.loads(out) if out else {}
            deps = data.get("dependencies", data) if isinstance(data, dict) else data
            findings = []
            for dep in (deps or []):
                for v in dep.get("vulns", []) or []:
                    findings.append({"package": dep.get("name"), "id": v.get("id")})
            result["cve_count"] = len(findings)
            result["findings"] = findings[:50]
    except FileNotFoundError:
        result["error_message"] = "pip-audit not installed"
    except subprocess.TimeoutExpired:
        result["error_message"] = "pip-audit timed out"
    except Exception as e:
        result["error_message"] = str(e)[:300]

    try:
        _SIDECAR.parent.mkdir(parents=True, exist_ok=True)
        _SIDECAR.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:
        pass
    return result


def latest() -> dict | None:
    try:
        return json.loads(_SIDECAR.read_text(encoding="utf-8"))
    except Exception:
        return None
