from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import os, csv, io, json, requests
from database import init_db, get_db_connection

app = Flask(__name__)
app.secret_key = "omnichain_web3_secret_2024"

if not os.path.exists('real_crypto.db'):
    init_db()
else:
    # Safely migrate DB to include email if missing
    import sqlite3
    try:
        conn = get_db_connection()
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass # Column already exists


# ─── Fraud Detection Engine ───────────────────────────────────────────────────
def calculate_risk(amount_eth, receiver_address, user_id):
    risk_level = 'low'
    risk_reason = ''

    if amount_eth >= 1.0:
        risk_level = 'high'
        risk_reason = f'Large transfer: {amount_eth} ETH exceeds 1 ETH threshold'
    elif amount_eth >= 0.5:
        if risk_level != 'high':
            risk_level = 'medium'
            risk_reason = f'Moderate transfer: {amount_eth} ETH'

    conn = get_db_connection()
    repeated = conn.execute(
        'SELECT COUNT(*) FROM transactions WHERE user_id = ? AND receiver_address = ?',
        (user_id, receiver_address)
    ).fetchone()[0]
    conn.close()

    if repeated >= 3:
        risk_level = 'high'
        risk_reason = f'Repeated transfers ({repeated}x) to same address'
    elif repeated >= 2 and risk_level == 'low':
        risk_level = 'medium'
        risk_reason = f'Multiple transfers ({repeated}x) to same address'

    return risk_level, risk_reason

