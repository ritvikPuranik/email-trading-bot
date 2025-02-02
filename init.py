import threading
import subprocess
import logging
from config import setup_credentials

logging.basicConfig(level=logging.INFO)

def run_config():
    logging.info("Running config setup")
    try:
        setup_credentials()
        logging.info("Config initialization completed")
    except Exception as e:
        logging.error(f"Config initialization failed: {str(e)}")
        raise

def start_flask_server():
    subprocess.run(["gunicorn", "-w", "2","--threads", "4", "-b", "0.0.0.0:3000", "alpha_trader:app"])
    # subprocess.run(["python3", "alpha_trader.py"]) # for the development server

def start_position_tracker():
    subprocess.run(["python3", "track_open_positions.py"])

if __name__ == "__main__":
    try:
        run_config()  # Run config setup first
        
        alpha_trader_thread = threading.Thread(target=start_flask_server)
        position_tracker_thread = threading.Thread(target=start_position_tracker)

        alpha_trader_thread.start()
        position_tracker_thread.start()

        logging.info("Started alpha_trader_thread and position_tracker_thread")

        alpha_trader_thread.join()
        position_tracker_thread.join()

        logging.info("Both threads have finished execution")
    except Exception as e:
        logging.error(f"Error during initialization: {str(e)}")
        exit(1)
