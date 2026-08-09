"""Generated CI and OIDC packaging correctness (GitHub Actions expressions, etc.)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from terragen.config import TerraGenConfig
from terragen.render import render_project
from terragen.validate import validate_config

# Raw Jinja must not survive into rendered CI YAML
_JINJA_LEFT = re.compile(r"(?<!\$)\{\{")
_JINJA_BLOCK = re.compile(r"\{%")


@pytest.mark.parametrize("cloud", ["aws", "gcp", "azure"])
@pytest.mark.parametrize("layout", ["flat", "modular"])
def test_github_actions_yaml_expressions(tmp_path, cloud: str, layout: str):
    """
    Generated workflow must use real GHA ${{ }} expressions (not leftover Jinja)
    and include cloud-appropriate OIDC login scaffolding.
    """
    data = {
        "project": f"ci-{cloud}-{layout[:3]}",
        "cloud": cloud,
        "region": {"aws": "us-east-1", "gcp": "us-central1", "azure": "eastus"}[cloud],
        "layout": layout,
        "environments": ["dev", "prod"] if layout == "modular" else [],
        "environment": "dev",
        "blueprint": "network",
        "generate_ci": True,
        "generate_oidc": True,
        "github_org": "example-org",
        "github_repo": "example-repo",
        "az_count": 2,
    }
    if cloud == "gcp":
        data["gcp_project_id"] = "billing-proj"

    cfg = TerraGenConfig.from_dict(data)
    assert validate_config(cfg).ok, validate_config(cfg).errors
    out = tmp_path / f"{cloud}-{layout}"
    render_project(cfg, out, force=True)

    gha = out / ".github" / "workflows" / "terraform.yml"
    assert gha.exists(), "GitHub Actions workflow missing"
    text = gha.read_text(encoding="utf-8")

    # No unrendered Jinja
    assert _JINJA_BLOCK.search(text) is None, "leftover {% %} in GHA YAML"
    assert _JINJA_LEFT.search(text) is None, (
        "leftover {{ }} without $ - Jinja leaked into GHA YAML:\n" + text[:500]
    )

    # Valid GHA expression for working directory
    assert "${{ env.TF_WORKING_DIR }}" in text
    if layout == "modular":
        assert "TF_WORKING_DIR: envs/dev" in text or "TF_WORKING_DIR: envs/" in text
    else:
        assert "TF_WORKING_DIR: ." in text

    # OIDC / cloud login secrets use ${{ secrets.* }}
    if cloud == "aws":
        assert "aws-actions/configure-aws-credentials" in text
        assert "${{ secrets.AWS_ROLE_ARN }}" in text
        assert "us-east-1" in text or cfg.region in text
    elif cloud == "gcp":
        assert "google-github-actions/auth" in text
        assert "${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}" in text
        assert "${{ secrets.GCP_SERVICE_ACCOUNT }}" in text
    elif cloud == "azure":
        assert "azure/login" in text
        assert "${{ secrets.AZURE_CLIENT_ID }}" in text
        assert "${{ secrets.AZURE_TENANT_ID }}" in text
        assert "${{ secrets.AZURE_SUBSCRIPTION_ID }}" in text

    assert "id-token: write" in text
    assert "terraform validate" in text or "Terraform Validate" in text

    # GitLab stub also emitted
    assert (out / ".gitlab-ci.yml").exists()


@pytest.mark.parametrize("cloud", ["aws", "gcp", "azure"])
def test_oidc_stack_rendered(tmp_path, cloud: str):
    data = {
        "project": f"oidc-{cloud}",
        "cloud": cloud,
        "region": {"aws": "us-east-1", "gcp": "us-central1", "azure": "eastus"}[cloud],
        "generate_oidc": True,
        "github_org": "example-org",
        "github_repo": "example-repo",
        "az_count": 2,
    }
    if cloud == "gcp":
        data["gcp_project_id"] = "billing-proj"
    cfg = TerraGenConfig.from_dict(data)
    out = tmp_path / cloud
    render_project(cfg, out, force=True)
    oidc = out / "oidc" / "main.tf"
    assert oidc.exists()
    body = oidc.read_text(encoding="utf-8")
    assert _JINJA_BLOCK.search(body) is None
    assert "example-org" in body or "example-repo" in body or "github" in body.lower()


def test_ci_disabled_skips_workflows(tmp_path):
    cfg = TerraGenConfig.from_dict(
        {
            "project": "no-ci",
            "cloud": "aws",
            "generate_ci": False,
            "generate_oidc": False,
            "az_count": 2,
        }
    )
    out = tmp_path / "out"
    render_project(cfg, out, force=True)
    assert not (out / ".github" / "workflows" / "terraform.yml").exists()
    assert not (out / "oidc" / "main.tf").exists()
