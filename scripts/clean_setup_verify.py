"""Verify an isolated local source export; never commit, push or alter the user's DB."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = {"eventlens", "frontend", "scripts", "tests", "data", "docs"}
FILES = {
    ".gitignore",
    "LICENSE",
    "README.md",
    "PROJECT_PLAN.md",
    "THIRD_PARTY_NOTICES.md",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-feasibility.txt",
}
EXCLUDED = {".git", ".venv", ".cache", "runtime", "node_modules", "dist", "__pycache__", "coverage"}


def main():
    free = shutil.disk_usage(ROOT).free
    if free < 5 * 1024**3:
        raise RuntimeError(
            "Need at least 5 GiB free for this isolated dependency/model verification"
        )
    work = ROOT / "runtime" / f"phase5-clean-{uuid4().hex}"
    project = work / "project"
    project.mkdir(parents=True)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "kind": "local-source-export-not-GitHub-clone",
        "status": "running",
        "initial_free_bytes": free,
        "steps": [],
        "source_sha256": {},
    }
    report_path = work / "report.json"

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    environment = os.environ.copy()
    environment.update(
        {
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "HF_HUB_DISABLE_XET": "1",
            "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
            "HF_HUB_DOWNLOAD_TIMEOUT": "120",
            "EVENTLENS_PUBLIC": "false",
            "EVENTLENS_WRITE_TOKEN": "",
            "EVENTLENS_ALLOWED_HOSTS": "127.0.0.1,localhost",
            "EVENTLENS_DATABASE": str(project / "runtime" / "clean.sqlite3"),
            "PYTHONPATH": "",
            "PYTHONNOUSERSITE": "1",
        }
    )
    environment.pop("VIRTUAL_ENV", None)

    def run(name, command, directory=project, timeout=1800):
        print(f"Starting {name}", flush=True)
        started = time.monotonic()
        step = {"name": name, "status": "running"}
        report["steps"].append(step)
        save()
        with (work / f"{name}.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(
                command,
                cwd=directory,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        step.update(
            {
                "status": "passed" if process.returncode == 0 else "failed",
                "exit_code": process.returncode,
                "seconds": time.monotonic() - started,
            }
        )
        save()
        print(f"Finished {name}: {step['status']} ({step['seconds']:.1f}s)", flush=True)
        if process.returncode:
            raise RuntimeError(f"{name} failed; inspect its local log")

    try:
        paths = (
            subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                cwd=ROOT,
            )
            .decode("utf-8")
            .split("\0")
        )
        for relative in sorted(set(paths) - {""}):
            path = Path(relative)
            if (
                path.is_absolute()
                or ".." in path.parts
                or any(part in EXCLUDED for part in path.parts)
            ):
                raise ValueError("Export encountered an unsafe or ignored path")
            if path.parts[0] not in FOLDERS and relative not in FILES:
                raise ValueError(f"Unexpected publishable path: {relative}")
            if any(part.startswith(".env") for part in path.parts):
                raise ValueError("Environment files are excluded from clean export")
            source = ROOT / path
            if source.is_symlink() or not source.is_file():
                raise ValueError("Export requires ordinary source files")
            destination = project / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            report["source_sha256"][relative] = hashlib.sha256(source.read_bytes()).hexdigest()
        report["source_manifest_sha256"] = hashlib.sha256(
            json.dumps(report["source_sha256"], sort_keys=True).encode()
        ).hexdigest()
        save()
        python = project / ".venv" / "Scripts" / "python.exe"
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            raise RuntimeError("npm unavailable")
        run("create-venv", [sys.executable, "-m", "venv", str(project / ".venv")])
        run("python-version", [str(python), "--version"])
        run("node-version", ["node", "--version"])
        run("npm-version", [npm, "--version"])
        run(
            "install-python",
            [str(python), "-m", "pip", "install", "-r", "requirements-dev.txt"],
            timeout=2400,
        )
        run("pip-check", [str(python), "-m", "pip", "check"])
        run("pip-freeze", [str(python), "-m", "pip", "freeze"])
        run("install-frontend", [npm, "ci"], project / "frontend")
        run("frontend-build", [npm, "run", "build"], project / "frontend")
        run("frontend-tests", [npm, "test"], project / "frontend")
        run("frontend-audit", [npm, "audit", "--audit-level=low"], project / "frontend")
        # pytest creates basetemp itself, but not missing parent directories.
        (project / ".cache" / "test-runs").mkdir(parents=True, exist_ok=True)
        run(
            "backend-tests-before-model",
            [
                str(python),
                "-m",
                "pytest",
                "-m",
                "not model",
                "-q",
                "--basetemp=.cache/test-runs/clean-before-model",
            ],
        )
        if (project / ".cache" / "huggingface").exists():
            raise ValueError("Clean model acquisition must start with no model cache")
        report["model_cache_initially_absent"] = True
        save()
        run("fresh-pinned-model-download", [str(python), "scripts/download_model.py"], timeout=1800)
        run(
            "real-model-tests",
            [str(python), "-m", "pytest", "-q", "--basetemp=.cache/test-runs/clean-real-model"],
        )
        run("offline-end-to-end", [str(python), "scripts/phase3_verify.py"])
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        save()
        print(f"Report: {report_path}", flush=True)


if __name__ == "__main__":
    main()
