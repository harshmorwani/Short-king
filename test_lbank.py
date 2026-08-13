import requests

URL = "https://lbkperp.lbank.com/cfd/openApi/v1/pub/marketData"

print("Testing LBank Futures REST API...")

r = requests.get(
    URL,
    params={"productGroup": "SwapU"},
    timeout=20
)

print("STATUS:", r.status_code)
print("RESPONSE:")
print(r.text[:5000])
