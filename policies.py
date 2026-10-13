"""Policy drafts for Lab 7. No controller or LLM calls occur here."""

from ipaddress import IPv4Network
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Protocol = Literal["any", "tcp", "udp", "icmp"]
Direction = Literal["one_way", "both"]
TrafficClass = Literal["low", "normal", "high"]
Port = Annotated[int, Field(
    strict=True, ge=1, le=65535,
    description="JSON integer from 1 to 65535, e.g. 5004, never a quoted string such as '5004'.",
)]
Rate = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]

# This is the assignment's intended inventory, not discovered VM state.
PLANNED_HOSTS = frozenset({"h1", "h2", "h3", "h4"})


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyParameters(StrictModel):
    pass


class AllowParameters(StrictModel):
    allow_only: bool


class RateParameters(StrictModel):
    rate_mbps: Rate


class PriorityParameters(StrictModel):
    traffic_class: TrafficClass


class PolicyBase(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    source: str
    destination: str
    protocol: Protocol
    direction: Direction
    source_port: Port | None = None
    destination_port: Port | None = None

    @model_validator(mode="after")
    def validate_traffic_match(self):
        if self.protocol not in {"tcp", "udp"} and (
            self.source_port is not None or self.destination_port is not None
        ):
            raise ValueError("Ports require protocol tcp or udp; any and icmp have no ports.")
        for field in ("source", "destination"):
            value = getattr(self, field)
            if value in PLANNED_HOSTS or value == "any":
                continue
            if value.startswith("h") and value[1:].isdigit():
                raise ValueError(f"Unknown {field} host {value}; planned hosts are h1–h4.")
            try:
                IPv4Network(value, strict=True)
            except ValueError as exc:
                raise ValueError(
                    f"{field} must be h1–h4, any, or a canonical IPv4 subnet such as 10.0.0.0/24."
                ) from exc
            if "/" not in value:
                raise ValueError(f"{field}: use a host alias or explicit IPv4 CIDR subnet.")
        return self


class BlockPolicy(PolicyBase):
    action: Literal["block"] = "block"
    parameters: EmptyParameters = Field(default_factory=EmptyParameters)


class AllowPolicy(PolicyBase):
    action: Literal["allow"] = "allow"
    parameters: AllowParameters


class RateLimitPolicy(PolicyBase):
    action: Literal["rate_limit"] = "rate_limit"
    parameters: RateParameters


class PrioritizePolicy(PolicyBase):
    action: Literal["prioritize"] = "prioritize"
    parameters: PriorityParameters


Policy = Annotated[
    BlockPolicy | AllowPolicy | RateLimitPolicy | PrioritizePolicy,
    Field(discriminator="action"),
]


class ValidationScope(StrictModel):
    schema_checked: bool
    endpoint_check: Literal["planned_h1_h4_inventory_and_ipv4_syntax"] = (
        "planned_h1_h4_inventory_and_ipv4_syntax"
    )
    live_topology_checked: Literal[False] = False
    installed_policy_conflicts_checked: Literal[False] = False


class PolicyDraft(StrictModel):
    status: Literal["ready_for_review", "rejected"]
    policy: Policy | None
    summary: str
    issues: list[str] = Field(default_factory=list)
    validation: ValidationScope
    requires_confirmation: Literal[True] = True
    applied: Literal[False] = False
    application_available: Literal[False] = False


def prepare_policy(policy_type: type[PolicyBase], **fields) -> PolicyDraft:
    """Build a canonical draft or a clear rejection; never mutate the network."""
    try:
        policy = policy_type.model_validate(fields)
    except ValidationError as exc:
        issues = [
            f"{'.'.join(map(str, error['loc'])) or 'policy'}: {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False)
        ]
        return PolicyDraft(
            status="rejected", policy=None, summary="Policy draft rejected.",
            issues=issues, validation=ValidationScope(schema_checked=False),
        )

    traffic = f"{policy.protocol.upper()} traffic"
    if policy.protocol == "any":
        traffic = "all traffic"
    if policy.source_port is not None:
        traffic += f" with source port {policy.source_port}"
    if policy.destination_port is not None:
        traffic += f" with destination port {policy.destination_port}"
    scope = f"from {policy.source} to {policy.destination}"
    if policy.direction == "both":
        scope = f"between {policy.source} and {policy.destination} in both directions"
        if policy.source_port is not None or policy.destination_port is not None:
            scope += " (reverse rules swap source and destination ports)"

    if isinstance(policy, BlockPolicy):
        summary = f"Block {traffic} {scope}."
    elif isinstance(policy, AllowPolicy):
        summary = f"Allow {traffic} {scope}."
        if policy.parameters.allow_only:
            summary += " Block other IPv4 traffic within that endpoint and direction scope."
    elif isinstance(policy, RateLimitPolicy):
        summary = f"Limit {traffic} {scope} to {policy.parameters.rate_mbps:g} Mbps per direction."
    else:
        summary = f"Give {traffic} {scope} the {policy.parameters.traffic_class} traffic class."

    return PolicyDraft(
        status="ready_for_review", policy=policy, summary=summary,
        validation=ValidationScope(schema_checked=True),
    )
