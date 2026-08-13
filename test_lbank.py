import requests

URL = "https://lbkperp.lbank.com/cfd/openApi/v1/pub/marketData"

print("Testing LBank REST API...")

try:
    r = requests.get(
        URL,
        params={"productGroup": "SwapU"},
        timeout=20
    )

    print("Status:", r.status_code)
    print("Response:")
    print(r.text[:3000])

except Exception as e:
    print("ERROR:", e)
