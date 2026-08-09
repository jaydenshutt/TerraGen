"""Tests for init-answers --interactive (Q&A → answers YAML only)."""

from pathlib import Path
from unittest.mock import patch

import yaml

from terragen.cli import main
from terragen.config import TerraGenConfig
from terragen.render import write_answers_example
from terragen.validate import validate_config


def test_write_answers_from_config_roundtrip(tmp_path):
    cfg = TerraGenConfig.from_dict(
        {
            "project": "qa-demo",
            "cloud": "aws",
            "region": "us-west-2",
            "blueprint": "network-ha",
            "az_count": 2,
            "nat_mode": "per_az",
            "owner": "platform",
        }
    )
    path = tmp_path / "from-qa.yaml"
    write_answers_example(path, cfg)
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["project"] == "qa-demo"
    assert data["cloud"] == "aws"
    assert data["blueprint"] == "network-ha"
    loaded = TerraGenConfig.from_file(path)
    assert validate_config(loaded).ok
    assert loaded.region == "us-west-2"
    assert loaded.nat_mode == "per_az"


def test_init_answers_static(tmp_path):
    path = tmp_path / "sample.yaml"
    assert main(["init-answers", "--out", str(path)]) == 0
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "project" in data
    assert "cloud" in data


def test_init_answers_refuses_overwrite(tmp_path):
    path = tmp_path / "exists.yaml"
    path.write_text("project: x\n")
    assert main(["init-answers", "--out", str(path)]) == 1


def test_init_answers_interactive_mocked(tmp_path):
    path = tmp_path / "interactive.yaml"
    cfg = TerraGenConfig.from_dict(
        {
            "project": "wizard-app",
            "cloud": "gcp",
            "region": "us-central1",
            "blueprint": "network",
            "gcp_project_id": "billing-proj",
            "az_count": 2,
        }
    )
    with patch("terragen.cli.interactive_config", return_value=cfg) as mocked:
        rc = main(
            [
                "init-answers",
                "--interactive",
                "--out",
                str(path),
                "--force",
            ]
        )
    assert rc == 0
    mocked.assert_called_once()
    # answers_only=True
    assert mocked.call_args.kwargs.get("answers_only") is True
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["project"] == "wizard-app"
    assert data["cloud"] == "gcp"
    # No terraform project files next to it
    assert not (tmp_path / "main.tf").exists()
    assert not list(tmp_path.glob("*-terraform"))


def test_init_answers_interactive_cancel(tmp_path):
    path = tmp_path / "cancelled.yaml"
    with patch("terragen.cli.interactive_config", side_effect=SystemExit(0)):
        rc = main(["init-answers", "-i", "-o", str(path)])
    assert rc == 0
    assert not path.exists()
