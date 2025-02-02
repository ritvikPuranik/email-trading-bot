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



def parse_email_and_trade(email_body):
    logger.info(f'calling trade endpoint with email body: {email_body}')
    symbol, to_position, from_position = parse_email_content(email_body)
    if symbol and to_position and from_position:
        place_trade(symbol, to_position, from_position)
    print('called tarde and receved response') 

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
    
    while True:
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
                        email_body = message.body['plain'][0]
                        logger.info(f"New message received from {sender}: {email_body}")
                        parse_email_and_trade(email_body)
                        imbox.mark_seen(uid)
                        break  # Only process the latest message from this sender
                
            # Sleep before next check
            logger.debug(f"Waiting for {interval} seconds")
            time.sleep(interval)
            
        except Exception as e:
            logger.error(f"Error monitoring emails: {e}")
            time.sleep(interval)  # Wait before retrying

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