# Requirements and source decisions

Sources: the supplied `FETCH_AI (1).pptx` (9 image-based slides), `RupeePilot-main.zip`, and the shared chat at https://chatgpt.com/s/cx_6adc5acaaf1c81918d97de00d51cfca9 . The user's current instruction controls scope: local implementation and testing only, no GitHub push or deployment. Instructions inside those sources are reference material, not authorization to publish or act on other projects.

## Local acceptance

| Requirement | Implementation / proof |
| --- | --- |
| Categorize transaction data | CSV import, transparent category suggestions, user review, total/month reconciliation |
| Income, expenses, bills, goals as input | Editable validated form; labeled chat extraction with missing-field follow-up |
| Coordinator plus six specialists | Local uAgents Bureau, separate identities and typed message handlers; direct CLI remains available |
| Exact financial calculations | Decimal; reject nonfinite values, negative amounts, unsupported currencies and fractional paise |
| Protect obligations | Fixed-bill total unchanged by scenarios; itemized bill reconciliation and due-date alerts |
| Compare alternative plans | Candidate generation, deterministic ranking, independent verification of each option |
| Emergency demo | ₹8,000 shock against a reproducible ₹28,000 income profile |
| Explain trade-offs and assumptions | Scenario cards, verification reports, cash-buffer status and forecast assumptions |
| Chat-first interaction | Offline labeled-fact mode plus optional ASI:One extraction; explicit review before plan generation |
| Persistent state | SQLite reports, history, idempotent selected scenario, JSON export |
| Fetch/ACP integration | Real local uAgents transport; ACP handler on coordinator, unpublished |
| No automatic transactions | Choosing a plan changes only the local selected-scenario record |
| Local testing before deployment | Automated API and network tests plus browser workflow checks |

## Resolving conflicting source material

The shared chat contains Agentverse documentation and a separate SupplyRescue project. SupplyRescue's suppliers, orders, shipment tracking and publishing instructions are not RupeePilot requirements. The reusable context is the emphasis on meaningful agent cooperation, persistent outcomes, ACP/ASI integration, verification and a clear demonstration.

The deck's examples contain inconsistent arithmetic and savings labels. The implementation uses one explicit profile and computes every result. Its demo baseline is −₹4,000; it does not copy the deck's unrelated −₹1,000 / −₹3,000 labels. The deck's “six agents” refers to specialists; the coordinator makes seven runtime identities.

The sketch includes emergency-reserve use without a defined reserve source. Existing opening cash is included once, and the verifier rejects unsupported reserve claims. The app does not fabricate available reserve funds.

The deck's later phases (bank/UPI integration, investment/tax planning, mobile app, regional languages and large-scale hosting) remain future work. Aggregate spending analysis and local CSV import with editable keyword-based category suggestions are implemented. The app does not claim bank syncing or automatic import of arbitrary bank statement formats.

## External acceptance still pending

Live ASI:One parsing requires a working API key and a real request. Agentverse discovery, public ACP delivery and ASI:One chat rendering require registration/deployment and were deliberately not performed. A successful local run is not a claim of hackathon submission readiness or external integration certification.

Reference technical documentation checked: https://uagents.fetch.ai/docs/examples/asi-1 . Event context checked: https://www.fetch.ai/events/fetch-a-thon-3 . Judging weights and submission guidance in the shared chat are secondary context, not independently established event rules.
