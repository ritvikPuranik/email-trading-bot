import os
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

def parse_email_content(body):
    words = body.split()
    symbol = words[1]
    to_position = words[words.index("to") + 1].upper()
    from_position = words[words.index("from") + 1].upper()

    logging.info(f"---------------- After parsing Symbol: {symbol}, From : {from_position}, To : {to_position}")
    return symbol, to_position, from_position

def get_symbol_info(symbol: str) -> dict:
    """
    Get symbol information including precision requirements.
    """
    try:
        exchange_info = hmac_client.exchange_info()
        symbol_info = next((s for s in exchange_info['symbols'] if s['symbol'] == symbol), None)
        if not symbol_info:
            raise ValueError(f"Symbol {symbol} not found")
        return symbol_info
    except Exception as e:
        logging.error(f"Error getting symbol info for {symbol}: {str(e)}")
        raise

def calculate_quantity(symbol: str, usdt_amount: float) -> float:
    """
    Calculate the quantity based on USDT amount and current market price.
    """
    try:
        # Get mark price
        mark_price = float(hmac_client.mark_price(symbol=symbol)['markPrice'])
        
        # Get symbol precision
        symbol_info = get_symbol_info(symbol)
        lot_size_filter = next(filter(lambda x: x['filterType'] == 'LOT_SIZE', symbol_info['filters']))
        step_size = lot_size_filter['stepSize']
        quantity_precision = len(str(float(step_size)).rstrip('0').split('.')[-1])
        
        # Calculate quantity with correct precision
        quantity = usdt_amount / mark_price
        quantity = round(quantity, quantity_precision)
        
        return quantity
    except Exception as e:
        logging.error(f"Error calculating quantity for {symbol}: {str(e)}")
        raise

def request_order_on_binance(symbol, signal, scale):
    try:
        USDT_QUANTITY = float(os.getenv('USDT_QUANTITY', '3000.0'))
        quantity = calculate_quantity(symbol, USDT_QUANTITY * scale)
        
        response = hmac_client.new_order(
            symbol=symbol,
            side=signal.upper(),
            type='MARKET',
            quantity=quantity
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
        is_long = position_amount > 0
        signal = signal.upper()
        logging.info(f"Current position for {symbol}: {position_amount} (is_long: {is_long}), signal: {signal}")

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