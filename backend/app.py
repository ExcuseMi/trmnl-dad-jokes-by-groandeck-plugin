import os
import requests
from flask import Flask, jsonify, abort
from modules.utils.ip_whitelist import init_ip_whitelist, require_trmnl_ip

app = Flask(__name__)

GROANDECK_API_URL = "https://groandeck.com/api/v1/random"
API_KEY = os.environ.get("GROANDECK_API_KEY")


@app.route("/")
@require_trmnl_ip
def random_joke():
    if not API_KEY:
        abort(500, description="GROANDECK_API_KEY not set")

    resp = requests.get(
        GROANDECK_API_URL,
        headers={"X-API-Key": API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    return jsonify(resp.json())


@app.route("/health")
def health():
    return jsonify({"ok": True})


init_ip_whitelist()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
