from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
import os
import csv
import json
from datetime import datetime, timezone

load_dotenv()
app = Flask(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "cambia_esto")
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.02"))
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.03"))
PAPER_BALANCE = float(os.getenv("PAPER_BALANCE", "10000"))
MAX_USDT_PER_TRADE = float(os.getenv("MAX_USDT_PER_TRADE", "100"))
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "900"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "10"))

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

balance = PAPER_BALANCE
position_size = 0.0
entry_price = 0.0
last_signal = ""
last_signal_at = None
last_trade_at = None
trades_today = 0
current_day = datetime.now(timezone.utc).date()

CSV_FILE = os.path.join(DATA_DIR, "trades.csv")

STATE_FILE_ENV = os.getenv("STATE_FILE")
if STATE_FILE_ENV:
    # If it's a filename only, store it inside DATA_DIR. If it's an absolute path, use it as-is.
    STATE_FILE = STATE_FILE_ENV if os.path.isabs(STATE_FILE_ENV) else os.path.join(DATA_DIR, STATE_FILE_ENV)
else:
    STATE_FILE = os.path.join(DATA_DIR, "bot_state.json")

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "symbol", "action", "price", "qty", "balance"])

def calculate_usdt_size(balance_usdt):
    risk_amount = balance_usdt * RISK_PER_TRADE
    suggested = risk_amount / STOP_LOSS_PCT if STOP_LOSS_PCT > 0 else 0
    return max(0, min(suggested, MAX_USDT_PER_TRADE, balance_usdt))

def log_trade(symbol, action, price, qty, balance_now):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.utcnow().isoformat(), symbol, action, price, qty, balance_now])


def utc_now():
    return datetime.now(timezone.utc)


def dt_to_iso(dt):
    return dt.isoformat() if dt else None


def iso_to_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def save_state():
    payload = {
        "balance": balance,
        "position_size": position_size,
        "entry_price": entry_price,
        "last_signal": last_signal,
        "last_signal_at": dt_to_iso(last_signal_at),
        "last_trade_at": dt_to_iso(last_trade_at),
        "trades_today": trades_today,
        "current_day": current_day.isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)


def load_state():
    global balance, position_size, entry_price
    global last_signal, last_signal_at, last_trade_at, trades_today, current_day

    if not os.path.exists(STATE_FILE):
        return

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    balance = float(data.get("balance", PAPER_BALANCE))
    position_size = float(data.get("position_size", 0.0))
    entry_price = float(data.get("entry_price", 0.0))
    last_signal = str(data.get("last_signal", ""))
    last_signal_at = iso_to_dt(data.get("last_signal_at"))
    last_trade_at = iso_to_dt(data.get("last_trade_at"))
    trades_today = int(data.get("trades_today", 0))

    day_str = data.get("current_day")
    try:
        current_day = datetime.fromisoformat(day_str).date() if day_str else utc_now().date()
    except ValueError:
        current_day = utc_now().date()


def roll_daily_counter(now):
    global trades_today, current_day
    today = now.date()
    if today != current_day:
        current_day = today
        trades_today = 0
        save_state()


def seconds_since(dt, now):
    if dt is None:
        return None
    return (now - dt).total_seconds()


def cooldown_active(now):
    if last_trade_at is None:
        return False
    return seconds_since(last_trade_at, now) < COOLDOWN_SECONDS

@app.route("/webhook", methods=["POST"])
def webhook():
    global balance, position_size, entry_price
    global last_signal, last_signal_at, last_trade_at, trades_today

    data = request.json
    if not data:
        return jsonify({"ok": False, "error": "JSON vacio"}), 400

    if data.get("secret") != WEBHOOK_SECRET:
        return jsonify({"ok": False, "error": "secret invalido"}), 403

    signal = str(data.get("signal", "")).lower()  # buy / sell
    symbol = data.get("symbol", "BTCUSDT")
    price = float(data.get("price", 0))

    if price <= 0:
        return jsonify({"ok": False, "error": "price invalido"}), 400

    now = utc_now()
    roll_daily_counter(now)

    # Ignore repeated same-side signals while still in cooldown window.
    if signal == last_signal and last_signal_at is not None:
        repeated_in_seconds = seconds_since(last_signal_at, now)
        if repeated_in_seconds is not None and repeated_in_seconds < COOLDOWN_SECONDS:
            last_signal_at = now
            save_state()
            return jsonify({
                "ok": True,
                "msg": f"Senal repetida ignorada (cooldown {COOLDOWN_SECONDS}s)"
            })

    if cooldown_active(now):
        remaining = int(COOLDOWN_SECONDS - seconds_since(last_trade_at, now))
        last_signal = signal
        last_signal_at = now
        save_state()
        return jsonify({"ok": True, "msg": f"Cooldown activo, espera {remaining}s"})

    if trades_today >= MAX_TRADES_PER_DAY:
        last_signal = signal
        last_signal_at = now
        save_state()
        return jsonify({"ok": True, "msg": "Limite diario de trades alcanzado"})

    if signal == "buy":
        if position_size > 0:
            return jsonify({"ok": True, "msg": "Ya hay posicion abierta, buy ignorado"})
        usdt_size = calculate_usdt_size(balance)
        qty = usdt_size / price
        if qty <= 0:
            return jsonify({"ok": False, "error": "qty calculada invalida"}), 400

        balance -= usdt_size
        position_size = qty
        entry_price = price
        trades_today += 1
        last_trade_at = now
        last_signal = signal
        last_signal_at = now
        log_trade(symbol, "BUY", price, qty, balance)
        save_state()

        return jsonify({
            "ok": True,
            "action": "BUY",
            "symbol": symbol,
            "price": price,
            "qty": qty,
            "balance": balance
        })

    elif signal == "sell":
        if position_size <= 0:
            return jsonify({"ok": True, "msg": "No hay posicion abierta, sell ignorado"})
        usdt_back = position_size * price
        balance += usdt_back
        qty = position_size
        position_size = 0.0
        entry_price = 0.0
        trades_today += 1
        last_trade_at = now
        last_signal = signal
        last_signal_at = now
        log_trade(symbol, "SELL", price, qty, balance)
        save_state()

        return jsonify({
            "ok": True,
            "action": "SELL",
            "symbol": symbol,
            "price": price,
            "qty": qty,
            "balance": balance
        })

    return jsonify({"ok": False, "error": "signal debe ser buy o sell"}), 400

@app.route("/status", methods=["GET"])
def status():
    now = utc_now()
    roll_daily_counter(now)
    cooldown_left = 0
    if cooldown_active(now):
        cooldown_left = int(COOLDOWN_SECONDS - seconds_since(last_trade_at, now))

    return jsonify({
        "balance": balance,
        "position_size": position_size,
        "entry_price": entry_price,
        "risk_per_trade": RISK_PER_TRADE,
        "stop_loss_pct": STOP_LOSS_PCT,
        "take_profit_pct": TAKE_PROFIT_PCT,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "cooldown_left_seconds": cooldown_left,
        "max_trades_per_day": MAX_TRADES_PER_DAY,
        "trades_today": trades_today,
        "state_file": STATE_FILE
    })

@app.route("/trades", methods=["GET"])
def trades_download():
    if not os.path.exists(CSV_FILE):
        return jsonify({"ok": False, "error": "trades.csv no existe aun"}), 404
    return send_file(
        CSV_FILE,
        mimetype="text/csv",
        as_attachment=True,
        download_name="trades.csv",
    )

if __name__ == "__main__":
    init_csv()
    load_state()
    app.run(host="0.0.0.0", port=5000)