#!/usr/bin/env python3
"""
Run both frontend and backend locally for development.
This script starts the NextJS frontend and FastAPI backend in parallel.
"""

import os
import sys
import subprocess
import signal
import time
import threading
from pathlib import Path

# Windows compatibility for npm command
NPM_CMD = "npm.cmd" if os.name == "nt" else "npm"

# Track subprocesses for cleanup
processes = []

def cleanup(signum=None, frame=None):
    """Clean up all subprocess on exit"""
    print("\n🛑 Shutting down services...")
    for proc in processes:
        try:
            if os.name == "nt":
                # On Windows, shell=True means proc.terminate() only kills cmd.exe,
                # not the actual child process (node, uvicorn). Use taskkill /T to
                # kill the entire process tree.
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/F", "/T"],
                    capture_output=True
                )
            else:
                proc.terminate()
                proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    sys.exit(0)

# Register cleanup handlers
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def check_requirements():
    """Check if required tools are installed"""
    checks = []

    # Check Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        node_version = result.stdout.strip()
        checks.append(f"✅ Node.js: {node_version}")
    except FileNotFoundError:
        checks.append("❌ Node.js not found - please install Node.js")

    # Check npm
    try:
        result = subprocess.run([NPM_CMD, "--version"], capture_output=True, text=True)
        npm_version = result.stdout.strip()
        checks.append(f"✅ npm: {npm_version}")
    except FileNotFoundError:
        checks.append("❌ npm not found - please install npm")

    # Check uv (which manages Python for us)
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        uv_version = result.stdout.strip()
        checks.append(f"✅ uv: {uv_version}")
    except FileNotFoundError:
        checks.append("❌ uv not found - please install uv")

    print("\n📋 Prerequisites Check:")
    for check in checks:
        print(f"  {check}")

    # Exit if any critical tools are missing
    if any("❌" in check for check in checks):
        print("\n⚠️  Please install missing dependencies and try again.")
        sys.exit(1)

def check_env_files():
    """Check if environment files exist"""
    project_root = Path(__file__).parent.parent

    root_env = project_root / ".env"
    frontend_env = project_root / "frontend" / ".env.local"

    missing = []

    if not root_env.exists():
        missing.append(".env (root project file)")
    if not frontend_env.exists():
        missing.append("frontend/.env.local")

    if missing:
        print("\n⚠️  Missing environment files:")
        for file in missing:
            print(f"  - {file}")
        print("\nPlease create these files with the required configuration.")
        print("The root .env should have all backend variables from Parts 1-7.")
        print("The frontend/.env.local should have Clerk keys.")
        sys.exit(1)

    print("✅ Environment files found")

def start_backend():
    """Start the FastAPI backend"""
    backend_dir = Path(__file__).parent.parent / "backend" / "api"

    print("\n🚀 Starting FastAPI backend...")

    # Check if dependencies are installed
    if not (backend_dir / ".venv").exists() and not (backend_dir / "uv.lock").exists():
        print("  Installing backend dependencies...")
        subprocess.run(["uv", "sync"], cwd=backend_dir, check=True)

    # Start the backend
    proc = subprocess.Popen(
        ["uv", "run", "main.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    processes.append(proc)

    # Wait for backend to start
    print("  Waiting for backend to start...")
    for _ in range(30):  # 30 second timeout
        try:
            import httpx
            response = httpx.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("  ✅ Backend running at http://localhost:8000")
                print("     API docs: http://localhost:8000/docs")
                return proc
        except:
            time.sleep(1)

    print("  ❌ Backend failed to start")
    cleanup()

def start_frontend():
    """Start the NextJS frontend"""
    frontend_dir = Path(__file__).parent.parent / "frontend"

    print("\n🚀 Starting NextJS frontend...")

    # Check if dependencies are installed
    if not (frontend_dir / "node_modules").exists():
        print("  Installing frontend dependencies...")
        subprocess.run([NPM_CMD, "install"], cwd=frontend_dir, check=True)

    # Start the frontend
    cmd = "npm run dev" if os.name == "nt" else [NPM_CMD, "run", "dev"]
    proc = subprocess.Popen(
        cmd,
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine stderr with stdout
        text=True,
        bufsize=1,
        shell=(os.name == "nt")
    )
    processes.append(proc)

    # Wait for frontend to start
    print("  Waiting for frontend to start...")
    import httpx

    for i in range(30):  # 30 second timeout
        # Start checking after 5 seconds
        if i > 5:  
            try:
                response = httpx.get("http://localhost:3000", timeout=1)
                print("  ✅ Frontend running at http://localhost:3000")
                return proc
            except httpx.ConnectError:
                pass  # Server not ready yet
            except Exception:
                # Any other response means server is up
                print("  ✅ Frontend running at http://localhost:3000")
                return proc

        time.sleep(1)

    print("  ❌ Frontend failed to start")
    cleanup()

def monitor_processes():
    """Monitor running processes and show their output"""
    print("\n" + "="*60)
    print("🎯 Alex Financial Advisor - Local Development")
    print("="*60)
    print("\n📍 Services:")
    print("  Frontend: http://localhost:3000")
    print("  Backend:  http://localhost:8000")
    print("  API Docs: http://localhost:8000/docs")
    print("\n📝 Logs will appear below. Press Ctrl+C to stop.\n")
    print("="*60 + "\n")

    # Monitor processes
    def stream_logs(p):
        try:
            for l in iter(p.stdout.readline, ''):
                if l:
                    print(f"[LOG] {l.strip()}", flush=True)
        except Exception:
            pass

    for proc in processes:
        threading.Thread(target=stream_logs, args=(proc,), daemon=True).start()

    while True:
        for proc in processes:
            # Check if process is still running
            if proc.poll() is not None:
                cmd_str = proc.args if isinstance(proc.args, str) else " ".join(proc.args)
                print(f"\n⚠️  A process has stopped unexpectedly! Command: '{cmd_str}' | Exit code: {proc.poll()}")
                cleanup()

        time.sleep(1)

def main():
    """Main entry point"""
    print("\n🔧 Alex Financial Advisor - Local Development Setup")
    print("="*50)

    # Check prerequisites
    check_requirements()
    check_env_files()

    # Install httpx if needed
    try:
        import httpx
    except ImportError:
        print("\n📦 Installing httpx for health checks...")
        subprocess.run(["uv", "add", "httpx"], check=True)

    # Start services
    backend_proc = start_backend()
    frontend_proc = start_frontend()

    # Monitor processes
    try:
        monitor_processes()
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()