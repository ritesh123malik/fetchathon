"""Check Agentverse status and connectivity for RupeePilot."""
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

def main():
    address = os.getenv("AGENT_ADDRESS", "").strip()
    if not address:
        raise SystemExit("AGENT_ADDRESS must be set in .env")

    python = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    av = ROOT / (".venv/Scripts/av.exe" if os.name == "nt" else ".venv/bin/av")

    print(f"Checking Agentverse registration for {address}...")
    cmd = [str(av), "agent", "-p", "-r", "-c", address]
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == "__main__":
    raise SystemExit(main())
