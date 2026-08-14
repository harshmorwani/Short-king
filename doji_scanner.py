import json
import os
import time
from datetime import datetime, timezone

import requests
from websocket import create_connection


LBANK_REST = "https://lbkperp.lbank.com"
LBANK_WS = "wss://lbkperpws.lbank.com/ws"

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TOP_N = 20
DOJI_MAX_BODY_PCT = 10.0
WS_TIMEOUT = 20


def get_json(url, params=None):
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    data = r.json()

    if str(data.get("result", "")).lower() not in ("true", "success", ""):
        raise RuntimeError(f"LBank error: {data}")

    return data


def get_top_losers():
    instruments = get_json(
        f"{LBANK_REST}/cfd/openApi/v1/pub/instrument",
        {"productGroup": "SwapU"},
    ).get("data", [])

    allowed = {
        str(x.get("symbol", "")).upper()
        for x in instruments
        if str(x.get("clearCurrency", "")).upper() == "USDT"
    }

    market_data = get_json(
        f"{LBANK_REST}/cfd/openApi/v1/pub/marketData",
        {"productGroup": "SwapU"},
    ).get("data", [])

    rows = []

    for x in market_data:
        symbol = str(x.get("symbol", "")).upper()

        if symbol not in allowed:
            continue

        try:
            open_price = float(x["openPrice"])
            last_price = float(x["lastPrice"])
            turnover = float(x.get("turnover", 0) or 0)

            if open_price <= 0:
                continue

            change = (last_price - open_price) / open_price * 100.0

            if change < 0:
                rows.append(
                    (symbol, change, turnover, last_price)
                )

        except (KeyError, TypeError, ValueError):
            continue

    rows.sort(key=lambda x: x[1])

    return rows[:TOP_N]


def get_last_closed_kbar(symbol):
    """
    Request 1-hour candles through the LBank futures WebSocket.

    We request two candles and use the older candle so that
    the currently forming candle is ignored.
    """

    ws = create_connection(
        LBANK_WS,
        timeout=WS_TIMEOUT
    )

    try:
        payload = {
            "action": "request",
            "request": "kbar",
            "kbar": "1hr",
            "pair": symbol,
            "size": "2",
        }

        ws.send(json.dumps(payload))

        deadline = time.time() + WS_TIMEOUT

        while time.time() < deadline:

            raw = ws.recv()

            if not raw:
                continue

            print(f"WebSocket {symbol}: {raw[:500]}")

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Direct list response
            if isinstance(msg, list):

                rows = [
                    x for x in msg
                    if isinstance(x, list) and len(x) >= 6
                ]

                if len(rows) >= 2:
                    return rows[-2]

                if len(rows) == 1:
                    return rows[0]

            # Dictionary response
            if isinstance(msg, dict):

                data = msg.get("data")

                if isinstance(data, list):

                    rows = [
                        x for x in data
                        if isinstance(x, list) and len(x) >= 6
                    ]

                    if len(rows) >= 2:
                        return rows[-2]

                    if len(rows) == 1:
                        return rows[0]

                # Some responses may contain kbar directly
                kbar = msg.get("kbar")

                if isinstance(kbar, list) and len(kbar) >= 6:
                    return kbar

        raise RuntimeError(
            f"No kbar response received for {symbol}"
        )

    finally:
        ws.close()


def normalize_kbar(raw):

    if not raw or len(raw) < 6:
        raise ValueError(f"Bad kbar: {raw}")

    ts = int(float(raw[0]))

    if ts > 10**12:
        ts //= 1000

    o = float(raw[1])
    h = float(raw[2])
    l = float(raw[3])
    c = float(raw[4])
    v = float(raw[5])

    return ts, o, h, l, c, v


def is_doji(o, h, l, c):

    candle_range = h - l

    if candle_range <= 0:
        return False, 0.0

    body_pct = abs(c - o) / candle_range * 100.0

    return body_pct <= DOJI_MAX_BODY_PCT, body_pct


def fmt_price(x):

    if x >= 100:
        return f"{x:,.2f}"

    if x >= 1:
        return f"{x:,.4f}"

    if x >= 0.01:
        return f"{x:,.6f}"

    return f"{x:.10f}".rstrip("0").rstrip(".")


def send_telegram(text):

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    r = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
        },
        timeout=15,
    )

    r.raise_for_status()


def main():

    print("Getting LBank futures losers...")

    losers = get_top_losers()

    print(
        "Top losers:",
        [(s, round(ch, 2)) for s, ch, _, _ in losers]
    )

    alerts = []
    errors = []

    for symbol, change, turnover, last_price in losers:

        print(f"\nChecking {symbol}...")

        try:

            raw = get_last_closed_kbar(symbol)

            ts, o, h, l, c, v = normalize_kbar(raw)

            doji, body_pct = is_doji(
                o,
                h,
                l,
                c
            )

            print(
                f"{symbol}: "
                f"O={o} H={h} L={l} C={c} "
                f"Body={body_pct:.2f}% "
                f"Doji={doji}"
            )

            if doji:

                candle_time = datetime.fromtimestamp(
                    ts,
                    tz=timezone.utc
                ).strftime(
                    "%Y-%m-%d %H:%M UTC"
                )

                alert = "\n".join(
                    [
                        "🔔 1H DOJI DETECTED",
                        "",
                        f"LBank Futures: {symbol}",
                        f"24H change: {change:.2f}%",
                        f"Candle: {candle_time}",
                        "",
                        f"Open:  {fmt_price(o)}",
                        f"High:  {fmt_price(h)}",
                        f"Low:   {fmt_price(l)}",
                        f"Close: {fmt_price(c)}",
                        f"Body:  {body_pct:.2f}% of range",
                        f"Volume: {v:,.4f}",
                    ]
                )

                alerts.append(alert)

        except Exception as e:

            print(f"ERROR {symbol}: {e}")

            errors.append(
                f"{symbol}: {e}"
            )

    if alerts:

        print(
            f"\nSending {len(alerts)} Telegram alert(s)..."
        )

        for alert in alerts:
            send_telegram(alert)

    print(
        f"\nDoji alerts: {len(alerts)}"
    )

    if errors:

        print("\nErrors:")

        for error in errors:
            print(" -", error)


if __name__ == "__main__":
    main()
