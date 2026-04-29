def add_indicators(df):
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=9).mean()
    df["ema_slow"] = df["close"].ewm(span=21).mean()
    return df


def generate_signal(df):
    """
    Retorna: 'buy', 'sell' o 'hold'
    """
    if len(df) < 30:
        return "hold"

    df = add_indicators(df)

    prev = df.iloc[-2]
    last = df.iloc[-1]

    crossed_up = prev["ema_fast"] <= prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
    crossed_down = prev["ema_fast"] >= prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]

    if crossed_up:
        return "buy"
    if crossed_down:
        return "sell"
    return "hold"