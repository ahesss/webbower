import eventlet
eventlet.monkey_patch()

import os
import sys
import time
import json
import requests
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from requests.adapters import HTTPAdapter

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "bower_mega_brutal_2026")

# SocketIO setup with eventlet
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Config SMSBower
API_BASE = "https://smsbower.com/stubs/handler_api.php"
SERVICE = "wa"

# Persistent HTTP Session for maximum speed (Fast Handshake)
http_session = requests.Session()
adapter = HTTPAdapter(pool_connections=100, pool_maxsize=200)
http_session.mount("https://", adapter)
http_session.mount("http://", adapter)

autobuy_active = {}

def api_req(key, action, **kwargs):
    if not key: return "ERR_NO_KEY"
    p = {'api_key': key, 'action': action}
    p.update(kwargs)
    try:
        # Ultra fast timeout for 1.5s like Hayuk1
        r = http_session.get(API_BASE, params=p, timeout=1.5)
        return r.text.strip()
    except:
        return "ERR_HTTP"

@app.route('/')
def index():
    return render_template('index.html')

# Keep proxy for manual actions if needed
@app.route('/api/proxy')
def proxy():
    api_key = request.args.get('api_key')
    if not api_key: return "ERROR: No API Key", 400
    params = request.args.to_dict()
    try:
        r = http_session.get(API_BASE, params=params, timeout=5)
        return r.text
    except:
        return "ERR_HTTP"

# =============================================
# SOCKET EVENTS (WAR MODE)
# =============================================
@socketio.on('init_session')
def on_init(data):
    key = data.get('api_key')
    if key:
        join_room(key)
        if autobuy_active.get(key):
            emit('autobuy_started', {'status': 'active'})

@socketio.on('get_balance')
def on_bal(data):
    key = data.get('api_key')
    res = api_req(key, 'getBalance')
    if 'ACCESS_BALANCE' in res:
        emit('balance_update', {'balance': res.split(':')[-1]})

def otp_worker(room_key, api_key, aid, st):
    """Monitors OTP in background without blocking the main loop"""
    while True:
        # 20 minutes timeout
        if (time.time() - st) > 1200:
            api_req(api_key, 'setStatus', status='8', id=aid)
            socketio.emit('order_update', {'id': aid, 'status': 'timeout'}, room=room_key)
            break
        
        r = api_req(api_key, 'getStatus', id=aid)
        if r.startswith('STATUS_OK'):
            code = r.split(':')[-1]
            api_req(api_key, 'setStatus', status='6', id=aid)
            socketio.emit('order_update', {'id': aid, 'status': 'got_otp', 'code': code}, room=room_key)
            break
        elif r == 'STATUS_CANCEL' or 'CANCEL' in r:
            socketio.emit('order_update', {'id': aid, 'status': 'cancelled'}, room=room_key)
            break
        
        # Check every 4 seconds to avoid rate limiting
        socketio.sleep(4)

@socketio.on('start_autobuy')
def on_auto(data):
    key = data.get('api_key')
    country_id = data.get('country_id')
    max_price = data.get('max_price')
    
    if autobuy_active.get(key): return
    autobuy_active[key] = True
    
    # 150 Workers for MEGA BRUTAL speed
    NUM_WORKERS = 150

    def single_worker(shared):
        while autobuy_active.get(key):
            try:
                res = api_req(key, 'getNumber', service=SERVICE, country=country_id, maxPrice=max_price)
                shared['att'] += 1
                if 'ACCESS_NUMBER' in res:
                    parts = res.split(':')
                    if len(parts) >= 3:
                        aid, num = parts[1], parts[2]
                        shared['found'] += 1
                        order = {
                            'id': aid, 
                            'number': num, 
                            'status': 'waiting', 
                            'order_time': time.time(), 
                            'price': max_price,
                            'country_id': country_id
                        }
                        socketio.emit('new_number', order, room=key)
                        socketio.start_background_task(otp_worker, key, key, aid, order['order_time'])
                    socketio.sleep(0.001)
                elif 'NO_BALANCE' in res:
                    autobuy_active[key] = False
                    socketio.emit('error_msg', {'message': '💸 SALDO HABIS!'}, room=key)
                    break
                elif 'NO_NUMBERS' in res:
                    # War mode: tiny sleep to stay aggressive
                    socketio.sleep(0.01)
                elif 'ERR_HTTP' in res or 'ERROR' in res:
                    socketio.sleep(0.05)
                else:
                    socketio.sleep(0.005)
            except:
                socketio.sleep(0.05)

    def stats_loop(shared):
        st = time.time()
        socketio.emit('autobuy_started', {'status': 'active'}, room=key)
        while autobuy_active.get(key):
            el = int(time.time() - st)
            socketio.emit('autobuy_stats', {
                'attempts': shared['att'],
                'found': shared['found'],
                'elapsed': el,
                'speed': round(shared['att']/max(el,1), 1)
            }, room=key)
            socketio.sleep(0.5)
        
        socketio.emit('autobuy_stopped', {}, room=key)

    shared = {'att': 0, 'found': 0}
    
    # Launch Workers
    for i in range(NUM_WORKERS):
        socketio.start_background_task(single_worker, shared)
    
    # Launch Stats
    socketio.start_background_task(stats_loop, shared)

@socketio.on('stop_autobuy')
def on_stop(data):
    key = data.get('api_key')
    if key: autobuy_active[key] = False

@socketio.on('cancel_order')
def on_cancel(data):
    key, aid = data.get('api_key'), data.get('id')
    api_req(key, 'setStatus', status='8', id=aid)
    socketio.emit('order_update', {'id': aid, 'status': 'cancelled'}, room=key)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
