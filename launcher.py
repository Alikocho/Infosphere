"""
launcher.py
===========
Standalone launcher for Infosphere.

Starts the Flask game server on a free port, then opens the
game in the user's default browser automatically.

This is the entry point for the PyInstaller-built .app and .exe.
"""

import os
import sys
import socket
import threading
import time
import webbrowser

# ── PyInstaller path fix ───────────────────────────────────────────────────────
# When running as a frozen executable, sys._MEIPASS contains the
# temp directory where PyInstaller unpacked the bundle.
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

# ── Find a free port ──────────────────────────────────────────────────────────

def find_free_port(start: int = 5000) -> int:
    """Find a free TCP port starting from `start`."""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start  # fallback


# ── Splash / tray (optional, gracefully skipped if tkinter not present) ───────

def show_splash(port: int):
    """Show a minimal splash window while the server starts. Silent if no tkinter."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title("Infosphere")
        root.geometry("320x120")
        root.resizable(False, False)
        root.configure(bg="#0d0d0b")

        tk.Label(root, text="INFOSPHERE",
                 font=("Courier", 18, "bold"),
                 fg="#c41e1e", bg="#0d0d0b").pack(pady=(20, 4))
        tk.Label(root, text=f"Starting on port {port}…",
                 font=("Courier", 10),
                 fg="#aaaaaa", bg="#0d0d0b").pack()
        tk.Label(root, text="Your browser will open automatically.",
                 font=("Courier", 9),
                 fg="#666666", bg="#0d0d0b").pack(pady=4)

        # Auto-close after 3 seconds
        root.after(3000, root.destroy)
        root.mainloop()
    except Exception:
        pass  # No tkinter — run silently


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    port = find_free_port(5000)
    url  = f"http://127.0.0.1:{port}"

    # Import server after path is set up
    from server import app, init_game

    # Initialise default game (election, human=red, opponent=heuristic)
    init_game(
        scenario       = "election",
        human_team_str = "red",
        opponent       = "heuristic",
        seed           = 42,
    )

    # Show splash on a background thread
    splash_thread = threading.Thread(target=show_splash, args=(port,), daemon=True)
    splash_thread.start()

    # Open browser after a short delay to let Flask start
    def open_browser():
        time.sleep(1.2)
        webbrowser.open(url)

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    print(f"Infosphere running at {url}")
    print("Close this window to stop the server.")

    # Start Flask (blocking)
    app.run(
        host     = "127.0.0.1",
        port     = port,
        debug    = False,
        threaded = True,
        use_reloader = False,   # must be False in frozen executables
    )


if __name__ == "__main__":
    main()
