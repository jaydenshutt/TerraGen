# Troubleshooting

## `terragen` not found

Use the module form:

```bash
python -m terragen version
```

Or install editable and ensure Scripts are on PATH:

```bash
python -m pip install -e .
```

## Generation fails: output directory exists

```
FileExistsError: ... not a TerraGen project
```

- Use a new `--out` path, or  
- `--force` only if the folder has `.terragen-generated` (TerraGen project) or you accept overwrite of a marked project.

## Validation errors on project name

Use a slug: lowercase letters, digits, hyphens; start with a letter (e.g. `my-app`, not `My App`).

## `terraform init` backend errors

State bucket/table missing:

1. Apply `bootstrap/` first ([guide](bootstrap-and-state.md))  
2. Or `terraform init -backend=false` for local experiments  
3. Or regenerate with `--no-backend`

## GCP: wrong project / API not enabled

Set `gcp_project_id` to your real billing project. Enable Compute / container APIs as needed for GKE.

## Azure: storage account name invalid

Derived names must be 3–24 alphanumeric. Shorten `project` / `environment`.

## Plan shows huge NAT cost

- Prefer `nat_mode: single` in non-prod  
- Or `nat_mode: none` / `network-private`  
- Use `python -m terragen cost --cloud aws --nat-mode per_az --az-count 3`

## Import: boto3 missing

```bash
pip install boto3
```

Or use `--inventory` without live AWS access.

## Import: large plan after first import

Normal for brownfield. Align tags, SG rules, and optional attributes; re-plan. See [brownfield import](brownfield-import.md).

## Modular: where do I apply?

```bash
cd envs/dev   # not repo root
terraform init
terraform plan
```

## Still stuck

```bash
python -m terragen doctor
python -m terragen validate -a answers.yaml
```

Open an issue on GitHub with: OS, Python version, command used, and full error text (redact secrets).
