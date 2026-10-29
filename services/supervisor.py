"""
Dispatch Hub Process Supervisor
Runs both the 24/7 Telegram SOS Bot Daemon and the News & Road Alerts Engine in parallel.
"""
import subprocess
import time
import sys

def main():
    print("[SUPERVISOR] Starting autonomous Car Hauler Dispatch Services...")
    try:
        import psycopg2
    except ImportError:
        print("[SUPERVISOR] Installing psycopg2-binary...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "psycopg2-binary"])
    bot_proc = subprocess.Popen([sys.executable, "-u", "telegram_bot_daemon.py"])
    news_proc = subprocess.Popen([sys.executable, "-u", "news_and_alerts_engine.py", "--daemon"])

    print("[SUPERVISOR] Services running: Telegram Bot (PID %d), News & Alerts (PID %d)" % (bot_proc.pid, news_proc.pid))

    try:
        while True:
            # Check if bot died, restart if needed
            if bot_proc.poll() is not None:
                print("[SUPERVISOR] telegram_bot_daemon crashed, restarting...")
                bot_proc = subprocess.Popen([sys.executable, "-u", "telegram_bot_daemon.py"])

            # Check if news died, restart if needed
            if news_proc.poll() is not None:
                print("[SUPERVISOR] news_and_alerts_engine crashed, restarting...")
                news_proc = subprocess.Popen([sys.executable, "-u", "news_and_alerts_engine.py", "--daemon"])

            time.sleep(10)
    except KeyboardInterrupt:
        print("[SUPERVISOR] Stopping services...")
        bot_proc.terminate()
        news_proc.terminate()

if __name__ == "__main__":
    main()
