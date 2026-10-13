# Lab 7 decisions and handoff

Last updated: 2026-10-12

## Scope and current status

- Lab 7 is the active project. Lab 6 is complete and is a reference for architecture, MCP patterns, and environment setup.
- The user selected an MCP server exposing multiple typed tools for SDN requests.
- The user selected a small web frontend and Python backend for requests, policy previews, approval, and results. Frameworks have not been chosen.
- Work should proceed objective by objective. Use the user's submitted Lab 6 report as the reference for screenshot placement and the user's writing style.
- Current authorization includes the four policy preparation tools, natural-language tests, and Objective 1's topology setup with evidence added to the existing Google Doc. Work continues objective by objective.
- The four tools are implemented in `mcp_server.py`, backed by `policies.py`. Actual MCP calls succeeded for all four tools and rejected ten invalid cases. Evidence is in `artifacts/demo_results.json` and `artifacts/tool_schemas.json`; see `README.md` for the workflow. The subsequently authorized topology setup is complete; see `NETWORK.md`.
- The assignment source is `Lab7_NL_Network_Controller.docx` in this folder. [Editable Google Docs copy](https://docs.google.com/document/d/1cJHFtHjMkrFUAD30k24qjuLG5HaMI12L_PNqvGN3bMU/edit?usp=drivesdk); its URL was verified through Drive search.

## Chosen architecture

Keep the implementation as simple and readable as possible. The user explicitly requested redesigning the natural-language demo because a long harness obscured the basic tool call. Prefer a direct flow and add complexity only when the next objective needs it.

Use an LLM-enabled MCP client to accept natural-language network requests and invoke a Python MCP server's typed tools. Tool descriptions and input schemas tell the client what operations are available. The client sends structured arguments; the server dispatches them to Python handlers.

Python owns policy validation, rule construction, and REST requests to the SDN controller. Tool schemas make the interface explicit, but do not guarantee that the LLM interpreted the request correctly. Validate the policy and require the user's confirmation before changing the network.

The intended flow is:

1. The user expresses a network intent in natural language.
2. The LLM client invokes an appropriate MCP tool.
3. The Python server produces and validates a structured policy.
4. The user sees the translated policy and confirms it.
5. The server applies the approved policy through Ryu REST.
6. The system reports the result and checks the installed flow entry.

The user prefers this MCP approach over a standalone Python application that controls the entire interaction directly.

### Frontend, tool results, and approval

The backend hosts the LLM interaction and MCP client connection; the browser UI does not hold provider credentials or connect directly to the controller. A policy preparation tool returns structured status, the canonical policy, a readable summary, and validation issues. Preparation does not install rules.

The backend stores the draft and renders the actual structured tool result in the frontend. The LLM also receives the result and may explain it or request clarification. Its explanation must not replace the canonical policy shown for approval.

The user clicks Apply or Reject on a specific draft. The proposed enforcement is server-controlled approval tied to that exact draft; an LLM-generated boolean or a claim of approval is insufficient. After Apply, the backend revalidates against current network state and invokes application for the approved draft. A changed draft requires fresh approval. The backend inspects the resulting flow table before reporting the rule as verified active; failures and unverified results remain visible.

Keep the assignment's terminal confirmation path alongside the web UI. Exact storage, authentication, draft identifiers, and approval enforcement still need implementation design.

## Assignment requirements to preserve

MCP is our interface choice; the assignment does not mention or require MCP. It explicitly requires a Python pipeline and these functions:

- `translate_intent(intent_string)`: construct a translator prompt, call an LLM provider API, parse JSON into a dictionary, and reject invalid JSON or schema violations with a clear exception.
- `validate_policy(policy_dict)`: reject unknown hosts, missing required fields, and contradictions with installed policies; return clear errors without crashing.
- `apply_policy(policy_dict)`: construct controller REST requests and install block/allow flow entries, then report the switch and flow parameters.
- `run_intent_controller()`: accept a natural-language intent, translate it, display its JSON, ask `Apply this policy? (yes/no)`, and apply only after confirmation.

Keep these functions available for submission and a live demonstration. An MCP client interpreting a sentence on its own does not fulfill the assignment's explicit requirement that `translate_intent()` call an LLM API. Plan the MCP interface around these functions; finalize the exact integration before implementation.

Other requirements:

- A documented JSON schema representing block, allow, rate-limit, and prioritize actions. Include source, destination, protocol, applicable port, and action-specific parameters.
- A single switch with hosts h1–h4, OpenFlow 1.3, and easy-to-read MAC addresses.
- Implement block and allow application at minimum. The document expressly says rate-limiting and prioritization application is not required in Objective 2.
- Demonstrate three translation examples and four complete pipeline examples, including the assignment's block, ICMP-only allow, and port-80 block cases.
- Exercise vague, unknown-host, meaningless, and contradictory intents; show validation catching at least two problematic cases.
- Capture topology, JSON, confirmation, and installed-flow evidence for the report. Disclose AI use and submit the Python files.
- Voice input is extra credit and has not been selected for implementation.

## MCP tool surface: proposals, not finalized decisions

Expose multiple tools with explicit schemas and narrow responsibilities. Candidate responsibilities are intent translation, block-policy preparation, allow-policy preparation, validation/preview, applying an approved policy, and inspecting installed policies/flows.

The current proposal is one preparation tool per required action: block, allow, rate-limit, and prioritize. Shared inputs are source, destination, protocol, optional TCP/UDP source and destination ports, and explicit one-way/both direction. Allow adds an allow-only flag; rate-limit adds a positive Mbps limit; prioritize adds a documented traffic class. Return a canonical policy, validation status/issues, readable preview, and an explicit indication that nothing has been applied. These input/output details are proposals, not yet a finalized schema.

The initial implementation now exposes these four preparation tools with structured output and a generated shared schema. It validates against the planned h1–h4 inventory and IPv4 subnet syntax, not live discovery. Live topology checks and installed-policy conflict checks are explicitly reported as not performed. All tools report application unavailable. Rate limits are specified per direction; traffic classes are low/normal/high intent labels with no queue mapping yet. This working contract is ready for the user's review; the application and approval tools remain to be built.

The user considered an additional LLM review comparing intent, tool calls, policy, and flows, then explicitly deferred it as overkill for this step. The user authorized reuse of the Lab 6 LLM provider credentials for later integration. This step requires no LLM call and did not access or copy credentials.

The user subsequently authorized live natural-language tool-selection tests using the Lab 6 provider configuration. `demo_natural_language.py` discovers tool schemas, calls the configured model with automatic tool choice, executes real MCP calls, and returns results to the model through a bounded agent loop. Credentials are read at runtime without copying or logging them. Four actionable examples and one vague clarification example passed in the saved evidence. The priority case initially selected the correct tool but repeatedly supplied a string port; input validation blocked it. Instructions were clarified, then the provider-facing optional-port schema was simplified to an integer-only optional field, a subset of the MCP integer-or-null schema. The failed case passed after this adaptation with an actual integer argument. Passing cases were retained; original failed attempts remain saved. No string coercion or network installation occurred. The full results are in `artifacts/natural_language_results.md` and `.json`.

Decide exact tool names and boundaries later. Rate-limit and prioritization tools must not claim execution support until their controller behavior is implemented and demonstrated. Approval should apply to the precise policy being installed; its enforcement mechanism remains to be designed.

## VM access and network decisions

- There are two main VMs: Mininet and the SDN controller.
- Tailscale is the operator access path. Use the VMs' internal LAN for traffic between Mininet and the controller, including ping, OpenFlow, and controller REST traffic.
- The Mininet VM account is `mininet`.
- The controller VM account is lowercase `sdn`. The user's local Tailscale identity is Dheeraj; that identity is distinct from the VM Linux account.
- Do not store passwords or other secrets in this document.

Earlier exploration in this conversation reported the following observations. Recheck them before implementation because they describe prior live state:

- Both VMs were reachable over Tailscale SSH, and internal-LAN pings succeeded in both directions.
- Mininet reported version 2.2.2. OVS was running; no Mininet process was listed. Interfaces named s1 and s2 were present, but the unprivileged account could not inspect the OVS database, so the active bridge/flow configuration was not established.
- The controller reported Ryu 4.27 using Python 2.7. No Ryu manager process or listeners on controller ports 6633 and 8080 were observed; connection checks from Mininet were refused.
- Record current IP addresses and the precise working access commands after a fresh inventory. No addresses are inferred here.

## References and next exploration

- [Lab6_AI_Flow_Analyst.docx on Google Drive](https://docs.google.com/document/d/1xl4yUb9DSaXn44ylcjYrIdu-3BtxUQ02/edit?usp=drivesdk&ouid=112273320867552996954&rtpof=true&sd=true): found through Drive search and read on 2026-10-12. The user confirmed this is the submitted Lab 6 report and selected it as the Lab 7 reference for writing style and screenshots. The source remains a Word file displayed in Google's document editor.
- Read `../lab6/README.md`, `../lab6/mcp_server.py`, `../lab6/mcp_config.json`, and `../lab6/topo_lab6.py` for relevant patterns. These files exist; their suitability for reuse still needs review.
- Recheck VM processes, controller compatibility, ports, and internal-LAN addresses before planning service startup.
- Finalize the policy schema, MCP tool boundaries, LLM provider/client, approval enforcement, and conflict handling.
- Preserve the assignment's required translator API call and callable Python functions while integrating MCP.
- The four preparation tools and topology have been shown and reviewed. The next Objective 1 step is the required named translator and its three examples; later objectives remain pending.

## Decision log

- 2026-10-12: Corrected the project target to Lab 7; Lab 6 is the completed reference.
- 2026-10-12: Restricted current work to exploration and documentation.
- 2026-10-12: Established Tailscale for operator access and the internal LAN for VM-to-VM communication.
- 2026-10-12: Selected a Python MCP server with multiple typed SDN tools.
- 2026-10-12: Requested this document in the Lab 7 folder as the continuing record of decisions.
- 2026-10-12: Selected a small web frontend plus Python backend, including policy preview and Apply/Reject controls.
- 2026-10-12: Selected an objective-by-objective workflow and the submitted Lab 6 report as the screenshot and writing-style reference.
- 2026-10-12: Authorized the four preparation tools as the first implementation step, with a demonstration of their inputs, outputs, and handlers. Deferred the extra LLM review layer. Implemented and exercised this step through real MCP transport.
- 2026-10-12: Authorized and completed live natural-language selection tests and requested the report in the side panel. Added explicit numeric instructions and a provider-facing optional-port schema adaptation after observing a rejected string port in the priority case.
- 2026-10-12: User requested simplicity as the main design principle. Replaced the 216-line natural-language harness with an 88-line single-request demo: discover tools, ask the model, execute selected MCP calls, show/save the result. Earlier reports are retained as historical evidence; the simplified script is the current workflow.
- 2026-10-12: Verified the simplified script with real priority and block calls and a vague-request clarification. The priority argument retained an integer port. A vague batch request did not complete; a direct rerun succeeded without calling a tool.
- 2026-10-12: Authorized and completed Objective 1's topology setup. Started Ryu and one-switch/four-host Mininet over the internal LAN; all 12 ping checks passed. Added setup notes and two screenshots of recorded VM output to the existing Lab 7 Google Doc. `NETWORK.md` records current access, startup, and reconnect details. The required named translator and later objectives remain pending.
- 2026-10-12: User requested actual terminal screenshots. Replaced both browser evidence images with real xterm window captures of VM output via SSH, and verified the Google Doc's PDF layout. User briefly authorized a Guacamole search across the VPN, then explicitly canceled it; the full TCP scan was stopped and no further discovery is authorized for this task.
- 2026-10-12: Implemented Objective 2 in `intent_controller.py`: `apply_policy()` builds drop/forward entries (priority 100, IPv4-only match so ARP survives) and POSTs them to Ryu REST; allow_only adds a priority-90 drop-other pair so "only" is enforced; `both` installs mirrored reverse entries. `run_intent_controller()` prints the JSON, requires typed "yes", then verifies the flow table. Installed policies append to `artifacts/installed_policies.json` for Objective 3 conflict checks.
- 2026-10-12: Fixed a real LLM flake during Objective 2 tests: "between A and B" was returned as two duplicate directional calls, tripping the strict one-policy translator. Fixed in the system prompt (exactly one tool call per request), not by weakening `translate_intent()`. All four pipeline tests then passed live and ping tests confirmed the blocks (h1->h3 100% loss) while allowed ICMP passed.
- 2026-10-12: Implemented Objective 3.2 `validate_policy()` in `intent_controller.py`: missing-field check, Pydantic schema/host/port revalidation, and overlap-vs-installed conflict detection returning human-readable OK/Rejected strings without raising. Wired into `run_intent_controller()` between translation and confirmation. Tested offline (conflict, unknown host, missing fields, clean) and live (validator refused allow-vs-installed-block before confirmation; a valid-but-declined run installed nothing; flow table unchanged at 21/8).
- 2026-10-12: Ran Objective 3.1 bad-input evidence: all four canonical bad intents drew LLM clarification questions with zero tool calls and translator rejection; switch untouched. Outputs in `artifacts/obj3_bad1-4.txt`.
- 2026-10-12: Built Objective 4 voice path per user choices: Groq Whisper (key validated live, stored mode-600 in lab7/.env) instead of local Whisper; Streamlit frontend (`voice_app.py`, native mic widgets) over plain-Python backend (`voice_controller.py` with the required `capture_voice_intent()`). Spoken yes/no confirmation kept, not skipped. Verified end to end with synthesized speech (espeak→Groq→translate→validate OK, apply withheld) and Streamlit serving HTTP 200 with zero errors; switch untouched at 21/8. The two graded spoken demos remain for the user at the mic.
