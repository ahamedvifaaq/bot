"""
Test trade: places a BUY on BTCUSDT via Binance Futures Testnet.
"""
import dotenv, logging, sys, os, json
dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

sys.path.insert(0, os.path.dirname(__file__))
from core.trader import BinanceFuturesTrader

trader = BinanceFuturesTrader()

if not trader.enabled:
    print("\nAPI keys not found.\n")
    sys.exit(1)

# Step 1: Check balance
print("\n[BALANCE CHECK]")
data, status = trader._request("GET", "/fapi/v2/balance", {})
if status == 200:
    for b in data:
        if float(b.get("balance", 0)) > 0:
            print(f"  {b['asset']}: {b['balance']}")
else:
    print(f"Balance check failed: {data}")
    sys.exit(1)

# Step 2: Get current BTCUSDT price
print("\n[FETCHING PRICE]")
import requests
price_resp = requests.get("https://testnet.binancefuture.com/fapi/v1/ticker/price",
                          params={"symbol": "BTCUSDT"}, timeout=10)
current_price = float(price_resp.json()["price"])
print(f"  BTCUSDT price: {current_price}")

# Step 3: Place test trade
sl_price = round(current_price * 0.994, 2)
tp_price = round(current_price * 1.012, 2)

test_signal = {
    "PAIR": "BTCUSDT",
    "TIMEFRAME": "5m",
    "TYPE": "BUY",
    "ENTRY": current_price,
    "STOP_LOSS": sl_price,
    "TAKE_PROFIT": f"{tp_price} / {round(current_price * 1.024, 2)} / {round(current_price * 1.036, 2)}",
    "PROBABILITY": "85%",
    "TIMESTAMP": "TEST",
}

print(f"\n[PLACING TRADE]")
print(f"  Entry:    {current_price}")
print(f"  SL:       {sl_price}")
print(f"  TP1:      {tp_price}")
print(f"  Leverage: {trader.leverage}x | Size: {trader.trade_usdt} USDT\n")

result = trader.execute_signal(test_signal)

print("\n" + "="*60)
if result:
    entry = result.get("entry", {})
    print("TRADE EXECUTED SUCCESSFULLY!")
    print(f"  Order ID:    {entry.get('orderId', 'N/A')}")
    print(f"  Status:      {entry.get('status', 'N/A')}")
    print(f"  Filled Qty:  {entry.get('executedQty', 'N/A')}")
    print(f"  Avg Price:   {entry.get('avgPrice', 'N/A')}")

    sl_info = result.get("stop_loss", {})
    tp_info = result.get("take_profit", {})
    print(f"  SL Order:    {sl_info.get('orderId', sl_info)}")
    print(f"  TP Order:    {tp_info.get('orderId', tp_info)}")
    print(f"\n  [FULL RESPONSE]")
    print(json.dumps(result, indent=2, default=str))
else:
    print("TRADE FAILED -- check logs above.")
print("="*60)
