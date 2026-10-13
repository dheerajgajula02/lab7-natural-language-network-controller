#!/usr/bin/env python3
"""Four typed MCP tools that prepare Lab 7 policies over stdio."""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from policies import (
    AllowPolicy, BlockPolicy, Direction, PolicyDraft, Port, PrioritizePolicy,
    Protocol, Rate, RateLimitPolicy, TrafficClass, prepare_policy,
)

mcp = FastMCP(
    "SDN-Lab7-Policy-Builder",
    log_level="WARNING",
    instructions=(
        "Prepare policy drafts using the four typed tools. Ask for clarification "
        "when endpoints, direction, protocol, or action-specific values are unclear. "
        "These tools never install rules. Drafts check a planned h1–h4 inventory, "
        "not the live network or installed-policy conflicts. Display the returned "
        "policy and summary for human review. No application tool exists yet. "
        "Encode ports as JSON integers without quotes, rates as JSON numbers, "
        "and allow_only as a JSON boolean. Never encode them as strings."
    ),
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
Endpoint = Annotated[str, Field(description="h1–h4, explicit any, or canonical IPv4 CIDR subnet")]


@mcp.tool(annotations=READ_ONLY)
def prepare_block_policy(
    source: Endpoint, destination: Endpoint, protocol: Protocol, direction: Direction,
    source_port: Port | None = None, destination_port: Port | None = None,
) -> PolicyDraft:
    """Prepare a drop-policy draft for matching IPv4 traffic; do not install it.

    Ports require TCP or UDP. Direction must be explicit. Both directions reverse
    endpoint and port matches. Unknown hosts are rejected against planned h1–h4.
    """
    return prepare_policy(
        BlockPolicy, source=source, destination=destination, protocol=protocol,
        direction=direction, source_port=source_port, destination_port=destination_port,
    )


@mcp.tool(annotations=READ_ONLY)
def prepare_allow_policy(
    source: Endpoint, destination: Endpoint, protocol: Protocol, direction: Direction,
    allow_only: Annotated[bool, Field(strict=True)],
    source_port: Port | None = None, destination_port: Port | None = None,
) -> PolicyDraft:
    """Prepare an allow-policy draft; do not install it.

    Set allow_only=true for 'allow only': other IPv4 traffic in the same endpoint
    and direction scope must be denied when later implemented. False adds an allow
    without requesting that complementary denial. Direction is explicit.
    """
    return prepare_policy(
        AllowPolicy, source=source, destination=destination, protocol=protocol,
        direction=direction, source_port=source_port, destination_port=destination_port,
        parameters={"allow_only": allow_only},
    )


@mcp.tool(annotations=READ_ONLY)
def prepare_rate_limit_policy(
    source: Endpoint, destination: Endpoint, protocol: Protocol, direction: Direction,
    rate_mbps: Rate,
    source_port: Port | None = None, destination_port: Port | None = None,
) -> PolicyDraft:
    """Prepare a rate-limit draft with a positive finite Mbps cap per direction.

    This represents intent only. Meter programming and application are not
    implemented; no bandwidth change occurs. Ports require TCP or UDP.
    """
    return prepare_policy(
        RateLimitPolicy, source=source, destination=destination, protocol=protocol,
        direction=direction, source_port=source_port, destination_port=destination_port,
        parameters={"rate_mbps": rate_mbps},
    )


@mcp.tool(annotations=READ_ONLY)
def prepare_prioritize_policy(
    source: Endpoint, destination: Endpoint, protocol: Protocol, direction: Direction,
    traffic_class: TrafficClass,
    source_port: Port | None = None, destination_port: Port | None = None,
) -> PolicyDraft:
    """Prepare a low/normal/high traffic-class draft; do not install it.

    Traffic class means desired QoS treatment, not OpenFlow flow-entry priority.
    Queue/DSCP mappings and execution are not implemented yet.
    """
    return prepare_policy(
        PrioritizePolicy, source=source, destination=destination, protocol=protocol,
        direction=direction, source_port=source_port, destination_port=destination_port,
        parameters={"traffic_class": traffic_class},
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
