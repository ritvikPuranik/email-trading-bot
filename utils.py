import os
import pickle
import base64
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

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

def fetch_latest_email(history_id=None):
    creds = get_credentials()
    if not creds:
        print("No valid credentials found.")
        return

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
                    
                    print("Sender:", sender)
                    print("Subject:", subject)
                    print("Body:", body)
                    save_processed_id(msg_id)
                    break
    except HttpError as error:
        print(f"An error occurred: {error}")
