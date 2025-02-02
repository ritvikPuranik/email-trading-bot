'''
Description: This script sets up a Flask server that listens for Gmail notifications using a webhook. 
It parses the email and places a trade based on the email content. 
The script also includes a function to set up a Gmail watch request and a webhook to receive notifications. 
The script uses the Google API client library to interact with Gmail and the Binance API to place trades. 
The script also includes OAuth flow for user authentication and a function to fetch the latest email using the Gmail API. The script is designed to be run as a standalone server using ngrok.
''' 

# 
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
from utils import fetch_latest_email, get_credentials, parse_email_content, place_trade
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
        "topicName": os.getenv("GOOGLE_TOPIC"),
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
    data = request.json
    encoded_message = data["message"]["data"]

    # Decode Base64
    decoded_bytes = base64.b64decode(encoded_message)
    decoded_message = decoded_bytes.decode("utf-8")  # Convert to string

    # Call fetch_latest_email with the historyId from the decoded message
    message_data = json.loads(decoded_message)
    history_id = message_data.get("historyId")
    if history_id:
        _, body = fetch_latest_email(history_id)
        if body:
            symbol, side, scale = parse_email_content(body)

            if symbol and side:
                place_trade(symbol, side, scale)

    # Acknowledge the subscription
    return json.dumps({"status": "success"}), 201  # Acknowledge receipt

@app.route("/")
def home():
    return "Gmail Webhook Server Running! <a href='/login'>Login with Google</a>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
