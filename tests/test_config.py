"""Tests for TerraGenConfig model."""

from terragen.config import TerraGenConfig


def test_legacy_enable_nat():
    cfg = TerraGenConfig.from_dict(
        {"project": "demo-app", "cloud": "aws", "enable_nat": False}
    )
    assert cfg.nat_mode == "none"
    assert cfg.enable_nat is False


def test_blueprint_ha_forces_nat():
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-app",
            "cloud": "aws",
            "blueprint": "network-ha",
            "nat_mode": "single",
            "az_count": 1,
        }
    )
    assert cfg.nat_mode == "per_az"
    assert cfg.az_count >= 2
    assert cfg.enable_vpc_endpoints is True


def test_blueprint_secure_guardduty():
    cfg = TerraGenConfig.from_dict(
        {"project": "demo-app", "cloud": "aws", "blueprint": "network-secure"}
    )
    assert cfg.enable_guardduty is True
    assert cfg.enable_flow_logs is True


def test_tags_merged():
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-app",
            "cloud": "aws",
            "owner": "alice",
            "tags": {"Team": "platform"},
        }
    )
    assert cfg.tags["Project"] == "demo-app"
    assert cfg.tags["Owner"] == "alice"
    assert cfg.tags["Team"] == "platform"
    assert cfg.tags["ManagedBy"] == "TerraGen"


def test_state_names():
    cfg = TerraGenConfig.from_dict(
        {"project": "demo-app", "cloud": "aws", "environment": "prod"}
    )
    assert "demo-app" in cfg.state_bucket_name
    assert "prod" in cfg.state_bucket_name
    assert "tf-lock" in cfg.state_lock_table


def test_azure_storage_account_length():
    cfg = TerraGenConfig.from_dict(
        {"project": "demo-azure", "cloud": "azure", "environment": "dev"}
    )
    assert 3 <= len(cfg.azure_storage_account) <= 24
    assert cfg.azure_storage_account.isalnum()


def test_to_template_context():
    cfg = TerraGenConfig.from_dict({"project": "demo-app", "cloud": "gcp"})
    ctx = cfg.to_template_context()
    assert ctx["enable_nat"] is True
    assert "public_subnets" in ctx
    assert ctx["gcp_project"]


def test_cost_estimate():
    cfg = TerraGenConfig.from_dict(
        {"project": "demo-app", "cloud": "aws", "nat_mode": "per_az", "az_count": 2}
    )
    est = cfg.cost_estimate()
    assert est["gateways"] == 2
    assert est["monthly_usd_low"] > 0
