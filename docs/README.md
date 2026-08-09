# TerraGen documentation

User-facing guides for installing, generating, deploying, and adopting Terraform with TerraGen.

| Guide | Description |
|-------|-------------|
| [Getting started](getting-started.md) | Install, first generate, first `terraform plan` |
| [Interactive mode](interactive-mode.md) | Wizard questions explained end-to-end |
| [Answers files](answers-file.md) | YAML/JSON schema, examples, automation |
| [Blueprints](blueprints.md) | Network, private, 3-tier, K8s-ready, clusters, hub-spoke |
| [Layouts](layouts.md) | Flat vs modular project structure |
| [Remote state & bootstrap](bootstrap-and-state.md) | Backend config and one-time state resources |
| [Brownfield import](brownfield-import.md) | Bring an existing AWS VPC under Terraform |
| [Clusters](clusters.md) | EKS / GKE / AKS full stack notes |
| [Hub-and-spoke](hub-spoke.md) | Multi-VPC topology |
| [CLI reference](cli-reference.md) | All commands and common flags |
| [Troubleshooting](troubleshooting.md) | Common errors and fixes |
| [Architecture](ARCHITECTURE.md) | How the generator is built (contributors) |

**Quick path:** [Getting started](getting-started.md) → pick a [blueprint](blueprints.md) → [bootstrap state](bootstrap-and-state.md) → `terraform apply`.

Also see the root [README](../README.md) and [examples/](../examples/).

### Disclaimer

TerraGen is provided **as-is**, **without warranty**, and is used **at your own risk**. Authors accept **no responsibility** for cloud cost, outages, or security outcomes. Review every plan before apply. We hope it still helps you move faster—see [README — Disclaimer](../README.md#disclaimer), [Getting started](getting-started.md#disclaimer-read-before-you-apply), and [LICENSE](../LICENSE).
