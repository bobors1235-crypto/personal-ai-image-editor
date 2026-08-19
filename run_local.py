"""
One-click Local Launcher for Personal AI Image Editor.
Starts the local FastAPI server and opens the browser.
"""

import os
import sys
import webbrowser
import subprocess
import time

def main():
    print("=" * 65)
    print("  ✨ Starting Personal AI Image Editor (Local Server) ✨")
    print("=" * 65)
    
    port = 7860
    host = "127.0.0.1"
    url = f"http://{host}:{port}"
    
    print(f"\n[+] Local UI will be available at: {url}")
    print("[+] Press Ctrl+C in this terminal to stop the server.\n")

    # Try opening browser after 1.5s
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(url)

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        import uvicorn
        uvicorn.run("local.server:app", host=host, port=port, reload=False)
    except KeyboardInterrupt:
        print("\n[!] Local server stopped gracefully.")
    except Exception as e:
        print(f"\n[!] Error launching server: {e}")
        print("Please ensure requirements are installed: pip install fastapi uvicorn pillow pydantic requests")

if __name__ == "__main__":
    main()
