#!/usr/bin/env python3
"""Objective 2: turn a translated policy into OpenFlow rules via Ryu REST.

Block and allow only; rate-limit and prioritization are Objective 3 material.
Every installed policy is appended to artifacts/installed_policies.json so the
Objective 3 validator can check new drafts against what is already live.
"""

import json
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values
from pydantic import TypeAdapter, ValidationError

from demo_natural_language import translate_intent
from policies import Policy

HERE = Path(__file__).resolve().parent
RYU_REST = "http://100.110.3.67:8080"  # controller VM over Tailscale; OpenFlow itself stays on the internal LAN
DPID = 1
SWITCH = "s1"
PRIORITY = 100
IPV4 = 2048  # dl_type for IPv4; matching it keeps ARP working so ping tests fail cleanly
PROTO_NUM = {"tcp": 6, "udp": 17, "icmp": 1}
INSTALLED = HERE / "artifacts" / "installed_policies.json"

# Mininet links h1-h4 to s1-eth1-4 in order, so host N lives on OpenFlow port N.
HOSTS = {
    "h1": {"ip": "10.0.0.1", "mac": "00:00:00:00:00:01", "port": 1},
    "h2": {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "port": 2},
    "h3": {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3},
    "h4": {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4},
}


def endpoint_match(policy, side):
    """Match fields for one endpoint: host MAC, IPv4 subnet, or omitted for any."""
    value = policy[side]
    prefix = "dl_src" if side == "source" else "dl_dst"
    if value == "any":
        return {}
    if value in HOSTS:
        return {prefix: HOSTS[value]["mac"]}
    nw_field = "nw_src" if side == "source" else "nw_dst"
    return {nw_field: value}  # validated as canonical CIDR by the MCP tool


def policy_entries(policy):
    """Build (match, actions) flow entries; both directions get forward+reverse."""
    match = {"dl_type": IPV4}
    match.update(endpoint_match(policy, "source"))
    match.update(endpoint_match(policy, "destination"))
    if policy["protocol"] != "any":
        match["nw_proto"] = PROTO_NUM[policy["protocol"]]
    if policy.get("source_port") is not None:
        match[f"{policy['protocol']}_src"] = policy["source_port"]
    if policy.get("destination_port") is not None:
        match[f"{policy['protocol']}_dst"] = policy["destination_port"]

    if policy["action"] == "block":
        entries = [(match, [])]
    elif policy["action"] == "allow":
        if policy["destination"] not in HOSTS:
            raise ValueError("Allow rules need a known destination host (h1-h4) in this lab.")
        entries = [(match, [{"type": "OUTPUT", "port": HOSTS[policy["destination"]]["port"]}])]
        if policy.get("parameters", {}).get("allow_only"):
            # Forward this traffic first, drop the rest of IPv4 inside the same scope.
            scope = {"dl_type": IPV4}
            scope.update(endpoint_match(policy, "source"))
            scope.update(endpoint_match(policy, "destination"))
            entries.append((scope, []))
    else:
        raise ValueError(f"Objective 2 does not install {policy['action']} policies.")

    if policy["direction"] == "both":
        mirrored = []
        for entry_match, actions in entries:
            reverse = dict(entry_match)
            for a_field, b_field in (("dl_src", "dl_dst"), ("nw_src", "nw_dst"),
                                     ("tcp_src", "tcp_dst"), ("udp_src", "udp_dst")):
                if a_field in reverse or b_field in reverse:
                    reverse[a_field], reverse[b_field] = reverse.get(b_field), reverse.get(a_field)
                    reverse = {k: v for k, v in reverse.items() if v is not None}
            if policy["action"] == "allow" and actions:
                reverse_out = [{"type": "OUTPUT", "port": HOSTS[policy["source"]]["port"]}]
                mirrored.append((reverse, reverse_out))
            else:
                mirrored.append((reverse, actions))
        entries.extend(mirrored)
    unique = []
    for entry in entries:
        if entry not in unique:  # any-to-any mirrors to itself; install once
            unique.append(entry)
    return unique


def get_flows():
    """Current flow table of s1 from Ryu REST."""
    response = requests.get(f"{RYU_REST}/stats/flow/{DPID}", timeout=10)
    response.raise_for_status()
    return response.json()[str(DPID)]


def expand_scope(policy):
    """Directed (source, destination) host pairs a policy covers; any means h1-h4."""
    hosts = ("h1", "h2", "h3", "h4")
    sources = hosts if policy["source"] == "any" else (policy["source"],)
    destinations = hosts if policy["destination"] == "any" else (policy["destination"],)
    pairs = {(s, d) for s in sources for d in destinations}
    if policy["direction"] == "both":
        pairs |= {(d, s) for s, d in pairs}
    return pairs


def overlaps(new, installed):
    """True if two policies cover common traffic. Port comparison is
    approximate for both-direction rules, whose mirror swaps the ports."""
    if not expand_scope(new) & expand_scope(installed):
        return False
    if "any" not in (new["protocol"], installed["protocol"]) and new["protocol"] != installed["protocol"]:
        return False
    for side in ("source", "destination"):
        new_port = new.get(f"{side}_port")
        old_port = installed.get(f"{side}_port")
        if new_port is not None and old_port is not None and new_port != old_port:
            return False
    return True


