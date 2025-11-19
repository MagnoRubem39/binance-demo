import os
import math

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
import pandas as pd


class BinanceConfigError(Exception):
    """Erro de configuração (falta API key/secret)."""
    pass


def get_client() -> Client:
    """Cria e devolve um cliente da Binance configurado para a Spot Testnet."""
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        raise BinanceConfigError(
            "BINANCE_API_KEY ou BINANCE_API_SECRET não estão configurados no .env."
        )

    # testnet=True ajusta endpoints para Spot Testnet
    client = Client(api_key, api_secret, testnet=True)
    return client


def get_non_zero_balances():
    """
    Retorna apenas os saldos com valor > 0 (free ou locked).
    Usado na tela inicial.
    """
    client = get_client()
    account_info = client.get_account()
    balances = account_info.get("balances", [])

    non_zero = []
    for b in balances:
        free = float(b.get("free", 0))
        locked = float(b.get("locked", 0))
        if free > 0 or locked > 0:
            non_zero.append(
                {
                    "asset": b.get("asset"),
                    "free": free,
                    "locked": locked,
                }
            )
    return non_zero


def get_klines_dataframe(
    symbol: str = "BTCUSDT",
    interval: str = Client.KLINE_INTERVAL_1HOUR,
    limit: int = 100,
) -> pd.DataFrame:
    """
    Busca candles (klines) da Binance e devolve um DataFrame com colunas numéricas.
    """
    client = get_client()
    raw = client.get_klines(symbol=symbol, interval=interval, limit=limit)

    df = pd.DataFrame(
        raw,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )

    # Converte timestamps
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

    # Converte preços/volume para float
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df


# ---------- NOVO: helpers de LOT_SIZE ----------

def _get_lot_size_filter(symbol: str):
    """
    Busca o filtro LOT_SIZE para o símbolo informado.
    """
    client = get_client()
    info = client.get_symbol_info(symbol.upper())
    if not info:
        raise ValueError(f"Símbolo inválido: {symbol}")

    for f in info["filters"]:
        if f["filterType"] == "LOT_SIZE":
            return f

    raise ValueError(f"Nenhum filtro LOT_SIZE encontrado para {symbol}")


def adjust_quantity_to_lot(symbol: str, quantity: float) -> float:
    """
    Ajusta a quantidade para respeitar:
    - minQty (mínimo)
    - stepSize (múltiplos do tamanho de lote)
    Devolve a quantidade ajustada como float.
    """
    lot = _get_lot_size_filter(symbol)
    min_qty = float(lot["minQty"])
    step_size = float(lot["stepSize"])
    step_str = lot["stepSize"]  # string para saber quantas casas decimais

    # Garante pelo menos o mínimo
    qty = max(quantity, min_qty)

    # Quantiza para o múltiplo do step (floor)
    if step_size > 0:
        steps = math.floor(qty / step_size)
        qty = steps * step_size

    # Calcula número de casas decimais suportado pelo step
    if "." in step_str:
        decimals = len(step_str.rstrip("0").split(".")[1])
    else:
        decimals = 0

    qty = float(f"{qty:.{decimals}f}")
    return qty


def place_market_order(symbol: str, side: str, quantity: float):
    """
    Envia uma ordem de mercado na Spot Testnet.
    side: 'BUY' ou 'SELL'
    quantity: quantidade base desejada (ex: 0.001 para BTCUSDT).
    A função ajusta a quantidade para respeitar o LOT_SIZE.
    """
    client = get_client()

    side = side.upper()
    if side not in ("BUY", "SELL"):
        raise ValueError("Side inválido, use 'BUY' ou 'SELL'.")

    if quantity <= 0:
        raise ValueError("Quantidade deve ser maior que zero.")

    # Ajusta para LOT_SIZE (mínimo + step)
    adj_quantity = adjust_quantity_to_lot(symbol, quantity)

    try:
        order = client.create_order(
            symbol=symbol.upper(),
            side=side,
            type=Client.ORDER_TYPE_MARKET,
            quantity=str(adj_quantity),  # manda como string para evitar problemas de float
        )
        return order
    except (BinanceAPIException, BinanceRequestException) as e:
        # Deixa a exception subir para ser tratada na rota Flask
        raise
