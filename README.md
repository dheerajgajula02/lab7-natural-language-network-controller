# Lab 7 policy tools

Four working Python MCP tools prepare structured policy drafts:

| Tool | Additional required input | Meaning |
|---|---|---|
| `prepare_block_policy` | None | Request a drop rule for matching traffic |
| `prepare_allow_policy` | `allow_only` | Allow matching traffic; optionally deny other IPv4 traffic within the same scope |
| `prepare_rate_limit_policy` | `rate_mbps` | Request a positive finite Mbps cap per direction |
| `prepare_prioritize_policy` | `traffic_class` | Request `low`, `normal`, or `high` QoS treatment |

All tools require `source`, `destination`, `protocol`, and `direction`. Optional source/destination ports are strict integers from 1 to 65535 and require TCP or UDP. Protocol is `any`, `tcp`, `udp`, or `icmp`; direction is explicitly `one_way` or `both`. Selectors accept the planned hosts h1–h4, explicit `any`, or a canonical IPv4 subnet. These policies match IPv4 traffic. In a bidirectional policy, reverse rules will swap both endpoint and port matches.

The planned host inventory is not live discovery. There is no controller connection, conflict lookup, application tool, approval persistence, frontend, or LLM integration in this step. Every output reports `applied: false` and `application_available: false`. An LLM API key is not needed to call these deterministic preparation tools.

## How a Python function becomes an MCP tool

`mcp_server.py` creates a `FastMCP` server. The `@mcp.tool()` decorator registers each function. Its name, docstring, and typed arguments become the discoverable tool description and input schema. The function calls the shared policy builder in `policies.py`. The returned `PolicyDraft` model becomes a JSON output schema and a structured tool result for the client/frontend.

The tool result contains status, the canonical policy, a summary, validation issues, confirmation requirement, application availability, and the scope of the checks performed. The policy's action is fixed by the selected tool. An allow-only policy explicitly requests complementary denial rather than merely adding an ICMP allow rule.

Invalid argument types, missing arguments, or out-of-range scalar values return an MCP error. Policy-level validation, such as an unknown host or an ICMP policy with a port, returns a structured `rejected` result. The server remains usable after either kind of rejection.

## Run the real MCP demonstration

From the project folder, with `requirements.txt` installed:

```bash
python3 lab7/demo_mcp.py
```

The demonstration launches the stdio server, initializes a real MCP session, discovers exactly four tools with output schemas, invokes every tool, exercises ten rejection cases, and checks a subnet/wildcard request after the failures. The client closes its server subprocess when finished.

Generated files:

- `artifacts/tool_schemas.json`: actual MCP discovery response, including tool input/output schemas.
- `artifacts/demo_results.json`: actual requests, responses, and rejection evidence.
- `policy_schema.json`: the shared JSON policy schema, with action-specific variants.

To connect an MCP client, use the `mcp_config.json` entry. Its absolute server path is configured for this workspace. The server runs on demand over stdio, without a network listener. Run `python3 lab7/mcp_server.py` only from a client that speaks the MCP protocol; it is not an interactive terminal prompt.

## Verification performed

On 2026-10-12, `python3 lab7/demo_mcp.py` completed successfully using MCP Python SDK 1.28.1 and Pydantic 2.13.4. The four successful policies and ten rejected requests were exercised over actual stdio transport, followed by successful subnet/wildcard recovery. No VM resources were changed or controller rules installed. This verifies the policy-tool step, not the complete Lab 7 pipeline.

The requested `verify-before-delivery` skill could not be read because its parent directory denied access. Verification followed the user's explicit workflow requirement by executing the actual MCP client/server interaction.

## Natural-language selection verification

The current `demo_natural_language.py` is a small single-request demonstration:

1. Discover the tools and their schemas from MCP.
2. Send your sentence and the tool schemas to the configured Lab 6 MiMo model.
3. Run its selected MCP calls, then display and save the returned drafts.

```bash
python3 lab7/demo_natural_language.py "Block all IPv4 traffic from h1 to h3, one-way only."
```

Run without an argument to enter a request interactively. The output is saved to `artifacts/simple_demo_latest.json`. The provider-facing schemas are saved to `artifacts/natural_language_tool_schemas.json`. Credentials are read at runtime without copying them. Validation is performed by the MCP server. This demo makes one model request; conversational follow-up belongs in the later frontend/backend implementation.

The user requested simplicity, so the original 216-line multi-case harness was replaced with this 88-line demonstration. Automatic test expectations, resume logic, report generation, and model retry loops were removed from the executable demo. Earlier verification reports below remain historical evidence from the original harness.

The simplified script was run against the real provider and MCP server: a priority request selected the priority tool with an integer port, a block request selected the block tool, and a vague request asked for clarification without a tool call. The vague check initially did not complete in a batch invocation, then completed successfully when rerun directly. The latest saved output is the clarification example.

Observed results: four actionable requests selected the correct tools and preserved their requested arguments; one vague request asked for clarification without calling a tool. The priority request initially selected the right tool but encoded destination port 5004 as text. Schema validation blocked it. Clearer instructions alone did not resolve this; simplifying the provider-facing optional port schema from integer-or-null to an optional integer succeeded. The original MCP schema remains strict, and no output coercion is performed. Three initial successful action cases and the vague case were retained; the priority case was rerun after the fix.

- `artifacts/natural_language_results.md`: readable report with requests, selected tool inputs, actual outputs, and final model responses.
- `artifacts/natural_language_results.json`: machine-readable evidence.
- `artifacts/natural_language_tool_schemas.json`: actual provider-facing tool schemas discovered from MCP, with the documented optional-port subset adaptation.
- `artifacts/natural_language_initial_results.json` and `natural_language_instruction_results.json`: retained failed attempts.

The resulting five cases passed in the recorded run. This is evidence for those examples, not a general guarantee of interpretation accuracy. These tests prepare drafts only; the full translator/controller and live-network workflow remain incomplete.
