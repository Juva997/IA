import requests

url = "http://127.0.0.1:8000/query"
payload = {"goal": "teste de debug"}

try:
    r = requests.post(url, json=payload, timeout=10)
    print(r.status_code)
    print(r.text)
except Exception as e:
    print("request error:", e)
