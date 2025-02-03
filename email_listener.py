import time
import os
from imbox import Imbox
import logging
from utils import parse_email_content, place_trade
from dotenv import load_dotenv
import ssl

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)



def parse_html_content(html_content: str) -> str:
    """Extract relevant text from HTML content."""
    # Look for the pattern "reversed trend to X from Y"
    import re
    match = re.search(r'(\w+) has reversed trend to (\w+) from (\w+)', html_content)
    if match:
        symbol, to_pos, from_pos = match.groups()
        return f"{symbol} {to_pos} {from_pos}"
    return ""

def parse_email_and_trade(message_body):
    
    if isinstance(message_body, dict):
        content = ""
        if message_body.get('plain') and message_body['plain'][0].strip():
            content = message_body['plain'][0]
        elif message_body.get('html') and message_body['html'][0].strip():
            content = message_body['html'][0]
        
        if content:
            logger.info(f'Extracted content: {content}')
            symbol, to_position, from_position = parse_email_content(content)
            if symbol and to_position and from_position:
                place_trade(symbol, to_position, from_position)
        else:
            logger.warning("No valid content found in message")
    else:
        logger.warning(f"Unexpected message body format: {type(message_body)}")

def monitor_emails(
    username: str,
    password: str,
    senders: list[str],
    interval: int = 5,
    subject: str = 'Mango Research Alerts'
) -> None:
    """
    Continuously monitor emails for new messages.
    
    Args:
        username: Gmail username
        password: Gmail app password
        senders: List of email addresses to monitor
        interval: Sleep interval between checks in seconds
        subject: Subject line to filter
    """
    logger.info(f"Starting email monitor for messages from: {senders}")
    
    # Create unverified SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        with Imbox('imap.gmail.com',
                username=username,
                password=password,
                ssl=True,
                ssl_context=ssl_context,
                starttls=False) as imbox:
            
            # Check for new messages from any of the senders
            for sender in senders:
                inbox_messages_from = imbox.messages(
                    sent_from=sender, 
                    subject=subject, 
                    unread=True
                )
                
                # Process latest message if any
                for uid, message in inbox_messages_from:
                    try:
                        # logger.info(f"Processing message with body: {message.body}")
                        parse_email_and_trade(message.body)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        continue
                    
                    imbox.mark_seen(uid)
                    break  # Only process the latest message from this sender
            
        logger.debug(f"Check complete. Closing now")
        
    except Exception as e:
        logger.error(f"Error monitoring emails: {e}")

if __name__ == "__main__":
    # Email credentials and settings
    USERNAME = os.getenv("EMAIL_USERNAME")
    PASSWORD = os.getenv("APP_PASSWORD")
    SENDERS = os.getenv("EMAIL_SENDERS").split(",")
    CHECK_INTERVAL = int(os.getenv("POLLING_INTERVAL"))
    
    # Start monitoring
    monitor_emails(
        username=USERNAME,
        password=PASSWORD,
        senders=SENDERS,
        interval=CHECK_INTERVAL
    )