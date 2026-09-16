import requests

r = requests.get("http://127.0.0.1:16333/collections", timeout=10)
print(r.status_code, r.text)