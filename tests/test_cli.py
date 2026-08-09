"""CLI integration tests."""

import json
from pathlib import Path

import pytest

from terragen.cli import main


def test_version(capsys):
    assert main(["version"]) == 0
    out = capsys.readouterr().out
    assert "TerraGen" in out
    assert "Created by Jayden Shutt" in out


def test_blueprints(capsys):
    assert main(["blueprints"]) == 0
    out = capsys.readouterr().out
    assert "network" in out
    assert "network-secure" in out


def test_regions(capsys):
    assert main(["regions", "aws"]) == 0
    assert "us-east-1" in capsys.readouterr().out


def test_init_answers(tmp_path):
    path = tmp_path / "answers.yaml"
    assert main(["init-answers", "--out", str(path)]) == 0
    assert path.exists()


def test_validate_ok(tmp_path, capsys):
    p = tmp_path / "a.yaml"
    p.write_text(
        "project: demo-cli\ncloud: aws\nregion: us-east-1\nvpc_cidr: 10.0.0.0/16\naz_count: 2\n"
    )
    assert main(["validate", "--answers", str(p)]) == 0


def test_validate_bad(tmp_path):
    p = tmp_path / "a.yaml"
    p.write_text("project: demo-cli\ncloud: nope\n")
    assert main(["validate", "--answers", str(p)]) == 1


def test_generate_noninteractive(tmp_path):
    out = tmp_path / "proj"
    rc = main(
        [
            "generate",
            "--non-interactive",
            "--project",
            "demo-cli",
            "--cloud",
            "aws",
            "--region",
            "us-east-1",
            "--out",
            str(out),
            "--force",
        ]
    )
    assert rc == 0
    assert (out / "main.tf").exists()
    assert (out / "terraform.tf").exists()


def test_generate_from_answers(tmp_path):
    answers = tmp_path / "ans.json"
    answers.write_text(
        json.dumps(
            {
                "project": "from-json",
                "cloud": "gcp",
                "region": "us-central1",
                "gcp_project_id": "proj-123",
                "az_count": 2,
            }
        )
    )
    out = tmp_path / "gcp-out"
    assert main(["generate", "--answers", str(answers), "--out", str(out), "--force"]) == 0
    assert (out / "main.tf").exists()
    assert "google_compute_network" in (out / "main.tf").read_text()


def test_dry_run(tmp_path, capsys):
    out = tmp_path / "dry"
    rc = main(
        [
            "generate",
            "--non-interactive",
            "--project",
            "dry-run-proj",
            "--cloud",
            "azure",
            "--out",
            str(out),
            "--dry-run",
        ]
    )
    assert rc == 0
    assert not out.exists()
    assert "dry-run" in capsys.readouterr().out.lower()


def test_cost(capsys):
    assert main(["cost", "--cloud", "aws", "--nat-mode", "per_az", "--az-count", "3"]) == 0
    assert "NAT" in capsys.readouterr().out or "nat" in capsys.readouterr().out.lower()
