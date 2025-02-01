import os
import pickle
import base64
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

TOKEN_FILE = os.getenv("TOKEN_FILE")

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

def fetch_latest_email(history_id):
    creds = get_credentials()
    if not creds:
        print("No valid credentials found.")
        return

    try:
        service = build("gmail", "v1", credentials=creds)
        messages = service.users().messages().list(userId="me", maxResults=1, labelIds=["CATEGORY_PERSONAL"]).execute()
        if "messages" in messages:
            msg_id = messages["messages"][0]["id"]
            message = service.users().messages().get(userId="me", id=msg_id).execute()
            
            headers = message["payload"]["headers"]
            sender = next(header["value"] for header in headers if header["name"] == "From")
            subject = next(header["value"] for header in headers if header["name"] == "Subject")
            body = ""
            if "parts" in message["payload"]:
                for part in message["payload"]["parts"]:
                    if part["mimeType"] == "text/plain":
                        body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                        break
            
            print("Sender:", sender)
            print("Subject:", subject)
            print("Body:", body)
    except HttpError as error:
        print(f"An error occurred: {error}")
