import os
import requests
import base64
from flask import Flask, request, jsonify
from datetime import datetime
from openai import OpenAI

app = Flask(__name__)

# --- CONFIG FROM ENV ---
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "urdock_verify_123")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Fix for proxies error
client = OpenAI(api_key=OPENAI_API_KEY)

# --- HELPER: Send WhatsApp Message ---
def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    r = requests.post(url, headers=headers, json=payload)
    print(f"Send Response: {r.text}")
    return r

@app.route("/")
def home():
    return "Bot is Running"

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("WEBHOOK VERIFIED")
        return challenge, 200
    return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(f"Incoming: {data}")
    try:
        if data.get("object") == "whatsapp_business_account":
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if "messages" in value:
                        msg = value["messages"][0]
                        from_number = msg["from"]
                        text_body = msg["text"]["body"]

                        # --- AI LOGIC ---
                        try:
                            completion = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{"role": "user", "content": text_body}]
                            )
                            reply_text = completion.choices[0].message.content
                        except Exception as ai_e:
                            print(f"AI Error: {ai_e}")
                            reply_text = "Hi! I am Urdoc Bot 🤖"

                        send_whatsapp_message(from_number, reply_text)
    except Exception as e:
        print(f"Error in webhook: {e}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
