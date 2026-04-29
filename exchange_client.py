import os
import ccxt
from dotenv import load_dotenv

load_dotenv()


def get_exchange():
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    sandbox = os.getenv("SANDBOX", "true").lower() == "true"

    exchange = ccxt.binance({
        "apiKey": api_key,
        "secret": api_secret,
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })

    if sandbox:
        exchange.set_sandbox_mode(True)

    return exchange