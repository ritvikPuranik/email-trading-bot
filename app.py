import os
import pickle
import flask
import base64
import json
from flask import Flask, request, redirect, session, url_for
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from utils import fetch_latest_email, get_credentials
from dotenv import load_dotenv

load_dotenv()

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE")
TOKEN_FILE = os.getenv("TOKEN_FILE")

# OAuth flow
@app.route("/login")
def login():
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=os.getenv("REDIRECT_URI")
    )
    auth_url, _ = flow.authorization_url(prompt="consent")
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth_callback():
    print("OAuth callback function called---------------------------------")
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=os.getenv("REDIRECT_URI")
    )
    flow.fetch_token(authorization_response=request.url)
    
    creds = flow.credentials
    print("Access Token:", creds.token)  # Log the access_token to the console
    with open(TOKEN_FILE, "wb") as token:
        pickle.dump(creds, token)

    return "Authentication successful! You can now receive email notifications."

# Gmail Watch function
def set_watch():
    creds = get_credentials()
    if not creds:
        print("User not authenticated. Redirect to /login")
        return "Please authenticate via /login"

    service = build("gmail", "v1", credentials=creds)
    request_body = {
        "labelIds": ["INBOX"],
        "topicName": "projects/beaming-ring-449419-b3/topics/Check-Email",  # Replace with your Pub/Sub topic
    }
    try:
        response = service.users().watch(userId="me", body=request_body).execute()
        print("Watch request sent:", response)
        return response
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

# Webhook for receiving notifications
@app.route("/gmail-webhook", methods=["POST"])
def gmail_webhook():
    print("Webhook received:")
    data = request.json
    encoded_message = data["message"]["data"]

    # Decode Base64
    decoded_bytes = base64.b64decode(encoded_message)
    decoded_message = decoded_bytes.decode("utf-8")  # Convert to string

    print("Decoded Message:", decoded_message)

    # Call fetch_latest_email with the historyId from the decoded message
    message_data = json.loads(decoded_message)
    history_id = message_data.get("historyId")
    if history_id:
        fetch_latest_email(history_id)

    return "", 200  # Acknowledge receipt

@app.route("/")
def home():
    return "Gmail Webhook Server Running! <a href='/login'>Login with Google</a>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
