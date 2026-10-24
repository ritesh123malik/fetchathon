"""Start and stop the local UI/API and seven-agent network together."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parent

def main():
    python=ROOT/('.venv/Scripts/python.exe' if os.name=='nt' else '.venv/bin/python')
    if not python.exists() or not (ROOT/'frontend/dist/index.html').exists():
        print('Run the setup steps in README.md first (Python environment and frontend build).')
        return 1
    api_port=int(os.getenv('RUPEEPILOT_API_PORT','8080'))
    agent_port=int(os.getenv('RUPEEPILOT_AGENT_PORT','8010'))
    for port in [api_port,agent_port]:
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port))==0:
                print(f'Port {port} is already in use. Stop the existing RupeePilot process or choose different local ports.')
                return 1
    env={**os.environ,'RUPEEPILOT_NETWORK':'1','PYTHONUNBUFFERED':'1'}
    children=[]
    try:
        children.append(subprocess.Popen([str(python),'run_network.py'],cwd=ROOT,env=env))
        for _ in range(400):
            if children[0].poll() is not None: raise RuntimeError('Agent network stopped during startup')
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1',agent_port))==0: break
            time.sleep(.1)
        else: raise RuntimeError('Agent network startup timed out')
        children.append(subprocess.Popen([str(python),'serve.py'],cwd=ROOT,env=env))
        for _ in range(100):
            if children[-1].poll() is not None: raise RuntimeError('Web service stopped during startup')
            try:
                with urlopen(f'http://127.0.0.1:{api_port}/api/health',timeout=1) as response:
                    if response.status==200: break
            except OSError: time.sleep(.1)
        print(f'\nRupeePilot is ready: http://127.0.0.1:{api_port}\nAll services are local. Press Ctrl+C to stop.\n',flush=True)
        while all(p.poll() is None for p in children): time.sleep(.5)
        raise RuntimeError('A local service stopped; shutting down the other service.')
    except KeyboardInterrupt: return 0
    except Exception as exc:
        print(exc,file=sys.stderr);return 1
    finally:
        for p in children:
            if p.poll() is None: p.terminate()
        for p in children:
            try: p.wait(timeout=10)
            except subprocess.TimeoutExpired: p.kill();p.wait()

if __name__=='__main__': raise SystemExit(main())
