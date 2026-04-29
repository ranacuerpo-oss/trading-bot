import os
import time
import math
import pandas as pd
from dotenv import load_dotenv

from exchange_client import get_exchange
from strategy import generate_signal
from risk import calculate_position_size_usdt

load_dotenv()


def fetch_ohlcv_df(exchange, symbol, timeframe, limit=200):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def get_usdt_balance(exchange):
    balance = exchange.fetch_balance()
    return float(balance["free"].get("USDT", 0))


def get_market_limits(exchange, symbol):
    market = exchange.market(symbol)
    min_amount = market["limits"]["amount"]["min"] or 0
    precision = market["precision"]["amount"] or 6
    return float(min_amount), int(precision)


def round_amount(amount, precision):
    factor = 10 ** precision
    return math.floor(amount * factor) / factor


def usdt_to_base_amount(usdt_size, price):
    if price <= 0:
        return 0
    return usdt_size / price


def main():
    exchange = get_exchange()

    symbol = os.getenv("SYMBOL", "BTC/USDT")
    timeframe = os.getenv("TIMEFRAME", "5m")
    risk_per_trade = float(os.getenv("RISK_PER_TRADE", "0.01"))
    stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "0.02"))
    take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "0.03"))
    max_usdt_per_trade = float(os.getenv("MAX_USDT_PER_TRADE", "100"))

    paper_mode = True  # Cambia a False cuando quieras enviar ordenes reales en testnet

    print("=== BOT INICIADO ===")
    print(f"Par: {symbol} | Timeframe: {timeframe}")
    print(f"Riesgo: {risk_per_trade*100:.2f}% | SL: {stop_loss_pct*100:.2f}% | TP: {take_profit_pct*100:.2f}%")
    print(f"Paper mode: {paper_mode}")
    print()

    while True:
        try:
            df = fetch_ohlcv_df(exchange, symbol, timeframe)
            signal = generate_signal(df)
            last_price = float(df.iloc[-1]["close"])

            usdt_balance = get_usdt_balance(exchange)
            usdt_size = calculate_position_size_usdt(
                balance_usdt=usdt_balance,
                risk_per_trade=risk_per_trade,
                stop_loss_pct=stop_loss_pct,
                max_usdt_per_trade=max_usdt_per_trade
            )

            min_amount, precision = get_market_limits(exchange, symbol)
            base_amount = usdt_to_base_amount(usdt_size, last_price)
            base_amount = round_amount(base_amount, precision)

            print(f"[{df.iloc[-1]['timestamp']}] Precio: {last_price:.2f} | Signal: {signal} | USDT libre: {usdt_balance:.2f}")

            if signal == "buy":
                if base_amount < min_amount:
                    print(f"BUY ignorado: amount {base_amount} < min_amount {min_amount}")
                else:
                    sl_price = last_price * (1 - stop_loss_pct)
                    tp_price = last_price * (1 + take_profit_pct)

                    if paper_mode:
                        print(f"[PAPER BUY] amount={base_amount} @ {last_price:.2f} | SL={sl_price:.2f} | TP={tp_price:.2f}")
                    else:
                        order = exchange.create_market_buy_order(symbol, base_amount)
                        print(f"[BUY REAL] {order}")

            elif signal == "sell":
                # Aqui vendemos solo como demostracion basica
                # En un bot real, validarias posicion abierta antes de vender
                if base_amount < min_amount:
                    print(f"SELL ignorado: amount {base_amount} < min_amount {min_amount}")
                else:
                    if paper_mode:
                        print(f"[PAPER SELL] amount={base_amount} @ {last_price:.2f}")
                    else:
                        order = exchange.create_market_sell_order(symbol, base_amount)
                        print(f"[SELL REAL] {order}")

            else:
                print("Sin señal de entrada/salida.")

        except Exception as e:
            print(f"Error: {e}")

        # Espera 60s (ajusta segun timeframe)
        time.sleep(60)


if __name__ == "__main__":
    main()