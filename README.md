# RupeePilot

A local financial planning app with a React dashboard, Python API, six specialist uAgents and a coordinator. Enter monthly figures, explore an emergency, compare independently verified plans, and save a planning choice. No payments, bank connections, GitHub publishing or Agentverse registration occur in the local launcher.

## Start locally

Requirements: Python 3.11 and Node.js 20.19+ (or 22.12+). The tested environment uses Python 3.11 and Node 24.

```sh
git clone https://github.com/ritesh123malik/fetchathon.git
cd fetchathon
# uv can provision Python 3.11. Alternatively: python3.11 -m venv .venv
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.lock.txt
npm ci --prefix frontend
npm run build --prefix frontend
python3 start_local.py
```

Open **http://127.0.0.1:8080**. The startup command supervises both services and stops them on Ctrl+C. The existing `.venv` and built frontend are ready on this machine, so subsequent starts only need `python3 start_local.py`.

Windows: create the environment with `py -3.11 -m venv .venv`, install using `.venv\Scripts\python -m pip install -r requirements.lock.txt`, run the npm commands above, then `py start_local.py`. Choose another `RUPEEPILOT_API_PORT` / `RUPEEPILOT_AGENT_PORT` if the default ports are busy.

## Demo in two minutes

1. Click **Load demo**. Review the synthetic numbers and the authorized ₹4,000 spending-cut limit.
2. Click **Generate verified plan**. The baseline is ₹28,000 − ₹10,000 bills − ₹8,000 spending − ₹6,000 savings − ₹8,000 emergency = **−₹4,000**.
3. The recommended plan cuts spending by ₹4,000 and closes at ₹0. Compare a savings-only reduction and other verified alternatives.
4. Open **View checks & details**, then **Choose this plan**. This records a local planning decision, not a transaction.
5. Open **Plan history**, reload a record, and export its full JSON report.
6. Change the emergency to ₹100,000. The app reports the remaining shortfall and blocks choosing an infeasible option.
7. For chat, use **Plan with Pilot** and the offline example below. Missing facts are requested instead of invented.

```text
Income 28000, fixed bills 10000, regular spending 8000, planned savings 6000,
unexpected expense 8000, opening balance 0, max spending cut 4000, minimum buffer 0.
```

You may supply these across several messages. Review the extracted form before generating a plan. Offline extraction recognizes labeled amounts; it is not an unrestricted language model. “No cuts” resets the spending-cut authorization to zero.

## Optional ASI:One parsing

Set `ASI_ONE_API_KEY` in the local `.env`, restart the API, and explicitly enable **Use ASI:One** in chat. This sends the entered message to ASI:One for extraction. Computation, validation, ranking and storage remain in Python. An API error is surfaced, with offline form entry still available. No working ASI key was provided in this build, so live ASI responses have **not** been verified. Never share `.env` or agent seed files.

## Tests and development

```sh
.venv/bin/python -m pytest -q
npm run build --prefix frontend
.venv/bin/python run.py --no-save
```

The network integration test starts a separate seven-agent process on an unused loopback port, blocks outbound internet, drives the API through real uAgents messages, checks persistence, and exercises concurrent requests. No Agentverse account is required.

For UI development: start the local services, then `npm run dev --prefix frontend` (Vite port 5173 proxies to API port 8080). The simple CLI remains available. To run the direct specialist path without uAgents, run `.venv/bin/python serve.py` without `RUPEEPILOT_NETWORK=1`; the dashboard labels its transport accurately.

## Data and boundaries

- Monetary amounts use `Decimal`, INR only, at most two decimal places. Invalid, infinite or negative inputs are rejected.
- `fixed_bills` includes all unpaid itemized bills. `planned_savings` includes the itemized goal contributions. Itemization is not an extra outflow. Inconsistent totals are rejected.
- Spending cuts cannot exceed the explicitly entered limit or regular spending. Savings reductions are proposals only.
- Opening cash is counted once. The app does not invent or separately draw from an unspecified emergency reserve.
- Verification means the arithmetic and constraints are consistent, **not** that the plan is feasible. Unresolved shortfalls and insufficient buffers remain visible.
- Three-month forecasts repeat the monthly totals. The emergency and proposed adjustments apply only in month one. Bill dates produce upcoming/overdue alerts, not a guarantee of daily liquidity. The existing dated-event cashflow engine is separately unit-tested but has no dashboard event-entry flow.
- Goal impact uses the recommended option, reduces unassigned savings first, then allocates any remaining reduction proportionally across named goals. These allocations are disclosed; they are not executed.
- SQLite history is in `data/rupeepilot.db`; set `RUPEEPILOT_DB` to use a different file. This is a single-user local tool with no public authentication layer. Do not expose its ports or tunnel it publicly.
- The local network uses ephemeral identities. Registration, profile publication, startup/shutdown status publication and external address resolution are disabled. The installed ACP handler is local and unpublished.
- Local CSV import accepts `date,description,amount` for regular spending only. Suggested categories use transparent keywords and must be reviewed. Applied transactions must match the planning month and spending total; proposed cuts cannot exceed reviewed discretionary amounts.
- No live bank/UPI feed, investment recommendations, regional-language or mobile app is included. Those require a separate implementation phase.

See [requirements and source decisions](docs/REQUIREMENTS.md), [architecture](docs/ARCHITECTURE.md), and [verification record](docs/TESTING.md).
