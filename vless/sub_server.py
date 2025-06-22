#!/usr/bin/env python3
from flask import Flask, send_file, jsonify
import os
import base64
from datetime import datetime

app = Flask(__name__)

# 配置
HOME = os.path.expanduser("~")
SUB_DIR = os.path.join(HOME, "agsb/sub")
SUB_FILE = os.path.join(SUB_DIR, "sub.txt")
TOKEN_FILE = os.path.join(SUB_DIR, "token")

def read_token():
    try:
        with open(TOKEN_FILE, 'r') as f:
            return f.read().strip()
    except:
        return None

def read_sub_content():
    try:
        with open(SUB_FILE, 'r') as f:
            return f.read().strip()
    except:
        return ""

@app.route('/sub/<token>')
def get_subscription(token):
    valid_token = read_token()
    if not valid_token or token != valid_token:
        return jsonify({"error": "无效的订阅token"}), 403
    
    content = read_sub_content()
    if not content:
        return jsonify({"error": "订阅内容为空"}), 404
    
    return content, 200, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Subscription-Userinfo': 'upload=0; download=0; total=0; expire=0'
    }

@app.route('/sub/status')
def get_server_status():
    return jsonify({
        "status": "running",
        "time": datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080) 