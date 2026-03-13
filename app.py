import os
from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# Config SMSBower
API_BASE = "https://smsbower.com/stubs/handler_api.php"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/proxy')
def proxy():
    action = request.args.get('action')
    api_key = request.args.get('api_key')
    
    if not api_key:
        return jsonify({"error": "No API Key"}), 400
        
    params = request.args.to_dict()
    try:
        # Gunakan timeout yang sedikit lebih longgar untuk proxy agar tidak sering timeout
        r = requests.get(API_BASE, params=params, timeout=10)
        return r.text
    except Exception as e:
        return f"ERR_HTTP: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
