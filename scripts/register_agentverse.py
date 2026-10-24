"""Register RupeePilot Coordinator agent on Agentverse."""
import os
from pathlib import Path
from dotenv import load_dotenv
from uagents_core.identity import Identity
from uagents_core.utils.registration import RegistrationRequestCredentials, register_chat_agent

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

def main():
    api_key = os.getenv("AGENTVERSE_API_KEY", "").strip()
    seed = os.getenv("COORDINATOR_SEED", "").strip()

    if not api_key or not seed:
        raise SystemExit("AGENTVERSE_API_KEY and COORDINATOR_SEED must be set in .env")

    identity = Identity.from_seed(seed, 0)
    address = identity.address
    endpoint = "https://agentverse.ai/v2/agents/mailbox/submit"

    readme_text = """# RupeePilot — AI Financial Planning Team

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![tag:domain/finance](https://img.shields.io/badge/finance-16845C)

RupeePilot is a multi-agent personal financial planning platform designed to help Indians navigate competing money demands, unexpected expenses, and savings goals with verified, explainable options.

## Multi-Agent Architecture

RupeePilot orchestrates six specialist agents under one coordinator:
- **Expense Agent**: Categorizes spending into essential and discretionary outflows, enforcing realistic cut limits.
- **Cashflow Agent**: Tracks opening balances, recurring inflows, mandatory commitments, and projected closing balance.
- **Bills Agent**: Monitors mandatory bills and due dates to guarantee zero bill defaults.
- **Goal Agent**: Calculates impacts on savings goals and timelines.
- **Scenario Agent**: Simulates verified alternatives (spending cuts vs. paused savings vs. buffer trade-offs).
- **Verification Agent**: Performs independent deterministic mathematical checks on every candidate plan before presentation.

## Try It in Chat

- "I earn ₹28,000 per month and my monthly expenses are around ₹21,000. I just got an unexpected ₹8,000 medical expense. What should I do?"
- "demo" — loads the synthetic emergency demo (₹28,000 income, ₹10,000 bills, ₹8,000 spending, ₹6,000 savings, ₹8,000 shock).
- "plan" — generates and verifies scenario options based on your reviewed financial profile.
- "reset" — clears the current draft to start a fresh planning session.

## Safety & Boundaries

- All calculations are verified independently using Python Decimal.
- No automatic bank transfers, payments, or account deductions.
- User always stays in control: choices are advisory planning decisions.
"""

    success = register_chat_agent(
        name="RupeePilot Financial Planner",
        endpoint=endpoint,
        active=True,
        track_interactions=False,
        credentials=RegistrationRequestCredentials(
            agentverse_api_key=api_key,
            agent_seed_phrase=seed,
        ),
        description="Multi-agent financial planning team with 6 specialists and independent verification. Navigate emergencies, protect bills, and reach savings goals in ASI:One.",
        readme=readme_text,
        starter_prompts=[
            "I earn ₹28,000 per month and my monthly expenses are ₹21,000. I got an unexpected ₹8,000 expense. What should I do?",
            "demo",
            "plan",
            "reset",
        ],
        metadata={
            "is_public": "True",
            "tags": ["innovationlab", "hackathon", "finance", "rupeepilot", "planning", "budget"],
        },
    )

    if not success:
        raise SystemExit("Registration on Agentverse failed.")

    profile_url = f"https://agentverse.ai/agents/details/{address}/profile"
    print(f"Successfully registered RupeePilot on Agentverse!")
    print(f"Address: {address}")
    print(f"Profile URL: {profile_url}")

if __name__ == "__main__":
    main()
