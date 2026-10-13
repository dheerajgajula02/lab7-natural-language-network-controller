#!/usr/bin/env python3
"""One natural-language request → LLM-selected MCP tools → policy drafts."""

import asyncio
import copy
import json
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent
INSTRUCTIONS = """Prepare IPv4 policy drafts for hosts h1–h4 using the supplied tools.
Ask for clarification if the request is vague or misses essential details.
Ping means ICMP; 'only' means allow_only=true. Ports must be JSON integers,
rates numbers, and flags booleans. Omit unused optional ports. Nothing is installed.
From A to B means one_way; between A and B means both. Return exactly one tool
call per request: 'between A and B' is a single call with direction=both, never
two calls, and 'only' is allow_only=true on that single call, never an extra
block call. Use native function calling
for an actionable intent. Do not write a tool call as JSON in the message text.
"""


def tool_schema(schema):
    """Advertise optional ports as integers for the configured MiMo provider."""
    schema = copy.deepcopy(schema)
    for field in ("source_port", "destination_port"):
        prop = schema["properties"][field]
        schema["properties"][field] = next(v for v in prop["anyOf"] if v["type"] == "integer")
    return schema


async def request_policy(query):
    config = dotenv_values(HERE.parent / "lab6" / ".env")
    if not all(config.get(key) for key in ("MIMO_API_KEY", "MIMO_BASE_URL", "MIMO_MODEL")):
        raise RuntimeError("Lab 6 MiMo configuration is incomplete.")
    server = StdioServerParameters(command=sys.executable, args=[str(HERE / "mcp_server.py")])

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Discover MCP tools and give their input schemas to the LLM.
            discovered = (await session.list_tools()).tools
            tools = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": tool_schema(t.inputSchema),
            }} for t in discovered]
            response = await asyncio.to_thread(
                requests.post, config["MIMO_BASE_URL"].rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + config["MIMO_API_KEY"]},
                json={"model": config["MIMO_MODEL"], "tools": tools, "tool_choice": "auto",
                      "messages": [{"role": "system", "content": INSTRUCTIONS},
                                   {"role": "user", "content": query}], "max_tokens": 4096},
                timeout=(10, 60),
            )
            if not response.ok:
                raise RuntimeError(f"Provider returned HTTP {response.status_code}.")
            choice = response.json()["choices"][0]
            if choice.get("finish_reason") == "length":
                raise RuntimeError("Model response was incomplete; no tool was executed.")
            message = choice["message"]

            # 2. Execute the tool calls the LLM selected, through real MCP.
            result = {"query": query, "reply": message.get("content"), "calls": []}
            for call in message.get("tool_calls") or []:
                name = call["function"]["name"]
                arguments = json.loads(call["function"]["arguments"])
                if name not in {t.name for t in discovered}:
                    raise RuntimeError("Model selected an unknown tool.")
                output = await session.call_tool(name, arguments)
                result["calls"].append({"tool": name, "input": arguments, "is_error": output.isError,
                                        "output": output.structuredContent or [c.model_dump(mode="json") for c in output.content]})

    # 3. Show and save the request, selected inputs, and actual outputs.
    artifacts = HERE / "artifacts"
    artifacts.mkdir(exist_ok=True)
    text = json.dumps(result, indent=2)
    (artifacts / "simple_demo_latest.json").write_text(text + "\n")
    (artifacts / "natural_language_tool_schemas.json").write_text(json.dumps(tools, indent=2) + "\n")
    return result


def translate_intent(intent_string):
    """Call the LLM/MCP pipeline and return one validated policy dictionary."""
    try:
        result = asyncio.run(request_policy(intent_string))
    except Exception as error:
        raise ValueError("Invalid LLM response or MCP request.") from error
    if len(result["calls"]) != 1:
        raise ValueError("Intent needs clarification or contains multiple policies.")
    call = result["calls"][0]
    if call["is_error"] or call["output"].get("status") != "ready_for_review":
        raise ValueError(f"Policy rejected: {call['output']}")
    return call["output"]["policy"]


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or input("Network request: ")
    try:
        print("Intent:", query, flush=True)
        print(json.dumps(translate_intent(query), indent=2))
    except (ValueError, RuntimeError, requests.RequestException) as error:
        print(f"Request failed: {error}", file=sys.stderr)
        sys.exit(1)
