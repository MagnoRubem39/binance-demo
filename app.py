import os

import pandas as pd
from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    flash,
    request,
)
from dotenv import load_dotenv

from services.binance_client import (
    get_non_zero_balances,
    BinanceConfigError,
    get_klines_dataframe,
    place_market_order,
)
from services.indicators import add_basic_indicators

# Carrega variáveis do .env
load_dotenv()


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    app.config["PORT"] = int(os.getenv("PORT", 5000))

    @app.route("/")
    def index():
        balances = []
        error_message = None

        try:
            balances = get_non_zero_balances()
        except BinanceConfigError as e:
            # Erro de configuração (chaves não setadas)
            error_message = str(e)
        except Exception as e:
            # Qualquer outro erro da Binance ou rede
            error_message = f"Erro ao conectar na Binance Testnet: {e}"

        return render_template(
            "index.html",
            balances=balances,
            error_message=error_message,
        )

    @app.route("/market-select")
    def market_select():
        """
        Lê o símbolo enviado pelo formulário e redireciona para /market/<symbol>.
        Ex.: ?symbol=ETHUSDT -> /market/ETHUSDT
        """
        symbol = request.args.get("symbol", "").upper().strip()

        if not symbol:
            flash("Informe um par, por exemplo BTCUSDT.", "danger")
            return redirect(url_for("index"))

        return redirect(url_for("market", symbol=symbol))


    @app.route("/market/<symbol>")
    def market(symbol):
        symbol = symbol.upper()
        rows = []
        error_message = None

        try:
            df = get_klines_dataframe(symbol=symbol)
            df = add_basic_indicators(df)

            # Pegamos só os últimos 30 candles para exibir
            latest = df.tail(30).copy().sort_values("open_time", ascending=False)

            for _, r in latest.iterrows():
                rows.append(
                    {
                        "open_time": r["open_time"].strftime("%d/%m %H:%M"),
                        "close": f"{r['close']:.2f}",
                        "sma_fast": f"{r['sma_fast']:.2f}"
                        if pd.notna(r["sma_fast"])
                        else "-",
                        "sma_slow": f"{r['sma_slow']:.2f}"
                        if pd.notna(r["sma_slow"])
                        else "-",
                        "rsi": f"{r['rsi']:.2f}" if pd.notna(r["rsi"]) else "-",
                        "macd": f"{r['macd']:.2f}" if pd.notna(r["macd"]) else "-",
                        "macd_signal": f"{r['macd_signal']:.2f}"
                        if pd.notna(r["macd_signal"])
                        else "-",
                    }
                )
        except BinanceConfigError as e:
            error_message = str(e)
        except Exception as e:
            error_message = f"Erro ao buscar dados de mercado: {e}"

        # Quantidade padrão para a demo
        default_qty = 0.001

        return render_template(
            "market.html",
            symbol=symbol,
            rows=rows,
            error_message=error_message,
            default_qty=default_qty,
        )

    @app.route("/order/<symbol>/<side>", methods=["POST"])
    def order(symbol, side):
        """
        Envia uma ordem de mercado de teste (testnet) e volta para a tela de market.
        """
        symbol = symbol.upper()
        side = side.upper()

        qty_str = request.form.get("quantity", "0.0")
        try:
            quantity = float(qty_str)
        except ValueError:
            flash("Quantidade inválida.", "danger")
            return redirect(url_for("market", symbol=symbol))

        try:
            order = place_market_order(symbol, side, quantity)
            order_id = order.get("orderId")
            flash(
                f"Ordem {side} de {quantity} {symbol} enviada com sucesso (ID {order_id}).",
                "success",
            )
        except Exception as e:
            flash(f"Erro ao enviar ordem: {e}", "danger")

        return redirect(url_for("market", symbol=symbol))

    return app


app = create_app()

if __name__ == "__main__":
    port = app.config.get("PORT", 5000)
    app.run(host="0.0.0.0", port=port, debug=True)
