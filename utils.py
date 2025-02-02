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

from retry import retry_on_failure

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
    symbol = words[1]
    to_position = words[words.index("to") + 1].upper()
    from_position = words[words.index("from") + 1].upper()

    logging.info(f"---------------- After parsing Symbol: {symbol}, From : {from_position}, To : {to_position}")
    return symbol, to_position, from_position

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

def calculate_quantity(symbol: str, usdt_amount: float) -> float:
    """
    Calculate the quantity based on USDT amount and current market price.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        usdt_amount: Amount in USDT to trade
    Returns:
        float: Quantity in base asset
    """
    try:
        # Get mark price
        mark_price = float(hmac_client.mark_price(symbol=symbol)['markPrice'])
        
        # Calculate quantity (round down to avoid precision errors)
        quantity = round(usdt_amount / mark_price, 3)  # Adjust decimals based on asset
        
        return quantity
    except Exception as e:
        logging.error(f"Error calculating quantity for {symbol}: {str(e)}")
        raise

def request_order_on_binance(symbol, signal, scale):
    try:
        USDT_QUANTITY = float(os.getenv('USDT_QUANTITY', '2000.0'))  # Default 2000 USDT
        response = hmac_client.new_order(
            symbol=symbol,
            side=signal.upper(),
            type='MARKET',
            quantity=calculate_quantity(symbol, USDT_QUANTITY * scale),
        )
        logging.info(f"{signal.capitalize()} order created: {response}")
    except ClientError as e:
        logging.error(f"Error creating {signal.lower()} order: {e.error_message}")


@retry_on_failure(max_attempts=3, delay=5.0)
def check_and_request_order(symbol: str, signal: str, to_position: str, from_position: str) -> None:
    """
    Check positions and create appropriate orders based on signal.
    
    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        signal: Trading signal ('BUY', 'SELL', 'CLOSE', 'REVERSE')
    """
    try:
        # Get current position
        positions = hmac_client.get_position_risk(symbol=symbol)
        position = next((pos for pos in positions if float(pos['positionAmt']) != 0), None)
        
        # If no position found and signal is CLOSE or REVERSE, nothing to do
        if not position and signal.upper() in ['CLOSE']:
            logging.info(f"No open position for {symbol} to {signal.lower()}")
            return

        position_amount = float(position['positionAmt']) if position else 0
        is_long = position_amount > 0 if position else None
        signal = signal.upper()

        # Direct BUY/SELL orders
        if signal in ['BUY', 'SELL']:
            request_order_on_binance(symbol, signal, 1)
            logging.info(f"Created new {symbol} position: {signal}")
            return

        # Close position
        if signal == 'CLOSE':
            side = 'SELL' if is_long else 'BUY'
            request_order_on_binance(symbol, side, 1)
            logging.info(f"Closed {symbol} position with {side}")
            return

        # Reverse position
        if signal == 'REVERSE':
            logging.info(f"is_long: {is_long}")
            logging.info(f"position: {position}")
            side = 'SELL' if is_long else 'BUY'

            if position is None:
                if to_position == 'LONG':
                    side = 'BUY'
                else:
                    side = 'SELL'
            else:
                side = 'SELL' if is_long and position else 'BUY'
            
            scale = 2 if position else 1
            request_order_on_binance(symbol, side, scale)
            logging.info(f"Reversed {symbol} position with {side} (scale: {scale})")
            return

        logging.error(f"Invalid signal received: {signal}")
                
    except ClientError as e:
        logging.error(f"Binance API error for {symbol}: {e.error_message}")
    except Exception as e:
        logging.error(f"Unexpected error for {symbol}: {str(e)}")

def place_trade(symbol, to_position, from_position):
    #set_margin_type(symbol, 'CROSS')
    set_leverage(symbol, 20)
    signal = get_signal(to_position, from_position)
    check_and_request_order(symbol, signal, to_position, from_position)

def get_signal(to_position, from_position):
    """
    Get the trading signal based on the current and previous positions.
    """

    if to_position == "NEUTRAL":
        signal = "CLOSE"
    elif to_position == "SHORT" and from_position == "NEUTRAL":
        signal = "SELL"
    elif to_position == "LONG" and from_position == "NEUTRAL":
        signal = "BUY"
    elif to_position == "SHORT" and from_position == "LONG":
        signal = "REVERSE"
    elif to_position == "LONG" and from_position == "SHORT":
        signal = "REVERSE"
    else:
        signal = None
    
    logging.info(f"Signal: {signal}")
    return signal

def set_margin_type(symbol: str, margin_type: str = 'ISOLATED') -> None:
    """
    Set margin type for a symbol.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        margin_type: 'ISOLATED' or 'CROSS'
    """
    try:
        response = hmac_client.change_margin_type(
            symbol=symbol,
            marginType=margin_type.upper()
        )
        logging.info(f"Changed margin type for {symbol} to {margin_type}")
        return response
    except ClientError as e:
        # Ignore error if margin type is already set
        if "No need to change margin type" in str(e):
            logging.info(f"Margin type already set to {margin_type} for {symbol}")
            return
        raise

def set_leverage(symbol: str, leverage: int = 20) -> None:
    """
    Set leverage for a symbol with error handling.
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        leverage: Leverage value (1-125 depending on symbol)
    """
    try:
        response = hmac_client.change_leverage(
            symbol=symbol,
            leverage=leverage,
            recvWindow=6000
        )
        logging.info(f"Changed leverage for {symbol} to {leverage}x")
        return response
        
    except ClientError as e:
        # Handle specific leverage errors
        if "Leverage is too large" in str(e):
            set_leverage(symbol, 10) ## TODO: Handle this better
            logging.error(f"Leverage {leverage}x is too high for {symbol}")
            raise
        elif "No need to change leverage" in str(e):
            logging.info(f"Leverage already set to {leverage}x for {symbol}")
            return
        else:
            logging.error(f"Error setting leverage for {symbol}: {str(e)}")
            raise
            
    except Exception as e:
        logging.error(f"Unexpected error setting leverage for {symbol}: {str(e)}")
        raise