from flask import Flask, request, jsonify
import anthropic
import hmac
import hashlib
import time
import requests
import os

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_SECRET = os.environ.get("BINANCE_SECRET")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
TRADE_SYMBOL = os.environ.get("TRADE_SYMBOL", "BTCUSDT")
TRADE_QUANTITY = os.environ.get("TRADE_QUANTITY", "0.001")

BINANCE_BASE = "https://api.binance.com"

def verify_webhook(data, signature):
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), data, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

def ask_claude(signal: str, symbol: str) -> str:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": (
                f"You are a trading execution assistant. "
                f"A TradingView alert just fired: '{signal}' for {symbol}. "
                f"Reply with ONLY one word: BUY, SELL, or HOLD."
            )
        }]
    )
    return message.content[0].text.strip().upper()

def place_order(side: str, symbol: str, quantity: str):
    timestamp = int(time.time() * 1000)
    params = f"symbol={symbol}&side={side}&type=MARKET&quantity={quantity}&timestamp={timestamp}"
    signature = hmac.new(
        BINANCE_SECRET.encode(), params.encode(), hashlib.sha256
    ).hexdigest()
    url = f"{BINANCE_BASE}/api/v3/order?{params}&signature={signature}"
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    response = requests.post(url, headers=headers)
    return response.json()

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data or "signal" not in data:
        return jsonify({"error": "Invalid payload"}), 400

    signal = data["signal"]
    symbol = data.get("symbol", TRADE_SYMBOL)
    quantity = data.get("quantity", TRADE_QUANTITY)

    decision = ask_claude(signal, symbol)
    print(f"Signal: {signal} | Claude says: {decision}")

    if decision in ["BUY", "SELL"]:
        result = place_order(decision, symbol, quantity)
        return jsonify({"decision": decision, "order": result})
    else:
        return jsonify({"decision": "HOLD", "order": None})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
