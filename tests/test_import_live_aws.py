"""
Optional live AWS brownfield import — **read-only**.

Uses boto3 describe-* only (no Create/Update/Delete). Generates HCL locally
and optionally terraform-validates. Never runs terraform apply / plan against
the account.

Enable / select target:
  TERRAGEN_LIVE_AWS=1          force-run (skip only if no credentials)
  TERRAGEN_TEST_VPC_ID=vpc-…  optional explicit VPC
  AWS_DEFAULT_REGION / session region

Without credentials the tests skip cleanly so CI without secrets stays green.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.tf_helpers import terraform_binary, terraform_validate


def _aws_session_ready() -> tuple[bool, str]:
    """Return (ok, reason). ok means STS GetCallerIdentity succeeds."""
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except ImportError:
        return False, "boto3 not installed"

    try:
        session = boto3.Session()
        region = (
            os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or session.region_name
            or "us-east-1"
        )
        sts = session.client("sts", region_name=region)
        sts.get_caller_identity()
        return True, region
    except Exception as e:  # noqa: BLE001 — any creds failure → skip
        return False, f"AWS credentials unavailable: {type(e).__name__}: {e}"


def _pick_vpc_id(region: str) -> str:
    """Prefer env VPC, else first non-default VPC, else default VPC."""
    forced = os.environ.get("TERRAGEN_TEST_VPC_ID", "").strip()
    if forced:
        return forced

    import boto3

    ec2 = boto3.client("ec2", region_name=region)
    vpcs = ec2.describe_vpcs().get("Vpcs") or []
    if not vpcs:
        pytest.skip(f"No VPCs in region {region}")

    non_default = [v for v in vpcs if not v.get("IsDefault")]
    chosen = (non_default or vpcs)[0]
    return chosen["VpcId"]


@pytest.fixture(scope="module")
def live_aws_region() -> str:
    force = os.environ.get("TERRAGEN_LIVE_AWS", "").strip() in ("1", "true", "yes")
    ok, info = _aws_session_ready()
    if not ok:
        if force:
            pytest.fail(f"TERRAGEN_LIVE_AWS set but {info}")
        pytest.skip(info)
    return info  # region string when ok


def test_live_discover_aws_vpc_readonly(tmp_path, live_aws_region: str):
    """Deep-discover a real VPC (Describe* only) and emit import project."""
    from terragen.import_brownfield import discover_aws_vpc, generate_import_project

    vpc_id = _pick_vpc_id(live_aws_region)
    disc = discover_aws_vpc(vpc_id, live_aws_region)

    assert disc.cloud == "aws"
    assert disc.vpc_id == vpc_id
    assert disc.region == live_aws_region
    assert disc.vpc_cidr
    counts = disc.summary_counts()
    assert counts["subnets"] >= 1

    out = tmp_path / "live-import"
    files = generate_import_project(disc, out)
    assert (out / "imports.tf").exists()
    assert (out / "vpc.tf").exists()
    assert (out / "discovered.json").exists()
    assert vpc_id in (out / "imports.tf").read_text(encoding="utf-8")
    assert len(files) >= 6

    # Sanity: no apply was invoked — only local files
    assert not (out / "terraform.tfstate").exists()


@pytest.mark.terraform
def test_live_import_terraform_validate(tmp_path, live_aws_region: str):
    """Generated HCL from a live discovery must pass terraform validate."""
    if terraform_binary() is None:
        pytest.skip("terraform/tofu not on PATH")

    from terragen.import_brownfield import discover_aws_vpc, generate_import_project

    vpc_id = _pick_vpc_id(live_aws_region)
    disc = discover_aws_vpc(vpc_id, live_aws_region)
    out = tmp_path / "live-import-tf"
    generate_import_project(disc, out)
    terraform_validate(out, also_bootstrap=False)


def test_cli_import_live_dry_run(live_aws_region: str, capsys):
    """CLI import --dry-run prints inventory JSON without writing files."""
    from terragen.cli import main

    vpc_id = _pick_vpc_id(live_aws_region)
    rc = main(
        [
            "import",
            "--cloud",
            "aws",
            "--vpc-id",
            vpc_id,
            "--region",
            live_aws_region,
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert vpc_id in out
    assert '"cloud"' in out or "cloud" in out
