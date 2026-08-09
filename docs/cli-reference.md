# CLI reference

All commands work as:

```bash
python -m terragen <command> [options]
# or, if on PATH:
terragen <command> [options]
```

**Credentials:** most commands are local. Cloud auth is needed for `bootstrap` apply, live `import`, and for `terraform plan`/`apply` on generated code — [Cloud credentials](cloud-credentials.md).

## Commands

| Command | Description |
|---------|-------------|
| `generate` | Generate a Terraform project (default if only flags given) |
| `bootstrap` | Init/plan/apply remote-state bootstrap stack |
| `import` | Brownfield: inventory (AWS/GCP/Azure) or live AWS VPC → import project |
| `validate` | Validate an answers file |
| `doctor` | Check Python deps, templates, Terraform, CLIs |
| `schema` | Print or write JSON Schema for answers |
| `blueprints` | List blueprints |
| `blueprint <id>` | Describe one blueprint |
| `regions <cloud>` | List curated regions |
| `cost` | Rough NAT monthly cost estimate |
| `init-answers` | Write answers YAML (sample **or** interactive Q&A only) |
| `version` | Show version |

## `generate` flags (common)

| Flag | Meaning |
|------|---------|
| `-a` / `--answers` | YAML/JSON answers file |
| `-o` / `--out` | Output directory |
| `-f` / `--force` | Overwrite TerraGen project |
| `--dry-run` | Show plan of files only |
| `--non-interactive` | No prompts |
| `--project` | Project name |
| `--cloud` | `aws` \| `gcp` \| `azure` |
| `--region` | Region |
| `--environment` | e.g. `dev` |
| `--environments` | Comma list for modular |
| `--blueprint` | Blueprint id |
| `--layout` | `flat` \| `modular` |
| `--vpc-cidr` | CIDR |
| `--az-count` | AZ count |
| `--nat-mode` | `none` \| `single` \| `per_az` |
| `--private-only` | Private-focused network |
| `--ipv6` | Dual-stack |
| `--spoke-count` | Hub-spoke spokes |
| `--interface-endpoints` | AWS interface endpoints pack |
| `--no-backend` | Skip backend/bootstrap files |
| `--no-ci` / `--no-policies` / `--no-oidc` | Skip extras |
| `--validate` | Run terraform/tofu validate after generate |
| `--github-org` / `--github-repo` | OIDC subjects |
| `--gcp-project-id` | GCP billing project |

## `import` flags

| Flag | Meaning |
|------|---------|
| `-i` / `--inventory` | JSON inventory (AWS / GCP / Azure) — **no cloud account required** |
| `--cloud aws` | Live discovery (AWS only today) |
| `--vpc-id` | AWS VPC id (live path) |
| `--region` | Region for live discovery |
| `-o` / `--out` | Output directory |
| `--dry-run` | Print inventory JSON only (live path) |

See [brownfield-import.md](brownfield-import.md) for inventory schemas and samples.

## `bootstrap` flags

| Flag | Meaning |
|------|---------|
| `-d` / `--project-dir` | Existing generated project |
| `-a` / `--answers` | Generate then bootstrap |
| `--binary` | `terraform` or `tofu` |
| `--auto-approve` | Apply without prompt |
| `--dry-run` | Print intended commands |

## `init-answers` flags

| Flag | Meaning |
|------|---------|
| `-o` / `--out` | Output path (default `answers.yaml`) |
| `-f` / `--force` | Overwrite existing file |
| `-i` / `--interactive` | Run Q&A wizard; write answers only (no Terraform project) |

## Examples

```bash
python -m terragen doctor
python -m terragen blueprints
python -m terragen init-answers -i -o answers.yaml          # Q&A → answers only
python -m terragen generate -a answers.yaml -o ./n --force
python -m terragen generate -a examples/answers-aws.yaml -o ./n --force --validate
python -m terragen import -i examples/inventory-aws-sample.json -o ./imp-aws
python -m terragen import -i examples/inventory-gcp-sample.json -o ./imp-gcp
python -m terragen import -i examples/inventory-azure-sample.json -o ./imp-az
python -m terragen cost --cloud aws --nat-mode per_az --az-count 3
```
