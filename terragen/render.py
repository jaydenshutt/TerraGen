"""Jinja2 rendering engine for Terraform project generation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from terragen.config import TerraGenConfig

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"


@dataclass
class RenderResult:
    output_dir: Path
    files_written: List[Path] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def relative_files(self) -> List[str]:
        return [str(p.relative_to(self.output_dir)).replace("\\", "/") for p in self.files_written]


def _build_env(extra_paths: Optional[Sequence[Path]] = None) -> Environment:
    paths = [TEMPLATES_DIR, TEMPLATES_DIR / "common", TEMPLATES_DIR / "layout"]
    if extra_paths:
        paths.extend(extra_paths)
    env = Environment(
        loader=FileSystemLoader([str(p) for p in paths if p.exists()]),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )
    env.filters["tojson"] = lambda v, **kw: json.dumps(v, **kw)
    env.filters["tf"] = _tf_value
    return env


def _tf_value(value) -> str:
    """Render a Python value as an HCL literal (terraform-fmt friendly)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if value is None:
        return "null"
    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        inner = ", ".join(_tf_value(v) for v in value)
        return f"[{inner}]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        parts = [f"{_tf_value(str(k))} = {_tf_value(v)}" for k, v in value.items()]
        return "{ " + ", ".join(parts) + " }"
    return json.dumps(str(value))


def _plan_flat(cfg: TerraGenConfig) -> List[tuple[str, str]]:
    """
    Flat single-root project (default).

    HashiCorp-aligned names:
      terraform.tf, providers.tf, variables.tf, outputs.tf, main.tf, backend.tf
    Additional resource files (security, cluster, …) keep domain splits for
    large multi-cloud stacks - allowed for complex modules.
    """
    cloud = cfg.cloud
    files: List[tuple[str, str]] = [
        ("versions.tf.j2", "terraform.tf"),
        ("providers.tf.j2", "providers.tf"),
        ("variables.tf.j2", "variables.tf"),
        ("outputs.tf.j2", "outputs.tf"),
        ("terraform.tfvars.j2", "terraform.tfvars"),
        ("gitignore.j2", ".gitignore"),
        ("README.md.j2", "README.md"),
        # Primary entrypoint (was network.tf) - HashiCorp standard module structure
        (f"{cloud}/network.tf.j2", "main.tf"),
        (f"{cloud}/security.tf.j2", "security.tf"),
    ]

    if cfg.enable_flow_logs or cfg.enable_billing_alerts or cfg.enable_guardduty:
        files.append((f"{cloud}/observability.tf.j2", "observability.tf"))

    if cfg.enable_cluster:
        files.append((f"{cloud}/cluster.tf.j2", "cluster.tf"))

    if cfg.enable_hub_spoke:
        files.append((f"{cloud}/hub_spoke.tf.j2", "hub_spoke.tf"))

    if cfg.enable_backend:
        files.append(("backend.tf.j2", "backend.tf"))

    files.extend(_shared_meta_files(cfg))
    return files


