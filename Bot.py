from flask import Flask, request
import requests
import json
import os

app = Flask(__name__)

# LOAD CONFIG
with open("config.json") as f:
    config = json.load(f)

API_KEY = config["api_key"]
PRODUCT_ID = config["product_id"]
RISK_PER_TRADE = config["risk_per_trade"]

# TELEGRAM
BOT_TOKEN = config["telegram_token"]
CHAT_ID = config["chat_id"]

BASE_URL = "https://api.delta.exchange"

trading_enabled = True
daily_loss = 0
MAX_DAILY_LOSS = 2
TRADE_COUNT = 0
MAX_TRADES = 3


# 📲 TELEGRAM MESSAGE
def send_msg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})


# 📲 TELEGRAM BUTTONS
def send_controls():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "▶ START", "callback_data": "start"},
                {"text": "⛔ STOP", "callback_data": "stop"}
            ]
        ]
    }

    data = {
        "chat_id": CHAT_ID,
        "text": "Control your trading bot:",
        "reply_markup": keyboard
    }

    requests.post(url, json=data)


# 📊 CALCULATE POSITION SIZE
def calculate_size():
    capital = 10  # your capital
    risk_amount = capital * RISK_PER_TRADE
    return round(risk_amount * 5, 2)


# 💰 PLACE ORDER WITH REAL SL/TP
def place_order(side):
    global TRADE_COUNT, daily_loss

    if not trading_enabled:
        return "Trading disabled"

    if TRADE_COUNT >= MAX_TRADES:
        send_msg("Max trades reached today")
        return

    if daily_loss >= MAX_DAILY_LOSS:
        send_msg("Daily loss limit hit. Bot stopped.")
        return

    size = calculate_size()

    headers = {"api-key": API_KEY}

    # 1. MARKET ORDER
    order = {
        "product_id": PRODUCT_ID,
        "size": size,
        "side": side,
        "order_type": "market"
    }

    r = requests.post(BASE_URL + "/v2/orders", json=order, headers=headers)
    response = r.json()

    send_msg(f"{side.upper()} ORDER EXECUTED")

    entry_price = float(response.get("average_fill_price", 0))

    if entry_price == 0:
        send_msg("Error getting entry price")
        return

    # 2. SL & TP CALCULATION
    if side == "buy":
        stop_loss = entry_price * 0.99
        take_profit = entry_price * 1.02
        exit_side = "sell"
    else:
        stop_loss = entry_price * 1.01
        take_profit = entry_price * 0.98
        exit_side = "buy"

    # 3. STOP LOSS
    sl_order = {
        "product_id": PRODUCT_ID,
        "size": size,
        "side": exit_side,
        "order_type": "stop_market",
        "stop_price": round(stop_loss, 2)
    }

    # 4. TAKE PROFIT
    tp_order = {
        "product_id": PRODUCT_ID,
        "size": size,
        "side": exit_side,
        "order_type": "limit",
        "limit_price": round(take_profit, 2)
    }

    requests.post(BASE_URL + "/v2/orders", json=sl_order, headers=headers)
    requests.post(BASE_URL + "/v2/orders", json=tp_order, headers=headers)

    send_msg(f"SL: {round(stop_loss,2)} | TP: {round(take_profit,2)}")

    TRADE_COUNT += 1


# 🔔 TRADINGVIEW WEBHOOK
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    action = data.get("action")

    if action == "buy":
        place_order("buy")

    elif action == "sell":
        place_order("sell")

    return "ok"


# 📱 TELEGRAM BUTTON CONTROL
@app.route('/telegram', methods=['POST'])
def telegram():
    global trading_enabled

    data = request.json
    callback = data.get("callback_query", {})
    cmd = callback.get("data")

    if cmd == "start":
        trading_enabled = True
        send_msg("Trading STARTED")

    elif cmd == "stop":
        trading_enabled = False
        send_msg("Trading STOPPED")

    return "ok"


# 🚀 START SERVER
import os

@app.route('/')
def home():
    return "Bot is running"
    
if __name__ == "__main__":
    send_controls()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
