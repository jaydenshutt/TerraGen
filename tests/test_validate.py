"""Tests for configuration validation."""

import pytest

from terragen.config import TerraGenConfig
from terragen.validate import validate_config


def test_valid_minimal():
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-app",
            "cloud": "aws",
            "region": "us-east-1",
            "vpc_cidr": "10.0.0.0/16",
            "az_count": 2,
        }
    )
    result = validate_config(cfg)
    assert result.ok


def test_invalid_cloud():
    cfg = TerraGenConfig.from_dict({"project": "demo-app", "cloud": "digitalocean"})
    result = validate_config(cfg)
    assert not result.ok
    assert any("Unsupported cloud" in e for e in result.errors)


def test_invalid_project_name():
    cfg = TerraGenConfig.from_dict({"project": "A", "cloud": "aws"})
    # slug may normalize; force bad after construct
    cfg.project = "Bad_Name!"
    result = validate_config(cfg)
    assert not result.ok


def test_unknown_region_warns():
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-app",
            "cloud": "aws",
            "region": "mars-east-1",
        }
    )
    result = validate_config(cfg)
    assert result.ok
    assert any("not in TerraGen" in w for w in result.warnings)


def test_bad_email():
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-app",
            "cloud": "aws",
            "enable_billing_alerts": True,
            "alert_emails": ["not-an-email"],
        }
    )
    result = validate_config(cfg)
    assert not result.ok


def test_ssh_open_world_warns():
    cfg = TerraGenConfig.from_dict(
        {
            "project": "demo-app",
            "cloud": "aws",
            "enable_bastion_sg": True,
            "ssh_cidrs": ["0.0.0.0/0"],
        }
    )
    result = validate_config(cfg)
    assert result.ok
    assert any("0.0.0.0/0" in w for w in result.warnings)


def test_raise_if_errors():
    cfg = TerraGenConfig.from_dict({"project": "demo-app", "cloud": "nope"})
    result = validate_config(cfg)
    with pytest.raises(ValueError):
        result.raise_if_errors()
