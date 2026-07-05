import sqlite3
import json
import hashlib
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

DB_PATH = '/home/minetest/.minetest/worlds/voxelibre/mod_storage.sqlite'

STATUS_PRIVS = {
    'basic':   ['interact', 'shout'],
    'vip':     ['interact', 'shout', 'fly', 'fast', 'home'],
    'premium': ['interact', 'shout', 'fly', 'fast', 'home', 'noclip', 'teleport'],
    'admin':   ['interact', 'shout', 'fly', 'fast', 'home', 'noclip', 'teleport', 'setspawn', 'ban', 'kick'],
}

def hash_password(username, password):
    return hashlib.sha1(f'{username}:{password}'.encode()).hexdigest()

def get_player(username):
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT key, value FROM entries WHERE modname='auth_laravel'"
        ).fetchall()
        conn.close()
        for k, v in rows:
            key = k.decode('utf-8') if isinstance(k, bytes) else k
            val = v.decode('utf-8') if isinstance(v, bytes) else v
            if key == f'player:{username}':
                return json.loads(val)
        return None
    except Exception as e:
        return None

def save_player(username, data):
    try:
        conn = sqlite3.connect(DB_PATH)
        target_key = f'player:{username}'.encode('utf-8')
        conn.execute(
            "INSERT OR REPLACE INTO entries (modname, key, value) VALUES ('auth_laravel', ?, ?)",
            (target_key, json.dumps(data).encode('utf-8'))
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/login', methods=['POST'])
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''

    if not username or not password:
        return jsonify({'ok': False, 'error': 'Заполните все поля.'}), 400

    data = get_player(username)
    if not data:
        return jsonify({'ok': False, 'error': 'Аккаунт не найден.'}), 401

    if data.get('password_hash') != hash_password(username, password):
        return jsonify({'ok': False, 'error': 'Неверный пароль.'}), 401

    if data.get('banned_until'):
        import time
        if data['banned_until'] > int(time.time()):
            remaining = (data['banned_until'] - int(time.time())) // 60
            return jsonify({'ok': False, 'error': f'Вы забанены. Осталось: {remaining} мин.'}), 403

    return jsonify({
        'ok': True,
        'username': username,
        'status': data.get('status', 'basic'),
    })

@app.route('/api/register', methods=['POST'])
def register():
    body = request.get_json(silent=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''

    if not username or not password:
        return jsonify({'ok': False, 'error': 'Заполните все поля.'}), 400

    if len(password) < 4:
        return jsonify({'ok': False, 'error': 'Пароль слишком короткий.'}), 400

    if get_player(username):
        return jsonify({'ok': False, 'error': 'Этот никнейм уже занят.'}), 409

    data = {
        'password_hash': hash_password(username, password),
        'status': 'basic',
        'privileges': STATUS_PRIVS['basic'],
    }

    if save_player(username, data):
        return jsonify({'ok': True, 'username': username, 'status': 'basic'})
    return jsonify({'ok': False, 'error': 'Ошибка сервера.'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
