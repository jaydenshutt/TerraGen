"""Bootstrap remote state helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from terragen.config import TerraGenConfig
from terragen.render import render_project


def find_bootstrap_dir(path: Path) -> Optional[Path]:
    """Locate bootstrap/ under a generated project."""
    path = Path(path)
    candidates = [
        path / "bootstrap",
        path,
    ]
    for c in candidates:
        if (c / "main.tf").exists() and c.name == "bootstrap":
            return c
        if c.name == "bootstrap" and any(c.glob("*.tf")):
            return c
    # If path itself is project root
    if (path / "bootstrap" / "main.tf").exists():
        return path / "bootstrap"
    return None


def ensure_bootstrap_generated(
    cfg: TerraGenConfig,
    outdir: Path,
    *,
    force: bool = True,
) -> Path:
    """Ensure project (including bootstrap/) exists for cfg."""
    outdir = Path(outdir)
    render_project(cfg, outdir, force=force, dry_run=False)
    boot = outdir / "bootstrap"
    if not boot.exists():
        raise FileNotFoundError(
            "Bootstrap directory was not generated. "
            "Set enable_bootstrap: true and enable_backend: true."
        )
    return boot


def run_bootstrap(
    bootstrap_dir: Path,
    *,
    binary: str = "terraform",
    auto_approve: bool = False,
    dry_run: bool = False,
) -> Tuple[int, str]:
    """
    terraform init + plan/apply in bootstrap directory.
    Returns (exit_code, combined_log).
    """
    bootstrap_dir = Path(bootstrap_dir)
    if not shutil.which(binary):
        return 127, f"{binary} not found on PATH. Install Terraform or OpenTofu."

    logs: List[str] = []

    def run(args: List[str]) -> int:
        logs.append(f"$ {' '.join(args)}")
        p = subprocess.run(
            args,
            cwd=str(bootstrap_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        if p.stdout:
            logs.append(p.stdout)
        if p.stderr:
            logs.append(p.stderr)
        return p.returncode

    if dry_run:
        return 0, f"[dry-run] would run in {bootstrap_dir}:\n  {binary} init\n  {binary} plan\n  {binary} apply"

    code = run([binary, "init", "-input=false"])
    if code != 0:
        return code, "\n".join(logs)

    code = run([binary, "plan", "-input=false"])
    if code != 0:
        return code, "\n".join(logs)

    if auto_approve:
        code = run([binary, "apply", "-input=false", "-auto-approve"])
    else:
        logs.append(
            "\nPlan completed. Re-run with --auto-approve to apply, or:\n"
            f"  cd {bootstrap_dir}\n  {binary} apply\n"
        )
        code = 0

    return code, "\n".join(logs)
