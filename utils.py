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

def parse_email_content(body):
    words = body.split()
    symbol = words[0]
    to_position = words[words.index("to") + 1].upper()
    from_position = words[words.index("from") + 1].upper()

    if to_position == "NEUTRAL":
        side = "CLOSE"
        scale = 1
    elif to_position == "SHORT" and from_position == "NEUTRAL":
        side = "SELL"
        scale = 1
    elif to_position == "LONG" and from_position == "NEUTRAL":
        side = "BUY"
        scale = 1
    elif to_position == "SHORT" and from_position == "LONG":
        side = "BUY"
        scale = 2
    elif to_position == "LONG" and from_position == "SHORT":
        side = "SELL"
        scale = 2
    else:
        side = None
    logging.info(f"---------------- After parsing Symbol: {symbol}, Side: {side}")
    return symbol, side, scale

def fetch_latest_email(history_id=None):
    logging.info("Fetching latest email")
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

                message = service.users().messages().get(userId="me", id=msg_id, format='full').execute()
                
                headers = message["payload"]["headers"]
                subject = next((header["value"] for header in headers if header["name"].lower() == "subject"), None)
                
                if subject == "Mango Research Alerts":
                    sender = next(header["value"] for header in headers if header["name"].lower() == "from")
                    body = ""
                    
                    # Handle message payload
                    payload = message['payload']
                    if 'body' in payload and 'data' in payload['body']:
                        # Simple message
                        body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
                    elif 'parts' in payload:
                        # Multipart message
                        for part in payload['parts']:
                            if part['mimeType'] == 'text/plain':
                                if 'data' in part['body']:
                                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                                elif 'attachmentId' in part['body']:
                                    attachment = service.users().messages().attachments().get(
                                        userId='me',
                                        messageId=msg_id,
                                        id=part['body']['attachmentId']
                                    ).execute()
                                    body = base64.urlsafe_b64decode(attachment['data']).decode('utf-8')
                    
                    logging.info(f"Sender: {sender}")
                    logging.info(f"Subject: {subject}")
                    logging.info(f"Body length: {len(body)}")
                    logging.info(f"Body content: {body}")
                    
                    save_processed_id(msg_id)
                    return subject, body
    except HttpError as error:
        logging.info(f"An error occurred: {error}")
        return None, None

    return None, None

def create_futures_order(symbol, side, scale):
    try:
        response = hmac_client.new_order(
            symbol=symbol,
            side=side.upper(),
            type='MARKET',
            quantity=QUANTITY * scale,
        )
        logging.info(f"{side.capitalize()} order created: {response}")
    except ClientError as e:
        logging.error(f"Error creating {side.lower()} order: {e.error_message}")


def place_trade(symbol, side, scale):
    # Change leverage
    hmac_client.change_leverage(
        symbol=symbol, leverage=20, recvWindow=6000
    )

    if side.upper() == 'CLOSE':
        try:
            positions = hmac_client.get_position_risk(symbol=symbol)
            for position in positions:
                if float(position['positionAmt']) != 0:
                    close_side = 'SELL' if float(position['positionAmt']) > 0 else 'BUY'
                    create_futures_order(symbol, close_side, scale)
                    logging.info(f"Closed position for {symbol} with {close_side} order.")
        except ClientError as e:
            logging.error(f"Error closing position for {symbol}: {e.error_message}")
    else: # For BUY or SELL orders, execute directly
        create_futures_order(symbol, side, scale)
