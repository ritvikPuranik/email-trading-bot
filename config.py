import os
import json
from dotenv import load_dotenv

def setup_credentials():
    load_dotenv()
    
    credentials = {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "project_id": os.getenv("GOOGLE_PROJECT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uris": [f"{os.getenv('NGROK_URL')}/oauth2callback"],
            "javascript_origins": [os.getenv("NGROK_URL"), "http://localhost:3000"]
        }
    }
    
    # Write credentials to a file
    credentials_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
    with open(credentials_path, 'w') as f:
        json.dump(credentials, f, indent=4)
    
    return credentials

if __name__ == "__main__":
    setup_credentials()