def _plan_modular(cfg: TerraGenConfig) -> List[tuple[str, str]]:
    """
    Modular layout (HashiCorp-style):
      modules/network/   VPC/VNet, security, optional hub-spoke
      modules/cluster/   EKS/GKE/AKS when enable_cluster (separate module)
      envs/<env>/        thin roots: main.tf calls network (+ cluster)
      bootstrap/         shared state backend
    """
    cloud = cfg.cloud
    mod = "modules/network"
    files: List[tuple[str, str]] = [
        # Network module - standard structure
        ("layout/module_versions.tf.j2", f"{mod}/terraform.tf"),
        ("variables.tf.j2", f"{mod}/variables.tf"),
        ("outputs.tf.j2", f"{mod}/outputs.tf"),
        (f"{cloud}/network.tf.j2", f"{mod}/main.tf"),
        (f"{cloud}/security.tf.j2", f"{mod}/security.tf"),
        ("gitignore.j2", ".gitignore"),
        ("README.md.j2", "README.md"),
    ]
    if cfg.enable_flow_logs or cfg.enable_billing_alerts or cfg.enable_guardduty:
        files.append((f"{cloud}/observability.tf.j2", f"{mod}/observability.tf"))

    # Cluster is a sibling module (not nested inside network)
    if cfg.enable_cluster:
        cmod = "modules/cluster"
        files.extend(
            [
                ("layout/module_versions.tf.j2", f"{cmod}/terraform.tf"),
                ("layout/cluster_variables.tf.j2", f"{cmod}/variables.tf"),
                (f"{cloud}/cluster.tf.j2", f"{cmod}/main.tf"),
            ]
        )

    if cfg.enable_hub_spoke:
        files.append((f"{cloud}/hub_spoke.tf.j2", f"{mod}/hub_spoke.tf"))

    # One root per environment (providers use baked values, not module vars)
    for env in cfg.env_list:
        prefix = f"envs/{env}"
        files.extend(
            [
                ("versions.tf.j2", f"{prefix}/terraform.tf"),
                ("layout/env_providers.tf.j2", f"{prefix}/providers.tf"),
                ("layout/env_main.tf.j2", f"{prefix}/main.tf"),
                ("layout/env_outputs.tf.j2", f"{prefix}/outputs.tf"),
                ("layout/env_tfvars.j2", f"{prefix}/terraform.tfvars"),
            ]
        )
        if cfg.enable_backend:
            files.append(("layout/env_backend.tf.j2", f"{prefix}/backend.tf"))

    files.extend(_shared_meta_files(cfg))
    return files


def _shared_meta_files(cfg: TerraGenConfig) -> List[tuple[str, str]]:
    files: List[tuple[str, str]] = []
    if cfg.enable_bootstrap and cfg.enable_backend:
        files.append((f"bootstrap/{cfg.cloud}.tf.j2", "bootstrap/main.tf"))
        files.append(("bootstrap/README.md.j2", "bootstrap/README.md"))

    if cfg.generate_policies:
        files.append(("policies/checkov.yaml.j2", "policy/checkov.yaml"))
        files.append(("policies/tflint.hcl.j2", "policy/.tflint.hcl"))

    if cfg.generate_ci:
        files.append(("cicd/github-actions.yml.j2", ".github/workflows/terraform.yml"))
        files.append(("cicd/gitlab-ci.yml.j2", ".gitlab-ci.yml"))

    if cfg.generate_oidc:
        files.append((f"oidc/{cfg.cloud}.tf.j2", "oidc/main.tf"))
        files.append(("oidc/README.md.j2", "oidc/README.md"))

    files.append(("answers.snapshot.yaml.j2", "terragen.answers.yaml"))
    return files


def _plan_files(cfg: TerraGenConfig) -> List[tuple[str, str]]:
    if cfg.is_modular:
        return _plan_modular(cfg)
    return _plan_flat(cfg)


def _render_one(
    env: Environment,
    tpl_name: str,
    target: Path,
    ctx: dict,
    result: RenderResult,
) -> None:
    try:
        tpl = env.get_template(tpl_name)
    except Exception as e:
        try:
            tpl = env.get_template(Path(tpl_name).name)
        except Exception as e2:
            raise RuntimeError(
                f"Template not found or unloadable: {tpl_name} ({e2})"
            ) from e2
    rendered = tpl.render(**ctx)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    result.files_written.append(target)


