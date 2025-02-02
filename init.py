import threading
import subprocess
import logging

logging.basicConfig(level=logging.INFO)

def start_flask_server():
    subprocess.run(["gunicorn", "-w", "1","--threads", "1", "-b", "0.0.0.0:3000", "alpha_trader:app"])
    # subprocess.run(["python3", "alpha_trader.py"]) # for the development server

def start_position_tracker():
    subprocess.run(["python3", "track_open_positions.py"])

if __name__ == "__main__":
    alpha_trader_thread = threading.Thread(target=start_flask_server)
    position_tracker_thread = threading.Thread(target=start_position_tracker)

    alpha_trader_thread.start()
    position_tracker_thread.start()

    logging.info("Started alpha_trader_thread and position_tracker_thread")

    alpha_trader_thread.join()
    position_tracker_thread.join()

    logging.info("Both threads have finished execution")
