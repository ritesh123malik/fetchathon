# Architecture

React/Vite serves a local dashboard. FastAPI validates requests and stores results. With the standard launcher, the API forwards each validated profile to the coordinator's local REST bridge on port 8010. The coordinator sends typed `AgentTask` messages to Expense, Cashflow, Bills and Goal agents, requests candidates from Scenario, then sends each candidate to Verification. Only independently approved candidates reach ranking and the UI.

`app/services/planner.py` owns the common pipeline and output bundle. `execute_task` reuses the original specialist calculation functions. `assemble_result` in the existing coordinator ranks direct and network results identically. Every network reply is checked for task ID, role, success and timeout. Network failure returns a visible error and does not save a plan.

The seven agents share a local uAgents Bureau process; they communicate through uAgents' dispatcher. They are not seven cloud services or seven LLM calls. The models validate payloads at each specialist boundary. Decimal amounts travel as JSON strings.

`run_network.py` also installs the official Chat Protocol on the coordinator. It acknowledges incoming messages and supports labeled facts, `demo`, `plan` and `reset`. Drafts are keyed by sender and session. The adapter calls the same local API; it does not register the agent or use mailbox access. The browser remains the full local review/selection interface.

The runtime pins uAgents 0.25.5. Its default startup status updater makes a network request even when registration is disabled, so `LocalAgent` explicitly overrides that method. A no-op batch registration policy, loopback bind, disabled inspector/profile publishing and local-only resolver prevent accidental discovery/publication in the local configuration. Integration tests block outbound socket connections.

No LLM can set balances or bypass the verifier. ASI:One is optional fact extraction; raw extracted facts remain subject to missing-field checks, model validation and user review. Offline chat is intentionally a limited parser, clearly labeled as such.