def render_project(
    cfg: TerraGenConfig,
    outdir: Path | str,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> RenderResult:
    """Render a full Terraform project for the given config."""
    import shutil

    outdir = Path(outdir)
    result = RenderResult(output_dir=outdir)

    # Always require --force to overwrite any non-empty directory (safer + consistent CLI).
    # On force, wipe the directory so renamed files (network.tf → main.tf) do not linger.
    if outdir.exists() and any(outdir.iterdir()) and not dry_run:
        marker = outdir / ".terragen-generated"
        if not force:
            if marker.exists():
                raise FileExistsError(
                    f"Output directory '{outdir}' already contains a TerraGen project. "
                    "Use --force to overwrite, or choose another --out path."
                )
            raise FileExistsError(
                f"Output directory '{outdir}' already exists and is not a TerraGen project. "
                "Use --force to overwrite, or choose another --out path."
            )
        shutil.rmtree(outdir)

    env = _build_env(
        [
            TEMPLATES_DIR / cfg.cloud,
            TEMPLATES_DIR / "bootstrap",
            TEMPLATES_DIR / "oidc",
            TEMPLATES_DIR / "layout",
        ]
    )
    plan = _plan_files(cfg)

    if dry_run:
        result.files_written = [outdir / rel for _, rel in plan]
        return result

    outdir.mkdir(parents=True, exist_ok=True)

    # Modular: network module (+ optional cluster module), then each env root
    if cfg.is_modular:
        primary_ctx = cfg.to_template_context()
        primary_ctx["render_scope"] = "module"
        primary_ctx["cluster_as_module"] = False
        for tpl_name, rel_path in plan:
            if rel_path.startswith("envs/") or rel_path.startswith("modules/cluster/"):
                continue
            _render_one(env, tpl_name, outdir / rel_path, primary_ctx, result)

        if cfg.enable_cluster:
            cluster_ctx = cfg.to_template_context()
            cluster_ctx["render_scope"] = "module_cluster"
            cluster_ctx["cluster_as_module"] = True
            for tpl_name, rel_path in plan:
                if not rel_path.startswith("modules/cluster/"):
                    continue
                _render_one(env, tpl_name, outdir / rel_path, cluster_ctx, result)

        for env_name in cfg.env_list:
            env_cfg = cfg.with_environment(env_name)
            env_ctx = env_cfg.to_template_context()
            env_ctx["render_scope"] = "env"
            env_ctx["cluster_as_module"] = False
            env_ctx["module_source"] = "../../modules/network"
            env_ctx["cluster_module_source"] = "../../modules/cluster"
            prefix = f"envs/{env_name}/"
            for tpl_name, rel_path in plan:
                if not rel_path.startswith(prefix):
                    continue
                _render_one(env, tpl_name, outdir / rel_path, env_ctx, result)
    else:
        ctx = cfg.to_template_context()
        ctx["render_scope"] = "flat"
        ctx["cluster_as_module"] = False
        for tpl_name, rel_path in plan:
            _render_one(env, tpl_name, outdir / rel_path, ctx, result)

    marker = outdir / ".terragen-generated"
    marker.write_text(
        json.dumps(
            {
                "generator": "TerraGen",
                "version": __import__("terragen").__version__,
                "cloud": cfg.cloud,
                "blueprint": cfg.blueprint,
                "project": cfg.project,
                "layout": cfg.layout,
                "environments": cfg.env_list,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result.files_written.append(marker)

    manifest = {
        "files": result.relative_files,
        "cloud": cfg.cloud,
        "blueprint": cfg.blueprint,
        "layout": cfg.layout,
        "environments": cfg.env_list,
        "cost_estimate": cfg.cost_estimate(),
    }
    man_path = outdir / "terragen.manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result.files_written.append(man_path)

    return result


def write_answers_example(path: Path, cfg: Optional[TerraGenConfig] = None) -> None:
    """Write a sample answers YAML file."""
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError("PyYAML required") from e

    if cfg is None:
        data = {
            "project": "demo-network",
            "cloud": "aws",
            "region": "us-east-1",
            "environment": "dev",
            "blueprint": "network",
            "layout": "flat",
            "vpc_cidr": "10.0.0.0/16",
            "az_count": 2,
            "nat_mode": "single",
            "enable_flow_logs": True,
            "enable_vpc_endpoints": False,
            "enable_interface_endpoints": False,
            "enable_backend": True,
            "enable_bootstrap": True,
            "generate_ci": True,
            "generate_policies": True,
            "generate_oidc": True,
            "owner": "platform-team",
            "tags": {"Team": "platform"},
        }
    else:
        data = cfg.to_answers_dict()

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
