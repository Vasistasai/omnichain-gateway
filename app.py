from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import os, csv, io, json
from database import init_db, get_db_connection

app = Flask(__name__)
app.secret_key = "omnichain_web3_secret_2024"

if not os.path.exists('real_crypto.db'):
    init_db()

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
        conn.close()
        return jsonify({"redirect": url_for('admin_dashboard') if user['role'] == 'Admin' else url_for('user_dashboard')})

    conn.close()
    return jsonify({"error": "Invalid credentials. Try admin/admin123 or public/public123"}), 401

@app.route('/api/bind-wallet', methods=['POST'])
def bind_wallet():
    if 'user_id' not in session or session.get('role') == 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    wallet_address = request.json.get('wallet_address', '').lower()
    if not wallet_address:
        return jsonify({"error": "Wallet address required"}), 400
    conn = get_db_connection()
    conn.execute('UPDATE users SET wallet_address = ? WHERE id = ?', (wallet_address, session['user_id']))
    conn.commit()
    conn.close()
    session['wallet_address'] = wallet_address
    return jsonify({"success": True})

@app.route('/api/unbind-wallet', methods=['POST'])
def unbind_wallet():
    if 'user_id' not in session or session.get('role') == 'Admin':
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db_connection()
    conn.execute('UPDATE users SET wallet_address = NULL WHERE id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    session.pop('wallet_address', None)
    return jsonify({"success": True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─── User Routes ─────────────────────────────────────────────────────────────
@app.route('/dashboard')
def user_dashboard():
    if 'user_id' not in session or session.get('role') == 'Admin':
        return redirect(url_for('index'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    txns = conn.execute('SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('dashboard.html', wallet_address=user['wallet_address'], transactions=txns)

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
    conn = get_db_connection()
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
    
    risk_filter = request.args.get('risk', '')
    search = request.args.get('search', '')
    
    conn = get_db_connection()
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

if __name__ == '__main__':
    app.run(debug=True, port=8000)
