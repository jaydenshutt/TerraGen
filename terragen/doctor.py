"""Environment health checks for TerraGen."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from terragen import __version__
from terragen.render import TEMPLATES_DIR


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    level: str = "info"  # info | warn | error


@dataclass
class DoctorReport:
    checks: List[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(c.level == "error" and not c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str, level: str = "info") -> None:
        self.checks.append(Check(name=name, ok=ok, detail=detail, level=level if not ok else "info"))


def _run(cmd: List[str], timeout: int = 15) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except FileNotFoundError:
        return 127, "not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def run_doctor(project_dir: Optional[Path] = None) -> DoctorReport:
    report = DoctorReport()

    report.add(
        "terragen",
        True,
        f"version {__version__} on Python {sys.version.split()[0]} ({platform.system()})",
    )

    # Dependencies
    for mod in ("jinja2", "yaml"):
        ok = importlib.util.find_spec(mod if mod != "yaml" else "yaml") is not None
        report.add(
            f"python:{mod}",
            ok,
            "installed" if ok else "missing — pip install Jinja2 PyYAML",
            level="error",
        )

    # Templates integrity
    required = [
        TEMPLATES_DIR / "common" / "versions.tf.j2",
        TEMPLATES_DIR / "aws" / "network.tf.j2",
        TEMPLATES_DIR / "gcp" / "network.tf.j2",
        TEMPLATES_DIR / "azure" / "network.tf.j2",
        TEMPLATES_DIR / "layout" / "env_main.tf.j2",
    ]
    missing = [str(p) for p in required if not p.exists()]
    report.add(
        "templates",
        not missing,
        "all core templates present" if not missing else f"missing: {missing}",
        level="error",
    )

    # Terraform / OpenTofu
    tf = shutil.which("terraform")
    tofu = shutil.which("tofu")
    if tf:
        code, out = _run([tf, "version"])
        first = out.splitlines()[0] if out else ""
        report.add("terraform", code == 0, first or tf)
    else:
        report.add(
            "terraform",
            False,
            "not on PATH (optional for generate; required to apply)",
            level="warn",
        )
    if tofu:
        code, out = _run([tofu, "version"])
        report.add("opentofu", code == 0, out.splitlines()[0] if out else tofu)
    else:
        report.add("opentofu", False, "not on PATH (optional)", level="info")

    # Cloud CLIs (optional)
    for name, binary in (("aws-cli", "aws"), ("gcloud", "gcloud"), ("az-cli", "az")):
        path = shutil.which(binary)
        if path:
            report.add(name, True, path)
        else:
            report.add(name, False, "not on PATH (optional)", level="info")

    # Project directory marker
    if project_dir:
        project_dir = Path(project_dir)
        marker = project_dir / ".terragen-generated"
        report.add(
            "project",
            marker.exists(),
            f"TerraGen project at {project_dir}" if marker.exists() else f"no marker in {project_dir}",
            level="warn" if not marker.exists() else "info",
        )
        answers = project_dir / "terragen.answers.yaml"
        if answers.exists():
            report.add("answers-snapshot", True, str(answers))

    return report


def format_report(report: DoctorReport) -> str:
    lines = ["TerraGen doctor", "=" * 40]
    for c in report.checks:
        if c.ok:
            icon = "OK"
        elif c.level == "error":
            icon = "ERR"
        elif c.level == "warn":
            icon = "WARN"
        else:
            icon = "INFO"
        lines.append(f"[{icon:4}] {c.name}: {c.detail}")
    lines.append("=" * 40)
    lines.append("Overall: " + ("healthy" if report.ok else "issues found"))
    return "\n".join(lines)