def sync_etherscan_history(wallet_address, user_id):
    if not wallet_address: return
    try:
        # We use Blockscout API because Etherscan recently deprecated free V1 endpoints
        url = f"https://eth-sepolia.blockscout.com/api?module=account&action=txlist&address={wallet_address}"
        res = requests.get(url, timeout=10)
        data = res.json()
        if data.get("status") == "1" and isinstance(data.get("result"), list):
            conn = get_db_connection()
            for tx in data["result"]:
                tx_hash = tx.get("hash")
                # Check if exists
                exists = conn.execute("SELECT id FROM transactions WHERE tx_hash = ?", (tx_hash,)).fetchone()
                if not exists:
                    amount_eth = float(tx.get("value", 0)) / 10**18
                    if amount_eth > 0:  # Only track non-zero ETH transfers
                        sender = tx.get("from", "")
                        receiver = tx.get("to", "")
                        block_number = int(tx.get("blockNumber", 0))
                        gas_used = int(tx.get("gasUsed", 0))
                        
                        risk_level, risk_reason = calculate_risk(amount_eth, receiver, user_id)
                        
                        conn.execute('''INSERT INTO transactions 
                            (user_id, tx_hash, amount_eth, sender_address, receiver_address, block_number, gas_used, status, risk_level, risk_reason)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (user_id, tx_hash, amount_eth, sender, receiver, block_number, gas_used, 'confirmed', risk_level, risk_reason))
            conn.commit()
            conn.close()
    except Exception as e:
        print("Etherscan sync error:", e)

# ─── Auth Routes ──────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard') if session.get('role') == 'Admin' else url_for('user_dashboard'))
    return render_template('login.html')

@app.route('/api/auth', methods=['POST'])
def auth():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()

    if user:
        conn.execute('UPDATE users SET ip_address = ? WHERE id = ?', (ip_address, user['id']))
        conn.commit()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['wallet_address'] = user['wallet_address']
        session['private_key'] = user['private_key']
        session['external_wallet'] = user['external_wallet']
        conn.close()
        return jsonify({"redirect": url_for('admin_dashboard') if user['role'] == 'Admin' else url_for('user_dashboard')})

    conn.close()
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    real_name = data.get('real_name', '').strip()
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not username or not password or not real_name or not email:
        return jsonify({"error": "All fields required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    from eth_account import Account
    import secrets
    new_account = Account.create(secrets.token_hex(32))

    conn = get_db_connection()
    existing = conn.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Username or Email already taken"}), 409

    conn.execute(
        'INSERT INTO users (real_name, username, email, password, role, wallet_address, private_key, ip_address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (real_name, username, email, password, 'User', new_account.address, new_account.key.hex(), ip_address)
    )
    conn.commit()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['wallet_address'] = user['wallet_address']
    session['private_key'] = user['private_key']
    conn.close()
    return jsonify({"redirect": url_for('user_dashboard')})

# ─── Password Reset Engine ────────────────────────────────────────────────────
OTP_STORE = {}

@app.route('/api/forgot_password', methods=['POST'])
def forgot_password():
    email = request.json.get('email', '').strip()
    if not email: return jsonify({"error": "Email is required"}), 400
    
    conn = get_db_connection()
    user = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    
    if not user:
        return jsonify({"error": "Email not found"}), 404
        
    import random
    otp = str(random.randint(100000, 999999))
    OTP_STORE[email] = otp
    
    # In a real app we would send an email here. For hackathon, we return it so the frontend can display it.
    print(f"\n[MOCK EMAIL SERVER] To: {email} | OTP: {otp}\n")
    return jsonify({"success": True, "message": "OTP sent to email", "demo_otp": otp})

@app.route('/api/reset_password', methods=['POST'])
def reset_password():
    data = request.json
    email = data.get('email', '').strip()
    otp = data.get('otp', '').strip()
    new_password = data.get('new_password', '').strip()
    
    if not email or not otp or not new_password:
        return jsonify({"error": "All fields required"}), 400
        
    if OTP_STORE.get(email) != otp:
        return jsonify({"error": "Invalid or expired OTP"}), 401
        
    conn = get_db_connection()
    conn.execute('UPDATE users SET password = ? WHERE email = ?', (new_password, email))
    conn.commit()
    conn.close()
    
    del OTP_STORE[email]
    return jsonify({"success": True})

@app.route('/api/bind-wallet', methods=['POST'])
def bind_wallet():
    if 'user_id' not in session or session.get('role') == 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    wallet_address = request.json.get('wallet_address', '').lower()
    if not wallet_address:
        return jsonify({"error": "Wallet address required"}), 400
    conn = get_db_connection()
    conn.execute('UPDATE users SET external_wallet = ? WHERE id = ?', (wallet_address, session['user_id']))
    conn.commit()
    conn.close()
    session['external_wallet'] = wallet_address
    return jsonify({"success": True})

@app.route('/api/unbind-wallet', methods=['POST'])
def unbind_wallet():
    if 'user_id' not in session or session.get('role') == 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db_connection()
    conn.execute('UPDATE users SET external_wallet = NULL WHERE id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    session.pop('external_wallet', None)
    return jsonify({"success": True})

@app.route('/api/regenerate-wallet', methods=['POST'])
def regenerate_wallet():
    if 'user_id' not in session or session.get('role') == 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    from eth_account import Account
    import secrets, hashlib, base58
    new_account = Account.create(secrets.token_hex(32))
    
    # Generate realistic-looking mock addresses for BTC and SOL
    btc_mock = "bc1q" + secrets.token_hex(20)
    sol_mock = base58.b58encode(secrets.token_bytes(32)).decode('utf-8')
    
    conn = get_db_connection()
    conn.execute('UPDATE users SET wallet_address = ?, private_key = ?, btc_wallet = ?, sol_wallet = ? WHERE id = ?', 
                 (new_account.address, new_account.key.hex(), btc_mock, sol_mock, session['user_id']))
    conn.commit()
    conn.close()
    session['wallet_address'] = new_account.address
    session['private_key'] = new_account.key.hex()
    return jsonify({"success": True})

@app.route('/api/send-mock-tx', methods=['POST'])
def send_mock_tx():
    if 'user_id' not in session: return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    asset = data.get('asset', 'ETH')
    receiver = data.get('receiver')
    amount = data.get('amount')
    sender = data.get('sender')
    
    import uuid
    tx_hash = f"mock_{asset.lower()}_" + uuid.uuid4().hex
    
    conn = get_db_connection()
    conn.execute('''INSERT INTO transactions 
                    (user_id, tx_hash, amount_eth, sender_address, receiver_address, status, currency)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (session['user_id'], tx_hash, float(amount), sender, receiver, 'confirmed', asset))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "tx_hash": tx_hash})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─── User Routes ─────────────────────────────────────────────────────────────
