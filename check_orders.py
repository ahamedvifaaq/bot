"""Check recent orders placed on Binance Futures Testnet."""
import dotenv, os, time, hmac, hashlib, requests, json
from urllib.parse import urlencode
dotenv.load_dotenv()

key = os.getenv("BINANCE_FUTURES_API_KEY")
secret = os.getenv("BINANCE_FUTURES_API_SECRET")
base = "https://testnet.binancefuture.com"

params = {"timestamp": int(time.time() * 1000), "symbol": "BTCUSDT", "limit": 10}
query = urlencode(params)
sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
params["signature"] = sig

r = requests.get(f"{base}/fapi/v1/allOrders", params=params,
                 headers={"X-MBX-APIKEY": key}, timeout=10)
orders = r.json()

print(f"Total orders found: {len(orders)}\n")
for o in orders[-6:]:
    print(f"  ID: {o['orderId']}  |  {o['side']:4s}  |  {o['type']:20s}  |  "
          f"qty={o['executedQty']:>10s}  |  price={o['avgPrice']:>12s}  |  "
          f"status={o['status']}")
