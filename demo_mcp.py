#!/usr/bin/env python3
"""Exercise the actual stdio server and save its schemas and policy outputs."""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import TypeAdapter

from policies import Policy

HERE = Path(__file__).resolve().parent
EXAMPLES = [
    ("prepare_block_policy", dict(source="h1", destination="h3", protocol="any", direction="one_way")),
    ("prepare_allow_policy", dict(source="h2", destination="h4", protocol="icmp", direction="both", allow_only=True)),
    ("prepare_rate_limit_policy", dict(source="h1", destination="h4", protocol="udp", direction="one_way", rate_mbps=10.0)),
    ("prepare_prioritize_policy", dict(source="h2", destination="h3", protocol="udp", direction="one_way", destination_port=5004, traffic_class="high")),
]


async def main():
    records = []
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "mcp_server.py")])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            inventory = await session.list_tools()
            assert {t.name for t in inventory.tools} == {name for name, _ in EXAMPLES}
            assert all(t.outputSchema and t.annotations.readOnlyHint for t in inventory.tools)
            for name, arguments in EXAMPLES:
                result = await session.call_tool(name, arguments)
                assert not result.isError, result
                output = result.structuredContent
                assert output and output["status"] == "ready_for_review", output
                assert not output["applied"] and not output["application_available"]
                assert not output["validation"]["live_topology_checked"]
                assert not output["validation"]["installed_policy_conflicts_checked"]
                policy = TypeAdapter(Policy).validate_python(output["policy"])
                assert policy.source == arguments["source"]
                assert policy.destination == arguments["destination"]
                assert policy.protocol == arguments["protocol"]
                assert policy.direction == arguments["direction"]
                if name == "prepare_allow_policy":
                    assert output["policy"]["parameters"]["allow_only"] is True
                    assert "Block other IPv4" in output["summary"]
                if name == "prepare_rate_limit_policy":
                    assert output["policy"]["parameters"]["rate_mbps"] == 10.0
                if name == "prepare_prioritize_policy":
                    assert output["policy"]["parameters"]["traffic_class"] == "high"
                    assert output["policy"]["destination_port"] == 5004
                records.append({"tool": name, "input": arguments, "output": output})
                print(f"{name}: {output['summary']}")

            base = EXAMPLES[0][1]
            negative_cases = [
                ("unknown host", "prepare_block_policy", {**base, "source": "h5"}),
                ("ICMP with port", "prepare_block_policy", {**base, "protocol": "icmp", "destination_port": 80}),
                ("bad port", "prepare_block_policy", {**base, "protocol": "tcp", "destination_port": 70000}),
                ("string port", "prepare_block_policy", {**base, "protocol": "tcp", "destination_port": "80"}),
                ("unknown protocol", "prepare_block_policy", {**base, "protocol": "sctp"}),
                ("missing direction", "prepare_block_policy", {k: v for k, v in base.items() if k != "direction"}),
                ("noncanonical subnet", "prepare_block_policy", {**base, "source": "10.0.0.5/24"}),
                ("negative rate", "prepare_rate_limit_policy", {**base, "rate_mbps": -1.0}),
                ("string approval flag", "prepare_allow_policy", {**base, "allow_only": "true"}),
                ("unknown traffic class", "prepare_prioritize_policy", {**base, "traffic_class": "urgent"}),
            ]
            for label, name, arguments in negative_cases:
                result = await session.call_tool(name, arguments)
                output = result.structuredContent
                assert result.isError or (output and output["status"] == "rejected"), (label, result)
                records.append({"case": label, "tool": name, "input": arguments,
                                "is_error": result.isError,
                                "output": output or [item.model_dump(mode="json") for item in result.content]})
                print(f"Rejected: {label}")

            # Still usable after malformed calls, with wildcard and subnet selectors.
            arguments = {**base, "source": "10.0.0.0/24", "destination": "any", "protocol": "tcp", "destination_port": 80}
            result = await session.call_tool("prepare_block_policy", arguments)
            assert not result.isError and result.structuredContent["status"] == "ready_for_review"
            records.append({"case": "subnet and wildcard after rejections", "input": arguments, "output": result.structuredContent})

    artifacts = HERE / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "tool_schemas.json").write_text(json.dumps(inventory.model_dump(mode="json"), indent=2) + "\n")
    (artifacts / "demo_results.json").write_text(json.dumps(records, indent=2) + "\n")
    (HERE / "policy_schema.json").write_text(json.dumps(TypeAdapter(Policy).json_schema(), indent=2) + "\n")
    print("Verified four tools, ten rejection cases, and subnet/wildcard recovery through MCP.")


if __name__ == "__main__":
    asyncio.run(main())
