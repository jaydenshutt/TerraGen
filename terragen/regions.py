"""Well-known region catalogs and validation helpers."""

from __future__ import annotations

from typing import Dict, List, Optional

# Curated common regions - not exhaustive, but covers typical defaults.
# Used for interactive suggestions and soft validation (warnings, not hard fails).

AWS_REGIONS: Dict[str, str] = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "ca-central-1": "Canada (Central)",
    "eu-west-1": "Europe (Ireland)",
    "eu-west-2": "Europe (London)",
    "eu-west-3": "Europe (Paris)",
    "eu-central-1": "Europe (Frankfurt)",
    "eu-north-1": "Europe (Stockholm)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-northeast-2": "Asia Pacific (Seoul)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "sa-east-1": "South America (São Paulo)",
    "af-south-1": "Africa (Cape Town)",
    "me-south-1": "Middle East (Bahrain)",
}

GCP_REGIONS: Dict[str, str] = {
    "us-central1": "Iowa",
    "us-east1": "South Carolina",
    "us-east4": "Northern Virginia",
    "us-west1": "Oregon",
    "us-west2": "Los Angeles",
    "europe-west1": "Belgium",
    "europe-west2": "London",
    "europe-west3": "Frankfurt",
    "europe-west4": "Netherlands",
    "europe-north1": "Finland",
    "asia-east1": "Taiwan",
    "asia-northeast1": "Tokyo",
    "asia-southeast1": "Singapore",
    "asia-south1": "Mumbai",
    "australia-southeast1": "Sydney",
    "southamerica-east1": "São Paulo",
}

AZURE_LOCATIONS: Dict[str, str] = {
    "eastus": "East US",
    "eastus2": "East US 2",
    "westus": "West US",
    "westus2": "West US 2",
    "westus3": "West US 3",
    "centralus": "Central US",
    "northeurope": "North Europe",
    "westeurope": "West Europe",
    "uksouth": "UK South",
    "ukwest": "UK West",
    "francecentral": "France Central",
    "germanywestcentral": "Germany West Central",
    "japaneast": "Japan East",
    "japanwest": "Japan West",
    "southeastasia": "Southeast Asia",
    "eastasia": "East Asia",
    "australiaeast": "Australia East",
    "brazilsouth": "Brazil South",
    "canadacentral": "Canada Central",
    "uaenorth": "UAE North",
}

REGION_CATALOGS = {
    "aws": AWS_REGIONS,
    "gcp": GCP_REGIONS,
    "azure": AZURE_LOCATIONS,
}

DEFAULT_REGIONS = {
    "aws": "us-east-1",
    "gcp": "us-central1",
    "azure": "eastus",
}

# Approximate monthly NAT costs (USD) for rough guidance - not quotes.
# Sources: public pricing pages as of 2025; always verify with the cloud calculator.
NAT_COST_HINTS = {
    "aws": {
        "gateway_hourly": 0.045,
        "data_per_gb": 0.045,
        "note": "NAT Gateway ~$32/mo idle + data processing per AZ",
    },
    "gcp": {
        "gateway_hourly": 0.044,
        "data_per_gb": 0.045,
        "note": "Cloud NAT gateway + data processing charges apply",
    },
    "azure": {
        "gateway_hourly": 0.045,
        "data_per_gb": 0.045,
        "note": "NAT Gateway resource + data processed charges apply",
    },
}


def list_regions(cloud: str) -> List[dict]:
    """Return [{code, name}, ...] for a cloud."""
    catalog = REGION_CATALOGS.get(cloud.lower(), {})
    return [{"code": k, "name": v} for k, v in catalog.items()]


def is_known_region(cloud: str, region: str) -> bool:
    return region in REGION_CATALOGS.get(cloud.lower(), {})


def suggest_regions(cloud: str, limit: int = 8) -> List[str]:
    catalog = REGION_CATALOGS.get(cloud.lower(), {})
    return list(catalog.keys())[:limit]


def default_region(cloud: str) -> str:
    return DEFAULT_REGIONS.get(cloud.lower(), "us-east-1")


def region_display(cloud: str, region: str) -> str:
    name = REGION_CATALOGS.get(cloud.lower(), {}).get(region)
    return f"{region} ({name})" if name else region


def estimate_nat_monthly_usd(
    cloud: str,
    az_count: int,
    nat_mode: str,
    estimated_gb_out: float = 100.0,
) -> Optional[dict]:
    """
    Rough monthly NAT cost estimate.

    nat_mode: none | single | per_az
    """
    hints = NAT_COST_HINTS.get(cloud.lower())
    if not hints or nat_mode == "none":
        return {
            "monthly_usd_low": 0.0,
            "monthly_usd_high": 0.0,
            "gateways": 0,
            "estimated_gb_out": estimated_gb_out,
            "note": "No NAT gateways configured",
        }

    gateways = 1 if nat_mode == "single" else max(1, az_count)
    hours = 730.0
    idle = gateways * hints["gateway_hourly"] * hours
    data = estimated_gb_out * hints["data_per_gb"]
    # data often charged once, not per gateway
    return {
        "monthly_usd_low": round(idle, 2),
        "monthly_usd_high": round(idle + data, 2),
        "gateways": gateways,
        "estimated_gb_out": estimated_gb_out,
        "note": hints["note"],
    }
