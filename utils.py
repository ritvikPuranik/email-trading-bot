import os
import pickle
import base64
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

import logging
from binance.um_futures import UMFutures
from binance.lib.utils import config_logging
from binance.error import ClientError
from dotenv import load_dotenv
load_dotenv()

config_logging(logging, logging.INFO)

# HMAC authentication with API key and secret
KEY = os.getenv('TESTNET_API_KEY')
SECRET = os.getenv('TESTNET_API_SECRET')
QUANTITY = float(os.getenv('QUANTITY'))

hmac_client = UMFutures(key=KEY, secret=SECRET, base_url=os.getenv('TESTNET_URL'))


TOKEN_FILE = os.getenv("TOKEN_FILE")
PROCESSED_IDS_FILE = "processed_ids.pkl"

def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "wb") as token:
                pickle.dump(creds, token)
        else:
            return None

    return creds

def load_processed_ids():
    if os.path.exists(PROCESSED_IDS_FILE):
        with open(PROCESSED_IDS_FILE, "rb") as f:
            return pickle.load(f)
    return set()

def save_processed_id(msg_id):
    processed_ids = load_processed_ids()
    processed_ids.add(msg_id)
    with open(PROCESSED_IDS_FILE, "wb") as f:
        pickle.dump(processed_ids, f)

def parse_email_content(subject, body):
    # body = "BTCUSDT has reversed trend to NEUTRAL from LONG on 4H timeframe!"
    symbol = "BTCUSDT"
    side = "BUY"
    
    return symbol, side

def fetch_latest_email(history_id=None):
    creds = get_credentials()
    if not creds:
        logging.info("No valid credentials found.")
        return None, None

    try:
        service = build("gmail", "v1", credentials=creds)
        messages = service.users().messages().list(userId="me", labelIds=["CATEGORY_PERSONAL"]).execute()
        if "messages" in messages:
            processed_ids = load_processed_ids()
            for msg in messages["messages"]:
                msg_id = msg["id"]
                if msg_id in processed_ids:
                    continue  # Skip already processed messages

                message = service.users().messages().get(userId="me", id=msg_id).execute()
                
                headers = message["payload"]["headers"]
                subject = next((header["value"] for header in headers if header["name"] == "Subject"), None)
                
                if subject == "Mango Research Alerts":
                    sender = next(header["value"] for header in headers if header["name"] == "From")
                    body = ""
                    if "parts" in message["payload"]:
                        for part in message["payload"]["parts"]:
                            if part["mimeType"] == "text/plain":
                                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                                break
                    
                    logging.info(f"Sender: {sender}")
                    logging.info(f"Subject: {subject}")
                    logging.info(f"Body: {body}")
                    save_processed_id(msg_id)
                    return subject, body
    except HttpError as error:
        logging.info(f"An error occurred: {error}")
        return None, None

    return None, None

def create_futures_order(symbol, side):
    try:
        response = hmac_client.new_order(
            symbol=symbol,
            side=side.upper(),
            type='MARKET',
            quantity=QUANTITY,
        )
        logging.info(f"{side.capitalize()} order created: {response}")
        if side.upper() == 'BUY':
            return float(hmac_client.ticker_price(symbol=symbol)['price'])
    except ClientError as e:
        logging.error(f"Error creating {side.lower()} order: {e.error_message}")

import threading

def place_trade(symbol, side):
    # Change leverage
    hmac_client.change_leverage(
        symbol=symbol, leverage=20, recvWindow=6000
    )

    if side.upper() == 'BUY':
        buy_price = create_futures_order(symbol, side)
    elif side.upper() == 'SELL':
        create_futures_order(symbol, side)
        buy_price = None
    else:
        logging.error("Invalid side provided. Must be 'BUY' or 'SELL'.")
        return
