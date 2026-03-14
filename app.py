import os
from flask import Flask, render_template, request, jsonify
import requests
from requests.adapters import HTTPAdapter

app = Flask(__name__)

# Config SMSBower
API_BASE = "https://smsbower.com/stubs/handler_api.php"

# Use Session for better performance (War Mode)
session = requests.Session()
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=100)
session.mount("https://", adapter)
session.mount("http://", adapter)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/proxy')
def proxy():
    api_key = request.args.get('api_key')
    if not api_key:
        return "ERROR: No API Key", 400
        
    params = request.args.to_dict()
    try:
        # Tembak langsung dengan session (Fast Handshake)
        r = session.get(API_BASE, params=params, timeout=10)
        return r.text
    except Exception as e:
        return f"ERR_HTTP: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
