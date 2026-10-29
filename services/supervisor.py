"""
Dispatch Hub Process Supervisor
Runs both the 24/7 Telegram SOS Bot Daemon and the News & Road Alerts Engine in parallel.
"""
import subprocess
import time
import sys

def main():
    print("[SUPERVISOR] Starting autonomous Car Hauler Dispatch Services...")
    import os
    env = os.environ.copy()
    current_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"/app:/app/services:{current_pp}".strip(":")
    try:
        import psycopg2
    except ImportError:
        print("[SUPERVISOR] Installing psycopg2-binary...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "psycopg2-binary"])
    bot_proc = subprocess.Popen([sys.executable, "-u", "telegram_bot_daemon.py"], env=env)
    news_proc = subprocess.Popen([sys.executable, "-u", "news_and_alerts_engine.py", "--daemon"], env=env)

    print("[SUPERVISOR] Services running: Telegram Bot (PID %d), News & Alerts (PID %d)" % (bot_proc.pid, news_proc.pid))

    try:
        while True:
            # Check if bot died, restart if needed
            if bot_proc.poll() is not None:
                print("[SUPERVISOR] telegram_bot_daemon crashed, restarting...")
                bot_proc = subprocess.Popen([sys.executable, "-u", "telegram_bot_daemon.py"], env=env)

            # Check if news died, restart if needed
            if news_proc.poll() is not None:
                print("[SUPERVISOR] news_and_alerts_engine crashed, restarting...")
                news_proc = subprocess.Popen([sys.executable, "-u", "news_and_alerts_engine.py", "--daemon"], env=env)

            time.sleep(10)
    except KeyboardInterrupt:
        print("[SUPERVISOR] Stopping services...")
        bot_proc.terminate()
        news_proc.terminate()

if __name__ == "__main__":
    main()
