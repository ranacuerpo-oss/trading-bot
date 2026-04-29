def calculate_position_size_usdt(balance_usdt, risk_per_trade, stop_loss_pct, max_usdt_per_trade):
    """
    balance_usdt: dinero disponible en USDT
    risk_per_trade: ej 0.01 (1%)
    stop_loss_pct: ej 0.02 (2%)
    max_usdt_per_trade: tope por operación

    Devuelve cuánto USDT usar en la operación.
    """
    risk_amount = balance_usdt * risk_per_trade
    if stop_loss_pct <= 0:
        return 0

    suggested_size = risk_amount / stop_loss_pct
    final_size = min(suggested_size, max_usdt_per_trade, balance_usdt)
    return max(final_size, 0)