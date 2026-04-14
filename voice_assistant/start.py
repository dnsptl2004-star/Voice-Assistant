"""
Launcher script for Voice-Controlled AI Laptop Assistant.
Starts both backend and frontend servers.
"""

import subprocess
import sys
import time
import threading
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def print_header():
    """Print application header."""
    print(f"""
{BLUE}===========================================================
           Voice-Controlled AI Laptop Assistant
                    Starting Application...
==========================================================={RESET}
""")

def run_backend():
    """Start the Flask backend server."""
    backend_dir = Path(__file__).parent / "backend"
    
    print(f"{GREEN}[BACKEND] Starting Flask server on http://localhost:5000{RESET}")
    
    try:
        subprocess.run(
            [sys.executable, "app.py"],
            cwd=str(backend_dir),
            check=True
        )
    except KeyboardInterrupt:
        print(f"{YELLOW}[BACKEND] Server stopped by user{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}[BACKEND] Error: {e}{RESET}")

def run_frontend():
    """Start the React frontend development server."""
    frontend_dir = Path(__file__).parent / "frontend"
    
    print(f"{GREEN}[FRONTEND] Starting React development server...{RESET}")
    
    # Wait a moment for backend to start
    time.sleep(3)
    
    try:
        subprocess.run(
            "npm start",
            cwd=str(frontend_dir),
            shell=True,
            check=True
        )
    except KeyboardInterrupt:
        print(f"{YELLOW}[FRONTEND] Server stopped by user{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}[FRONTEND] Error: {e}{RESET}")

def check_dependencies():
    """Check if required dependencies are installed."""
    frontend_dir = Path(__file__).parent / "frontend"
    
    issues = []
    
    # Check Python dependencies
    try:
        import flask
        import pyautogui
        import keyboard
        import waitress
    except ImportError:
        issues.append("Python dependencies not installed. Run: pip install -r backend/requirements.txt")
    
    # Check Node.js
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        issues.append("Node.js not found. Please install Node.js 16+")
    
    # Check if node_modules exists
    if not (frontend_dir / "node_modules").exists():
        issues.append("Frontend dependencies not installed. Run: cd frontend && npm install")
    
    return issues

def main():
    """Main launcher function."""
    print_header()
    
    # Check dependencies
    print(f"{YELLOW}[SETUP] Checking dependencies...{RESET}")
    issues = check_dependencies()
    
    if issues:
        print(f"{RED}[ERROR] Missing dependencies:{RESET}")
        for issue in issues:
            print(f"  - {issue}")
        print(f"\n{YELLOW}Please install missing dependencies and try again.{RESET}")
        return
    
    print(f"{GREEN}[SETUP] All dependencies found!{RESET}\n")
    
    # Start servers in separate threads
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    frontend_thread = threading.Thread(target=run_frontend, daemon=True)
    
    try:
        backend_thread.start()
        time.sleep(2)
        frontend_thread.start()
        
        print(f"""
{GREEN}[OK] Backend running at: http://localhost:5000{RESET}
{GREEN}[OK] Frontend will open at: http://localhost:3000{RESET}

{YELLOW}Press Ctrl+C to stop both servers{RESET}
""")
        
        # Keep main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[LAUNCHER] Stopping servers...{RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
