#!/usr/bin/env python3
"""
TerraGen - beginner-friendly, cloud-agnostic Terraform project generator (AWS, GCP, Azure)

Created by Jayden Shutt

This script asks a few questions about the desired network layout and security
settings and renders Terraform files into an output directory using Jinja2 templates.

Usage:
    python TerraGen.py                      # interactive
    python TerraGen.py --answers answers.json  # non-interactive (JSON/YAML file)
"""
import argparse
import json
import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import ipaddress
from typing import List, Tuple

TEMPLATES_DIR = Path(__file__).parent / "templates"


def ask(prompt, default=None):
    """Helper to prompt user for input with a default."""
    if default:
        resp = input(f"{prompt} [{default}]: ")
        return resp.strip() or default
    return input(f"{prompt}: ").strip()


def interactive_questions():
    """Guide user through creating a configuration."""
    print("Welcome to TerraGen — Terraform starter generator for AWS, GCP, or Azure")
    project = ask("Project name", "my-cloud-project")
    cloud = ask("Cloud provider (aws, gcp, azure)", "aws")
    region = ask("Cloud region/location (e.g., us-east-1, us-central1, eastus)", "us-east-1")
    vpc_cidr = ask("Network CIDR block", "10.0.0.0/16")
    az_count = int(ask("Number of availability zones (2 or 3 recommended)", "2"))
    
    answers = {
        "project": project,
        "cloud": cloud.lower(),
        "region": region,
        "vpc_cidr": vpc_cidr,
        "az_count": az_count,
        "tags": {"Project": project},
        "backend": True,  # Always configure backend
    }
    return answers


def load_answers(path):
    """Load answers from a JSON or YAML file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            raise ValueError("PyYAML is required to parse YAML answer files. Please install it.")
        except Exception as e:
            raise ValueError(f"Unable to parse answers file as JSON or YAML: {path}") from e


def render_templates(answers, outdir: Path):
    """Render Jinja2 templates to the output directory."""
    cloud = answers.get('cloud', 'aws')
    
    # The loader will now look in the base templates/ dir and the cloud-specific one
    template_paths = [TEMPLATES_DIR, TEMPLATES_DIR / cloud]
    env = Environment(
        loader=FileSystemLoader([str(p) for p in template_paths]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    outdir.mkdir(parents=True, exist_ok=True)

    # Common templates
    templates_to_render = ["main.tf.j2", "variables.tf.j2", "outputs.tf.j2", "README.md.j2"]
    
    # Always render backend.tf, as we've simplified the logic
    templates_to_render.append("backend.tf.j2")

    for tpl_name in templates_to_render:
        try:
            tpl = env.get_template(tpl_name)
            rendered = tpl.render(**answers)
            target = outdir / tpl_name.replace('.j2', '')
            with open(target, "w", encoding="utf-8") as f:
                f.write(rendered)
        except Exception as e:
            print(f"Warning: Could not render template {tpl_name}. Skipping. Error: {e}")

    print(f"Generated Terraform configuration in: {outdir}")


def compute_subnet_cidrs(vpc_cidr: str, az_count: int) -> Tuple[List[str], List[str]]:
    """Divide the VPC CIDR into public and private subnets for each AZ."""
    net = ipaddress.ip_network(vpc_cidr)
    
    # We need 2 subnets per AZ (1 public, 1 private)
    total_subnets = az_count * 2
    
    # Calculate the prefix length needed to accommodate all subnets
    new_prefix = net.prefixlen + (total_subnets - 1).bit_length()
    if new_prefix > 28: # Don't create subnets smaller than /28
        new_prefix = 28

    if new_prefix > net.max_prefixlen:
        raise ValueError("VPC CIDR is too small to be subdivided into the required number of subnets.")

    subnets = list(net.subnets(new_prefix=new_prefix))

    public_cidrs = []
    private_cidrs = []
    for i in range(az_count):
        public_cidrs.append(str(subnets[i * 2]))
        private_cidrs.append(str(subnets[i * 2 + 1]))

    return public_cidrs, private_cidrs


def main():
    parser = argparse.ArgumentParser(description="Cloud-agnostic Terraform starter generator (AWS, GCP, Azure)")
    parser.add_argument("--answers", help="Path to a JSON or YAML file with answers for non-interactive runs.")
    parser.add_argument("--out", help="Output directory for the generated Terraform files.")
    args = parser.parse_args()

    if args.answers:
        answers = load_answers(args.answers)
    else:
        answers = interactive_questions()

    outdir = Path(args.out) if args.out else Path.cwd() / f"{answers.get('project', 'my-project')}-terraform"

    # Ensure 'cloud' key exists
    if 'cloud' not in answers:
        answers['cloud'] = 'aws' # Default to AWS

    # Compute subnet CIDRs
    try:
        public_cidrs, private_cidrs = compute_subnet_cidrs(answers["vpc_cidr"], answers["az_count"])
        answers["public_subnets"] = public_cidrs
        answers["private_subnets"] = private_cidrs
    except (ValueError, KeyError) as e:
        print(f"Error: Could not compute subnet CIDRs. Please check your configuration. Details: {e}")
        return

    # Render the templates
    render_templates(answers, outdir)
    
    print("\nNext steps:")
    print(f"1. cd {outdir}")
    print("2. Review the generated *.tf files.")
    print("3. Run 'terraform init' to initialize the project.")
    print("4. Run 'terraform plan' to see the execution plan.")
    print("5. Run 'terraform apply' to deploy your infrastructure.")


if __name__ == "__main__":
    main()