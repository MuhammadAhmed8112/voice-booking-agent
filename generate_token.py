"""
Run this ONCE locally to generate token.json.
Then paste the contents of token.json into HuggingFace Spaces secret: GOOGLE_TOKEN_JSON

Usage:
    python generate_token.py
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

token_json = creds.to_json()

with open("token.json", "w") as f:
    f.write(token_json)

print("\nDone! token.json created.")
print("Now paste the contents below into HuggingFace Spaces secret: GOOGLE_TOKEN_JSON\n")
print(token_json)
