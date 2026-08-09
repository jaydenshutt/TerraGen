"""Shared helpers for optional terraform/tofu validation in pytest."""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pytest


@lru_cache(maxsize=1)
def terraform_binary() -> Optional[str]:
    """Return first available binary name (terraform preferred over tofu)."""
    for name in ("terraform", "tofu"):
        if shutil.which(name):
            return name
    return None


requires_terraform = pytest.mark.skipif(
    terraform_binary() is None,
    reason="terraform/tofu not on PATH (install to run HCL validation tests)",
)


def require_terraform() -> str:
    binary = terraform_binary()
    if not binary:
        pytest.skip("terraform/tofu not on PATH")
    return binary


def workdir_for_config(project_dir: Path, cfg) -> Path:
    """Root to run terraform validate against (modular env root or flat root)."""
    project_dir = Path(project_dir)
    if getattr(cfg, "is_modular", False):
        env = (cfg.env_list or [cfg.environment])[0]
        return project_dir / "envs" / env
    return project_dir


def terraform_validate(
    project_dir: Path,
    *,
    workdir: Optional[Path] = None,
    also_bootstrap: bool = False,
) -> None:
    """
    Run terraform fmt (best-effort), init -backend=false, and validate.

    Uses TF_PLUGIN_CACHE_DIR so repeated provider downloads stay fast.
    Raises AssertionError with stdout/stderr on failure.
    """
    binary = require_terraform()
    root = Path(project_dir)
    work = Path(workdir) if workdir is not None else root
    assert work.is_dir(), f"terraform workdir missing: {work}"

    env = os.environ.copy()
    cache = Path(env.get("TF_PLUGIN_CACHE_DIR") or (Path.home() / ".terraform.d" / "plugin-cache"))
    cache.mkdir(parents=True, exist_ok=True)
    env["TF_PLUGIN_CACHE_DIR"] = str(cache)
    env.setdefault("TF_IN_AUTOMATION", "1")
    env.setdefault("TF_INPUT", "0")

    # Normalize formatting (generated HCL is usually already fmt-clean)
    subprocess.run(
        [binary, "fmt", "-recursive", str(root)],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    def _run(args: list[str], cwd: Path) -> None:
        p = subprocess.run(
            args,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if p.returncode != 0:
            combined = f"{p.stdout or ''}\n{p.stderr or ''}"
            # Registry / DNS outages are environment issues, not product regressions
            transient = (
                "no such host" in combined
                or "could not connect to registry" in combined
                or "Failed to query available provider" in combined
                or "dial tcp" in combined
                or "i/o timeout" in combined
                or "TLS handshake timeout" in combined
            )
            if transient:
                pytest.skip(
                    f"Terraform registry/network unavailable during {' '.join(args)}:\n"
                    f"{combined[-500:]}"
                )
            raise AssertionError(
                f"{' '.join(args)} failed (cwd={cwd}, code={p.returncode}):\n"
                f"--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}"
            )

    _run([binary, "init", "-backend=false", "-input=false", "-no-color"], work)
    _run([binary, "validate", "-no-color"], work)

    if also_bootstrap:
        boot = root / "bootstrap"
        if (boot / "main.tf").is_file():
            _run([binary, "init", "-backend=false", "-input=false", "-no-color"], boot)
            _run([binary, "validate", "-no-color"], boot)


def render_and_terraform_validate(cfg, outdir: Path, *, also_bootstrap: bool = True) -> Path:
    """Render project then terraform-validate (skips if no terraform binary)."""
    from terragen.render import render_project
    from terragen.validate import validate_config

    result = validate_config(cfg)
    assert result.ok, result.errors
    outdir = Path(outdir)
    render_project(cfg, outdir, force=True)
    if terraform_binary() is None:
        return outdir
    terraform_validate(
        outdir,
        workdir=workdir_for_config(outdir, cfg),
        also_bootstrap=also_bootstrap,
    )
    return outdir
