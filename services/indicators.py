import pandas as pd
import ta


def add_basic_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona alguns indicadores básicos ao DataFrame de candles:
    - SMA 9
    - SMA 21
    - RSI 14
    - MACD (linha e sinal)
    """
    df = df.copy()

    # Médias móveis simples
    df["sma_fast"] = df["close"].rolling(window=9).mean()
    df["sma_slow"] = df["close"].rolling(window=21).mean()

    # RSI 14
    rsi_ind = ta.momentum.RSIIndicator(close=df["close"], window=14)
    df["rsi"] = rsi_ind.rsi()

    # MACD
    macd_ind = ta.trend.MACD(close=df["close"])
    df["macd"] = macd_ind.macd()
    df["macd_signal"] = macd_ind.macd_signal()

    return df
