# Natural-language MCP verification

Provider model: `mimo-v2.6-flash`. These are live model selections followed by actual MCP calls.

Each request received all four tools discovered from the running server. Tool choice was automatic; expected outcomes were used only to evaluate the results.

All results are drafts. Live topology, installed-policy conflicts, approval, and installation are not part of this check.

Completed cases: 5/5. Unlisted cases are pending.

## Case 1: PASS

Stop all IPv4 traffic that h1 sends to h3. This is one-way; leave the reverse direction alone.

Expected tool: `prepare_block_policy`

Selected tool: `prepare_block_policy`

Input:
```json
{
  "source": "h1",
  "destination": "h3",
  "protocol": "any",
  "direction": "one_way"
}
```

Actual MCP output:
```json
{
  "status": "ready_for_review",
  "policy": {
    "schema_version": "1.0",
    "source": "h1",
    "destination": "h3",
    "protocol": "any",
    "direction": "one_way",
    "source_port": null,
    "destination_port": null,
    "action": "block",
    "parameters": {}
  },
  "summary": "Block all traffic from h1 to h3.",
  "issues": [],
  "validation": {
    "schema_checked": true,
    "endpoint_check": "planned_h1_h4_inventory_and_ipv4_syntax",
    "live_topology_checked": false,
    "installed_policy_conflicts_checked": false
  },
  "requires_confirmation": true,
  "applied": false,
  "application_available": false
}
```

Model's response:

The draft is ready for review:

- **Action:** Block all traffic from **h1 → h3** (one-way; the reverse direction h3 → h1 is untouched)
- **Protocol/ports:** Any protocol, no port restriction
- **Validation:** Endpoints checked against the planned h1–h4 inventory; **no live topology or installed-policy conflict checks were performed**
- **Status:** Not applied — this is a draft only and requires your confirmation

Let me know if you'd like to narrow it (e.g., a specific protocol or port) before confirming.

## Case 2: PASS

Let h2 and h4 ping each other in both directions, but allow no other IPv4 traffic between them.

Expected tool: `prepare_allow_policy`

Selected tool: `prepare_allow_policy`

Input:
```json
{
  "source": "h2",
  "destination": "h4",
  "protocol": "icmp",
  "direction": "both",
  "allow_only": true
}
```

Actual MCP output:
```json
{
  "status": "ready_for_review",
  "policy": {
    "schema_version": "1.0",
    "source": "h2",
    "destination": "h4",
    "protocol": "icmp",
    "direction": "both",
    "source_port": null,
    "destination_port": null,
    "action": "allow",
    "parameters": {
      "allow_only": true
    }
  },
  "summary": "Allow ICMP traffic between h2 and h4 in both directions. Block other IPv4 traffic within that endpoint and direction scope.",
  "issues": [],
  "validation": {
    "schema_checked": true,
    "endpoint_check": "planned_h1_h4_inventory_and_ipv4_syntax",
    "live_topology_checked": false,
    "installed_policy_conflicts_checked": false
  },
  "requires_confirmation": true,
  "applied": false,
  "application_available": false
}
```

Model's response:

The draft is ready for review:

- **Allow** ICMP (ping) between **h2 ↔ h4** in **both directions**.
- With `allow_only` set, any **other IPv4 traffic between h2 and h4 must be denied** — satisfying "no other IPv4 traffic between them."

**Status:** This is only a draft (`applied: false`). Endpoints were validated against the planned h1–h4 inventory, but no live topology check or installed-policy conflict check has been performed, and the rule is not installed. It also requires confirmation before any future application.

Shall I keep this draft as-is?

## Case 3: PASS

Cap UDP traffic from h1 to h4 at ten megabits per second, one-way.

Expected tool: `prepare_rate_limit_policy`

Selected tool: `prepare_rate_limit_policy`

Input:
```json
{
  "source": "h1",
  "destination": "h4",
  "protocol": "udp",
  "direction": "one_way",
  "rate_mbps": 10
}
```