def validate_policy(policy_dict):
    """Check a translated policy before it reaches apply_policy().

    Returns a human-readable verdict starting with OK or Rejected, and never
    raises, so a bad draft can never crash the controller or touch the switch.
    """
    try:
        if not isinstance(policy_dict, dict):
            return "Rejected: policy must be a JSON object."
        required = ("action", "source", "destination", "protocol", "direction")
        missing = [field for field in required if field not in policy_dict]
        if missing:
            return f"Rejected: missing required field(s): {', '.join(missing)}."
        try:
            TypeAdapter(Policy).validate_python(policy_dict)
        except ValidationError as error:
            parts = []
            for item in error.errors(include_input=False, include_url=False)[:3]:
                loc = ".".join(map(str, item["loc"])) or "policy"
                parts.append(loc + ": " + item["msg"])
            return "Rejected: invalid policy (" + "; ".join(parts) + ")."
        installed = json.loads(INSTALLED.read_text()) if INSTALLED.exists() else []
        for entry in installed:
            old = entry["policy"]
            if overlaps(policy_dict, old) and old["action"] != policy_dict["action"]:
                return (f"Rejected: conflicts with installed {old['action']} policy "
                        f"({old['source']}->{old['destination']} {old['protocol']}); "
                        f"remove it before applying the opposite action.")
        return "OK: policy is valid and conflicts with nothing installed."
    except Exception as error:
        return f"Rejected: validator error ({error})."


def apply_policy(policy_dict):
    """Install a translated block/allow policy on s1 and confirm what went in."""
    entries = policy_entries(policy_dict)
    for match, actions in entries:
        body = {"dpid": DPID, "priority": PRIORITY - (10 if not actions and policy_dict["action"] == "allow" else 0),
                "match": match, "actions": actions}
        response = requests.post(f"{RYU_REST}/stats/flowentry/add", json=body, timeout=10)
        response.raise_for_status()
        target = "DROP" if not actions else f"OUTPUT:{actions[0]['port']}"
        print(f"Installed {policy_dict['action']} on {SWITCH} (dpid {DPID}): match {match} -> {target}", flush=True)
    INSTALLED.parent.mkdir(exist_ok=True)
    installed = json.loads(INSTALLED.read_text()) if INSTALLED.exists() else []
    installed.append({"policy": policy_dict,
                      "flows": [{"match": m, "actions": a} for m, a in entries]})
    INSTALLED.write_text(json.dumps(installed, indent=2) + "\n")
    return entries


def roast_intent(intent):
    """Side quest: one playful LLM line when an intent is too vague to translate."""
    try:
        config = dotenv_values(HERE.parent / "lab6" / ".env")
        response = requests.post(
            config["MIMO_BASE_URL"].rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + config["MIMO_API_KEY"]},
            json={"model": config["MIMO_MODEL"],
                  "messages": [{"role": "user", "content":
                                "Roast this vague network request in one short playful "
                                f"line, no profanity, networking-themed: {intent!r}"}],
                  "max_tokens": 60},
            timeout=(10, 30),
        )
        if response.ok:
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


def diagnose_failure(intent, error):
    """Side quest: one concrete LLM guess at why the intent failed to translate."""
    try:
        config = dotenv_values(HERE.parent / "lab6" / ".env")
        response = requests.post(
            config["MIMO_BASE_URL"].rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + config["MIMO_API_KEY"]},
            json={"model": config["MIMO_MODEL"],
                  "messages": [{"role": "user", "content":
                                "A network intent failed to translate with this error: "
                                f"{error}. The intent was: {intent!r}. Valid hosts are "
                                "h1-h4; actions are block, allow, rate_limit, prioritize. "
                                "In one short sentence state the likely concrete reason "
                                "(unknown host, contradictory allow and block, vague "
                                "request, or similar). No roast, no extra text."}],
                  "max_tokens": 80},
            timeout=(10, 30),
        )
        if response.ok:
            return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


def run_intent_controller():
    """Translate one terminal intent, ask before touching the switch, then verify."""
    intent = " ".join(sys.argv[1:]) or input("Network intent: ")
    try:
        policy = translate_intent(intent)
    except ValueError as error:
        print(f"Request failed: {error}", file=sys.stderr)
        reason = diagnose_failure(intent, error)
        if reason:
            print(f"Likely reason: {reason}")
        roast = roast_intent(intent)
        if roast:
            print(roast)
        return sys.exit(1)
    print("Translated policy:")
    print(json.dumps(policy, indent=2))
    verdict = validate_policy(policy)
    print(verdict)
    if not verdict.startswith("OK"):
        print("Policy discarded; nothing was installed.")
        return 0
    if input("Apply this policy? (yes/no): ").strip().lower() != "yes":
        print("Policy discarded; nothing was installed.")
        return 0
    apply_policy(policy)
    flows = get_flows()
    print(f"Rule is active: s1 flow table now holds {len(flows)} entries.")
    return 0


if __name__ == "__main__":
    sys.exit(run_intent_controller())
