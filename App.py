
import os
import requests
import base64
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# --- CONFIG FROM ENV ---
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "urdock_verify_123")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")  # or use Groq/OpenRouter

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
    print("Send Response:", r.text)
    return r.status_code == 200

# --- HELPER: Download Image from WhatsApp ---
def download_whatsapp_image(media_id):
    # Get media URL
    url = f"https://graph.facebook.com/v25.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return None
    media_url = r.json().get("url")
    
    # Download image
    img_r = requests.get(media_url, headers=headers)
    if img_r.status_code == 200:
        return img_r.content
    return None

# --- HELPER: AI Analysis with Vision ---
def analyze_with_ai(user_text, image_bytes=None):
    # If you use OpenAI
    if not OPENAI_API_KEY:
        return "⚠️ OPENAI_API_KEY set nahi hai Render pe. Pehle API key daalo."

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # urDOC Persona Prompt
        system_prompt = '''
        You are urDOC - an advanced AI Wellness Assistant for Aditya.
        Tone: Friendly Hinglish, caring, not too formal.
        Capabilities:
        1. If user sends food pic - estimate calories, protein, health score 1-10, suggest healthier alternative
        2. If medicine/skin/rash pic - give general info, possible causes, precautions, but ALWAYS say "Ye general info hai, doctor se consult karo"
        3. If symptom text - ask follow-up, give possible home remedies, red flags kab doctor ke paas jana hai
        4. If user says "remind me" - acknowledge reminder
        Keep answer short, WhatsApp friendly, use emojis.
        Add disclaimer at end if medical: "Note: Ye AI suggestion hai, final diagnosis ke liye doctor se milo 🙏"
        '''

        if image_bytes:
            b64 = base64.b64encode(image_bytes).decode('utf-8')
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # vision model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_text or "Is image ko analyze karo"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]}
                ],
                max_tokens=500
            )
        else:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                max_tokens=400
            )
        return response.choices[0].message.content

    except Exception as e:
        print("AI Error:", e)
        return f"AI me error aaya: {str(e)[:200]}"

# --- WEBHOOK VERIFICATION (GET) ---
@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("WEBHOOK VERIFIED")
        return challenge, 200
    return "Verification failed", 403

# --- WEBHOOK RECEIVER (POST) ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("Incoming:", data)
    
    try:
        if data.get("object") == "whatsapp_business_account":
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    if not messages:
                        continue
                    
                    msg = messages[0]
                    from_number = msg.get("from")
                    msg_type = msg.get("type")

                    user_text = ""
                    image_bytes = None

                    if msg_type == "text":
                        user_text = msg.get("text", {}).get("body", "")
                    elif msg_type == "image":
                        user_text = msg.get("image", {}).get("caption", "") or "Ye image dekh ke batao kya hai"
                        media_id = msg.get("image", {}).get("id")
                        image_bytes = download_whatsapp_image(media_id)
                        send_whatsapp_message(from_number, "📸 Image mil gayi, analyze kar raha hu... 2 sec")

                    if from_number:
                        # Typing-like delay
                        reply = analyze_with_ai(user_text, image_bytes)
                        send_whatsapp_message(from_number, reply)

    except Exception as e:
        print("Webhook error:", e)

    return jsonify({"status": "ok"}), 200

@app.route("/", methods=["GET"])
def home():
    return "urDOC Bot is Running! Use /webhook for WhatsApp", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