Actual MCP output:
```json
{
  "status": "ready_for_review",
  "policy": {
    "schema_version": "1.0",
    "source": "h1",
    "destination": "h4",
    "protocol": "udp",
    "direction": "one_way",
    "source_port": null,
    "destination_port": null,
    "action": "rate_limit",
    "parameters": {
      "rate_mbps": 10.0
    }
  },
  "summary": "Limit UDP traffic from h1 to h4 to 10 Mbps per direction.",
  "issues": [],
  "validation": {
    "schema_checked": true,
    "endpoint_check": "planned_h1_h4_inventory_and_ipv4_syntax",
    "live_topology_checked": false,
    "installed_policy_conflicts_checked": false
  },
  "requires_confirmation": true,
  "applied": false,
  "application_available": false
}
```

Model's response:

The draft rate limit is ready for review:

- **Source → Destination:** h1 → h4 (one-way, so return traffic is not affected)
- **Protocol:** UDP (all ports, since none were specified)
- **Cap:** 10 Mbps in the h1→h4 direction

Limitations to be aware of:
- This is a **draft only** — no meter has been programmed and **no bandwidth change has occurred**.
- Validation was done against the planned h1–h4 inventory and IPv4 syntax only; **live topology and installed-policy conflict checks have not been performed**.

Would you like to narrow this to a specific UDP port, extend it to both directions, or proceed toward implementation?

## Case 4: FAIL

Give high priority to UDP video traffic sent from h2 to h3, destined for port 5004. One-way only.

Expected tool: `prepare_prioritize_policy`

Selected tool: `prepare_prioritize_policy`

Input:
```json
{
  "source": "h2",
  "destination": "h3",
  "protocol": "udp",
  "direction": "one_way",
  "destination_port": "5004",
  "traffic_class": "high"
}
```

Actual MCP output:
```json
{
  "status": "rejected",
  "applied": false,
  "issues": [
    "destination_port: '5004' is not valid under any of the given schemas"
  ]
}
```

This call was rejected by client-side schema validation before MCP execution. The error was returned to the LLM for correction.

Selected tool: `prepare_prioritize_policy`

Input:
```json
{
  "destination": "h3",
  "destination_port": "5004",
  "direction": "one_way",
  "protocol": "udp",
  "source": "h2",
  "traffic_class": "high"
}
```

Actual MCP output:
```json
{
  "status": "rejected",
  "applied": false,
  "issues": [
    "destination_port: '5004' is not valid under any of the given schemas"
  ]
}
```

This call was rejected by client-side schema validation before MCP execution. The error was returned to the LLM for correction.

Selected tool: `prepare_prioritize_policy`

Input:
```json
{
  "destination": "h3",
  "destination_port": "5004",
  "direction": "one_way",
  "protocol": "udp",
  "source": "h2",
  "traffic_class": "high"
}
```

Actual MCP output:
```json
{
  "status": "rejected",
  "applied": false,
  "issues": [
    "destination_port: '5004' is not valid under any of the given schemas"
  ]
}
```

This call was rejected by client-side schema validation before MCP execution. The error was returned to the LLM for correction.

Model's response:

(No final text)

Error: RuntimeError: request or tool validation failed; inspect local execution.

## Case 5: PASS

Make the network faster.

Expected tool: `none; clarify`

Model's response:

"Make the network faster" is too vague for me to draft a specific policy — it could mean several different things. To prepare something useful, I need a bit more detail:

1. **Which traffic?** For example: a source host (h1–h4), a destination host or subnet, or a particular service/port.
2. **What kind of treatment do you want?**
   - **Priority boost** — mark certain traffic as higher/normal/lower traffic class (QoS preference).
   - **Bandwidth cap** — limit a flow's rate to a certain Mbps (usually to *reduce* congestion rather than speed things up).
   - **Allow-only** — permit a specific flow exclusively (with everything else in scope denied).
3. **Direction** — one-way or both directions?
4. **Protocol** — TCP, UDP, ICMP (ping), or any?

Once you tell me *what traffic* you want improved and *how*, I'll prepare a draft policy for it (as a draft only — nothing gets installed).

## Practical limit

These examples document the observed run, not a guarantee that every wording will be interpreted correctly. Server validation and approval are still required. Initial invalid arguments and corrections are retained above.
