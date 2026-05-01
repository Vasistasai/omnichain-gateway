import sqlite3
import requests

conn = sqlite3.connect('real_crypto.db')
addr = conn.execute("SELECT wallet_address FROM users WHERE username='public'").fetchone()[0]
print("Public wallet:", addr)

url = f"https://api-sepolia.etherscan.io/api?module=account&action=txlist&address={addr}&startblock=0&endblock=99999999&sort=desc"
res = requests.get(url).json()

print("Status:", res.get("status"))
print("Message:", res.get("message"))
print("Result count:", len(res.get("result", [])))
