from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainDescriptor:
    name: str
    route_prefix: str
    layer: str
    description: str


DOMAIN_DESCRIPTORS: tuple[DomainDescriptor, ...] = (
    DomainDescriptor(
        name="bot",
        route_prefix="/bot",
        layer="bot",
        description="Telegram integration boundary and user interaction state.",
    ),
    DomainDescriptor(
        name="ingestion",
        route_prefix="/ingestion",
        layer="api",
        description="Document intake, upload validation, and job bootstrap.",
    ),
    DomainDescriptor(
        name="diff",
        route_prefix="/diff",
        layer="worker",
        description="Structural and semantic comparison pipeline.",
    ),
    DomainDescriptor(
        name="compliance",
        route_prefix="/compliance",
        layer="worker",
        description="Legal hierarchy checks against official sources.",
    ),
    DomainDescriptor(
        name="report",
        route_prefix="/report",
        layer="worker",
        description="Report assembly and export orchestration.",
    ),
    DomainDescriptor(
        name="tenancy",
        route_prefix="/tenancy",
        layer="api",
        description="Tenant scoping and access context resolution.",
    ),
)