@app.route('/dashboard')
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    if session.get('role') == 'Admin':
        return redirect(url_for('admin_dashboard'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    
    # Trigger a sync for both wallets to fetch latest transactions on page load
    if user['wallet_address']:
        sync_etherscan_history(user['wallet_address'], user['id'])
    if user['external_wallet']:
        sync_etherscan_history(user['external_wallet'], user['id'])
        
    txns = conn.execute('SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('dashboard.html', 
                           wallet_address=user['wallet_address'], 
                           private_key=user['private_key'],
                           external_wallet=user['external_wallet'],
                           btc_wallet=user['btc_wallet'],
                           sol_wallet=user['sol_wallet'],
                           transactions=txns)

@app.route('/settings')
def settings_page():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    if session.get('role') == 'Admin':
        return redirect(url_for('admin_dashboard'))
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    return render_template('settings.html', 
                           wallet_address=user['wallet_address'], 
                           private_key=user['private_key'],
                           external_wallet=user['external_wallet'])

@app.route('/api/sync-tx', methods=['POST'])
def sync_tx():
    if 'user_id' not in session or session.get('role') == 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    tx_hash = data.get('tx_hash')
    amount_eth = float(data.get('amount_eth', 0))
    receiver = data.get('receiver_address', '')
    sender = data.get('sender_address', '')
    block_number = data.get('block_number')
    gas_used = data.get('gas_used')

    if not tx_hash or not amount_eth or not receiver:
        return jsonify({"error": "Missing transaction data"}), 400

    risk_level, risk_reason = calculate_risk(amount_eth, receiver, session['user_id'])

    conn = get_db_connection()
    try:
        conn.execute('''INSERT INTO transactions 
            (user_id, tx_hash, amount_eth, sender_address, receiver_address, block_number, gas_used, status, risk_level, risk_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (session['user_id'], tx_hash, amount_eth, sender, receiver, block_number, gas_used, 'confirmed', risk_level, risk_reason))
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500
    conn.close()
    return jsonify({"success": True, "risk_level": risk_level, "risk_reason": risk_reason})

# ─── Admin Routes ─────────────────────────────────────────────────────────────
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    
    # Sync all users to ensure stats are accurate
    conn = get_db_connection()
    all_users = conn.execute('SELECT id, wallet_address, external_wallet FROM users').fetchall()
    for u in all_users:
        if u['wallet_address']:
            sync_etherscan_history(u['wallet_address'], u['id'])
        if u['external_wallet']:
            sync_etherscan_history(u['external_wallet'], u['id'])
            
    stats = {
        'total_txns': conn.execute('SELECT COUNT(*) FROM transactions').fetchone()[0],
        'total_eth': conn.execute('SELECT COALESCE(SUM(amount_eth), 0) FROM transactions').fetchone()[0],
        'flagged': conn.execute("SELECT COUNT(*) FROM transactions WHERE risk_level != 'low'").fetchone()[0],
        'high_risk': conn.execute("SELECT COUNT(*) FROM transactions WHERE risk_level = 'high'").fetchone()[0],
        'total_users': conn.execute("SELECT COUNT(*) FROM users WHERE role = 'User'").fetchone()[0],
    }
    conn.close()
    return render_template('admin.html', stats=stats)

@app.route('/admin/transactions')
def admin_transactions():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    
    # Sync all users (for demo purposes)
    conn = get_db_connection()
    all_users = conn.execute('SELECT id, wallet_address, external_wallet FROM users').fetchall()
    for u in all_users:
        if u['wallet_address']:
            sync_etherscan_history(u['wallet_address'], u['id'])
        if u['external_wallet']:
            sync_etherscan_history(u['external_wallet'], u['id'])
    
    risk_filter = request.args.get('risk', '')
    search = request.args.get('search', '')
    
    query = '''SELECT t.*, u.real_name, u.ip_address, u.username
               FROM transactions t JOIN users u ON t.user_id = u.id WHERE 1=1'''
    params = []

    if risk_filter:
        query += ' AND t.risk_level = ?'
        params.append(risk_filter)
    if search:
        query += ' AND (t.tx_hash LIKE ? OR t.sender_address LIKE ? OR t.receiver_address LIKE ?)'
        params += [f'%{search}%', f'%{search}%', f'%{search}%']

    query += ' ORDER BY t.id DESC'
    txns = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('admin_transactions.html', transactions=txns, risk_filter=risk_filter, search=search)

@app.route('/admin/suspicious')
def admin_suspicious():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    txns = conn.execute('''SELECT t.*, u.real_name, u.ip_address, u.username
               FROM transactions t JOIN users u ON t.user_id = u.id
               WHERE t.risk_level != 'low' ORDER BY t.risk_level DESC, t.id DESC''').fetchall()
    conn.close()
    return render_template('admin_suspicious.html', transactions=txns)

@app.route('/admin/analytics')
def admin_analytics():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    return render_template('admin_analytics.html')

@app.route('/api/admin/analytics-data')
def analytics_data():
    if session.get('role') != 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db_connection()
    
    by_day = conn.execute('''SELECT DATE(timestamp) as day, COUNT(*) as count, SUM(amount_eth) as volume
                             FROM transactions GROUP BY DATE(timestamp) ORDER BY day DESC LIMIT 30''').fetchall()
    
    risk_dist = conn.execute('''SELECT risk_level, COUNT(*) as count FROM transactions GROUP BY risk_level''').fetchall()
    
    top_receivers = conn.execute('''SELECT receiver_address, COUNT(*) as count, SUM(amount_eth) as total
                                    FROM transactions GROUP BY receiver_address ORDER BY count DESC LIMIT 5''').fetchall()
    
    conn.close()
    return jsonify({
        'by_day': [dict(r) for r in by_day],
        'risk_dist': [dict(r) for r in risk_dist],
        'top_receivers': [dict(r) for r in top_receivers]
    })

@app.route('/admin/export-csv')
def export_csv():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    txns = conn.execute('''SELECT t.id, t.tx_hash, t.amount_eth, t.sender_address, t.receiver_address,
                           t.block_number, t.gas_used, t.status, t.risk_level, t.risk_reason, t.timestamp,
                           u.real_name, u.ip_address
                           FROM transactions t JOIN users u ON t.user_id = u.id ORDER BY t.id DESC''').fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','TxHash','Amount(ETH)','Sender','Receiver','Block','Gas','Status','Risk','Reason','Timestamp','RealName','IP'])
    for t in txns:
        writer.writerow([t['id'], t['tx_hash'], t['amount_eth'], t['sender_address'], t['receiver_address'],
                         t['block_number'], t['gas_used'], t['status'], t['risk_level'], t['risk_reason'],
                         t['timestamp'], t['real_name'], t['ip_address']])
    
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment; filename=transactions.csv"})

@app.route('/admin/users')
def admin_users():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    users = conn.execute('''SELECT u.id, u.real_name, u.username, u.role, u.ip_address,
                            u.wallet_address, u.external_wallet,
                            COUNT(t.id) as txn_count,
                            COALESCE(SUM(t.amount_eth), 0) as total_eth
                            FROM users u LEFT JOIN transactions t ON u.id = t.user_id
                            GROUP BY u.id ORDER BY u.id''').fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
