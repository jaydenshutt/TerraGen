"""JSON Schema for TerraGen answers files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from terragen.config import (
    ENVIRONMENTS,
    LAYOUTS,
    NAT_MODES,
    SUPPORTED_BLUEPRINTS,
    SUPPORTED_CLOUDS,
)


def answers_schema() -> Dict[str, Any]:
    """Return JSON Schema (draft 2020-12) for answers files."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/jaydenshutt/TerraGen/schemas/answers.schema.json",
        "title": "TerraGen Answers",
        "description": "Configuration for generating a multi-cloud Terraform network project",
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "project": {
                "type": "string",
                "pattern": "^[a-z][a-z0-9-]{1,38}[a-z0-9]$",
                "description": "Project slug used for resource naming",
            },
            "cloud": {"type": "string", "enum": list(SUPPORTED_CLOUDS)},
            "region": {"type": "string", "minLength": 1},
            "environment": {"type": "string"},
            "environments": {
                "oneOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "string"},
                ],
                "description": "Modular layout: list of env roots to generate",
            },
            "blueprint": {"type": "string", "enum": list(SUPPORTED_BLUEPRINTS)},
            "layout": {"type": "string", "enum": list(LAYOUTS)},
            "vpc_cidr": {"type": "string"},
            "az_count": {"type": "integer", "minimum": 1, "maximum": 6},
            "public_subnets": {"type": "array", "items": {"type": "string"}},
            "private_subnets": {"type": "array", "items": {"type": "string"}},
            "nat_mode": {"type": "string", "enum": list(NAT_MODES)},
            "private_only": {
                "type": "boolean",
                "description": "Shorthand: nat_mode=none + no public subnets + endpoints",
            },
            "create_public_subnets": {"type": "boolean"},
            "enable_flow_logs": {"type": "boolean"},
            "enable_vpc_endpoints": {"type": "boolean"},
            "enable_interface_endpoints": {"type": "boolean"},
            "interface_endpoints": {"type": "array", "items": {"type": "string"}},
            "enable_bastion_sg": {"type": "boolean"},
            "ssh_cidrs": {"type": "array", "items": {"type": "string"}},
            "enable_guardduty": {"type": "boolean"},
            "enable_nsg_defaults": {"type": "boolean"},
            "enable_billing_alerts": {"type": "boolean"},
            "billing_thresholds": {
                "type": "object",
                "additionalProperties": {"type": "number"},
            },
            "alert_emails": {"type": "array", "items": {"type": "string", "format": "email"}},
            "enable_backend": {"type": "boolean"},
            "enable_bootstrap": {"type": "boolean"},
            "generate_ci": {"type": "boolean"},
            "generate_policies": {"type": "boolean"},
            "generate_oidc": {"type": "boolean"},
            "github_org": {"type": "string"},
            "github_repo": {"type": "string"},
            "owner": {"type": "string"},
            "cost_center": {"type": "string"},
            "gcp_project_id": {"type": "string"},
            "azure_subscription_id": {"type": "string"},
            "tags": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        "required": [],
        "examples": [
            {
                "project": "demo-aws",
                "cloud": "aws",
                "region": "us-east-1",
                "environment": "dev",
                "blueprint": "network",
                "layout": "modular",
                "environments": ["dev", "staging", "prod"],
                "vpc_cidr": "10.0.0.0/16",
                "az_count": 2,
                "nat_mode": "single",
            }
        ],
    }


def write_schema(path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(answers_schema(), indent=2) + "\n", encoding="utf-8")
    return path
