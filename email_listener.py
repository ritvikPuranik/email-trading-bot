import time
import os
from imbox import Imbox
import logging
import requests
from dotenv import load_dotenv
import ssl

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)



def call_trade_endpoint(email_body):
    logger.info(f'calling trade endpoint with email body: {email_body}')
    data = {'email':email_body}
    url ='http://localhost:3000/trade'
    response = requests.post(url, json=data)
    print(response.json())
    print('called tarde and receved response') 

def monitor_emails(
    username: str,
    password: str,
    sender: str,
    interval: int = 5,
    subject: str = 'Mango Research Alerts'
) -> None:
    """
    Continuously monitor emails for new messages.
    
    Args:
        username: Gmail username
        password: Gmail app password
        sender: Email address to monitor
        interval: Sleep interval between checks in seconds
        subject: Subject line to filter
    """
    logger.info(f"Starting email monitor for messages from: {sender}")
    
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
                    ssl_context=ssl_context,  # Use the custom SSL context
                    starttls=False) as imbox:
                
                # Check for new messages
                inbox_messages_from = imbox.messages(
                    sent_from=sender, 
                    subject=subject, 
                    unread=True
                )
                
                # Process latest message if any
                for uid, message in inbox_messages_from:
                    email_body = message.body['plain'][0]
                    logger.info(f"New message received: {email_body}")
                    call_trade_endpoint(email_body)
                    imbox.mark_seen(uid)
                    break  # Only process the latest message
                
            # Sleep before next check
            logger.debug(f"Waiting for {interval} seconds")
            time.sleep(interval)
            
        except Exception as e:
            logger.error(f"Error monitoring emails: {e}")
            time.sleep(interval)  # Wait before retrying

if __name__ == "__main__":
    # Email credentials and settings
    USERNAME = "cryptotradrrs@gmail.com"
    PASSWORD = os.getenv("APP_PASSWORD")
    SENDER = "trend-alert@mangoresearch.co"
    CHECK_INTERVAL = 5  # seconds
    
    # Start monitoring
    monitor_emails(
        username=USERNAME,
        password=PASSWORD,
        sender=SENDER,
        interval=CHECK_INTERVAL
    )