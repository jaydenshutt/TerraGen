"""Cost awareness helpers for generated architectures."""

from __future__ import annotations

from terragen.config import TerraGenConfig
from terragen.regions import estimate_nat_monthly_usd


def architecture_cost_report(cfg: TerraGenConfig, estimated_gb_out: float = 100.0) -> str:
    """Human-readable cost guidance for the selected architecture."""
    nat = estimate_nat_monthly_usd(
        cfg.cloud, cfg.az_count, cfg.nat_mode, estimated_gb_out
    )
    lines = [
        "Estimated recurring network costs (order-of-magnitude, USD/month):",
        f"  Cloud:        {cfg.cloud.upper()}",
        f"  NAT mode:     {cfg.nat_mode} ({nat['gateways']} gateway(s))",
        f"  Idle estimate:${nat['monthly_usd_low']:.2f}",
        f"  With ~{estimated_gb_out:.0f} GB egress: ~${nat['monthly_usd_high']:.2f}",
        f"  Note:         {nat['note']}",
        "",
        "Cost tips:",
    ]
    if cfg.nat_mode == "per_az":
        lines.append("  • Switch to nat_mode=single for non-production to cut idle NAT cost.")
    if not cfg.enable_vpc_endpoints and cfg.enable_nat:
        lines.append(
            "  • Enable VPC/gateway endpoints for object storage to reduce NAT data charges."
        )
    if cfg.nat_mode == "none" and cfg.cloud == "aws" and cfg.enable_interface_endpoints:
        lines.append(
            "  • Private-only + interface endpoints: no NAT idle cost; API traffic stays on AWS network."
        )
    if cfg.is_modular:
        lines.append(
            "  • Modular layout: apply per env under envs/<name> after bootstrap."
        )
    if cfg.az_count > 2 and cfg.environment in ("dev", "staging"):
        lines.append("  • Consider az_count=2 in non-prod unless you need full AZ symmetry.")
    if cfg.enable_flow_logs:
        lines.append("  • Flow logs incur small storage/ingestion costs — set retention intentionally.")
    if not any("Switch" in l or "Enable" in l or "Consider" in l for l in lines[-6:]):
        lines.append("  • Current layout looks cost-reasonable for its blueprint.")
    lines.append(
        "  • Always verify with the official cloud pricing calculator before budgeting."
    )
    return "\n".join(lines)
