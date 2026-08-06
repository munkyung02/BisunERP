from __future__ import annotations


ERP_NAME = "BisunERP"
ERP_VERSION = "4.1.0"


def get_erp_version() -> str:
    """Return the canonical ERP release version."""
    return ERP_VERSION


def get_display_version() -> str:
    """Return the canonical version formatted for user-facing UI."""
    return f"v{ERP_VERSION}"


def get_version_metadata() -> dict[str, str]:
    """Return reusable version metadata for logs, reports, and exports."""
    return {
        "erp_name": ERP_NAME,
        "erp_version": ERP_VERSION,
        "erp_display_version": get_display_version(),
    }
