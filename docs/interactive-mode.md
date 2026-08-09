# Interactive mode

```bash
python -m terragen generate
```

With no answers file and no major flags, TerraGen runs a guided wizard.

## What to expect

1. **Sections** with short plain-language help above each question  
2. **Progress** markers like `[3/18]`  
3. Defaults in `[brackets]` - press Enter to accept  
4. A **summary** of cloud, blueprint, CIDRs, NAT, features, and rough NAT cost  
5. Confirm **Generate files with these settings?** before anything is written  
6. **Ctrl+C** cancels cleanly  

## Question groups

| Section | What you set |
|---------|----------------|
| Project basics | Name, cloud (aws/gcp/azure), region, environment |
| Layout | `flat` or `modular`; multi-env list if modular |
| Blueprint | Opinionated preset (network, private, eks-cluster, hub-spoke, …) |
| Network size | VPC CIDR, number of AZs |
| Internet access | Private-only vs NAT mode (`none` / `single` / `per_az`) |
| Logging & endpoints | Flow logs, gateway endpoints, interface endpoints (AWS) |
| Security | Bastion SG, SSH CIDRs, GuardDuty (AWS), billing alerts |
| Tags | Owner, cost center |
| Cloud-specific | GCP project ID, Azure subscription |
| GitHub | Org/repo for OIDC subjects |
| Packaging | Backend, bootstrap, CI, policies, OIDC stack |
| Advanced | IPv6 dual-stack; spoke count if hub-spoke |

## Answers file only (no Terraform)

To capture Q&A answers without generating a project:

```bash
python -m terragen init-answers --interactive --out answers.yaml
```

Same wizard and summary; writes only the YAML. Then:

```bash
python -m terragen generate --answers answers.yaml --out ./my-network --force
```

## Tips

- Start with blueprint **`network`** and NAT **`single`** for a balanced first deploy.  
- Use **`network-private`** if you want no public subnets (AWS gets interface endpoints automatically).  
- Prefer **`modular`** only if you already know you want multiple env roots.  
- After a full `generate`, re-use `terragen.answers.yaml` for non-interactive runs.  
- Prefer `init-answers --interactive` when you only need the answers file.

See also: [Answers files](answers-file.md), [Blueprints](blueprints.md).
