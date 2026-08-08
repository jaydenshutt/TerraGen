# Contributing to TerraGen

Thanks for helping improve TerraGen.

## Development setup

```bash
git clone https://github.com/jaydenshutt/TerraGen.git
cd TerraGen
python -m pip install -e ".[dev]"
pytest -q
```

## Project layout

| Path | Role |
|------|------|
| `terragen/` | Python package (CLI, config, render, validation) |
| `terragen/templates/` | Jinja2 Terraform templates (common + per cloud) |
| `examples/` | Sample answers files |
| `tests/` | Unit and render tests |

## Adding a feature

1. Extend `TerraGenConfig` in `config.py` if new answers are needed
2. Validate in `validate.py`
3. Update templates under `terragen/templates/`
4. Add/adjust tests (prefer golden render checks)
5. Update `README.md` / `examples/` when the public schema changes

## Template rules

- Never emit dual-column / merged garbage — each line must be valid HCL or Jinja
- Prefer Terraform `count` / `for_each` and variables over hard-coding CIDRs in resources
- Keep cloud-specific resources in `aws/`, `gcp/`, `azure/`
- Shared files live in `common/`

## Running generation smoke tests

```bash
terragen generate --answers examples/answers-aws.yaml --out /tmp/tg-aws --force
# If Terraform is installed:
cd /tmp/tg-aws && terraform init -backend=false && terraform validate
```

## Pull requests

- Keep PRs focused
- Include tests for behavior changes
- Do not commit generated `tmp-gen/` or local state files
