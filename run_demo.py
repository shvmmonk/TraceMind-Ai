"""Launch the 4 local processes; Ctrl+C shuts down all services."""
from __future__ import annotations
import subprocess
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PUBLIC_PORT=int(os.getenv('PORT','8000'))
SERVICES=[('control plane','engine.main:app',PUBLIC_PORT),('order-service','engine.services:order_app',8001),
          ('inventory-service','engine.services:inventory_app',8002),('payment-service','engine.services:payment_app',8003)]

def main():
    children=[]
    for name,_,port in SERVICES:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
            sock.settimeout(.5)
            if sock.connect_ex(('127.0.0.1',port)) == 0:
                raise SystemExit(f'Port {port} is already in use ({name}). Stop the existing demo before starting another.')
    try:
        for name,app,port in SERVICES:
            cmd=[sys.executable,'-m','uvicorn',app,'--host','0.0.0.0' if port==PUBLIC_PORT and os.getenv('PUBLIC_DEMO','0')=='1' else '127.0.0.1','--port',str(port),'--no-access-log']
            p=subprocess.Popen(cmd,cwd=ROOT,stdout=None,stderr=None)
            children.append(p)
        for name,_,port in SERVICES:
            for _ in range(70):
                if children[[s[2] for s in SERVICES].index(port)].poll() is not None:
                    raise RuntimeError(f'{name} process terminated unexpectedly; port {port} may be in use')
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health' if port==PUBLIC_PORT else f'http://127.0.0.1:{port}/health',timeout=.5).close()
                    break
                except Exception:time.sleep(.15)
            else:raise RuntimeError(f'{name} failed health check on port {port}')
        print('\n'+'='*62,flush=True)
        print(f'  TraceMind AI is running: http://127.0.0.1:{PUBLIC_PORT}',flush=True)
        print(f'  API documentation:          http://127.0.0.1:{PUBLIC_PORT}/docs',flush=True)
        print('  Press Ctrl+C to stop all services.',flush=True)
        print('='*62+'\n',flush=True)
        while True:time.sleep(1)
    except KeyboardInterrupt:pass
    finally:
        for p in children:p.terminate()
        for p in children:
            try:p.wait(timeout=4)
            except subprocess.TimeoutExpired:p.kill()

if __name__=='__main__':main()
