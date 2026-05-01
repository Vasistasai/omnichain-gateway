import sqlite3
import os
from eth_account import Account

DB_NAME = 'real_crypto.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            real_name TEXT NOT NULL,
            wallet_address TEXT,
            private_key TEXT,
            external_wallet TEXT,
            ip_address TEXT,
            role TEXT NOT NULL DEFAULT 'User'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tx_hash TEXT UNIQUE NOT NULL,
            amount_eth REAL NOT NULL,
            sender_address TEXT,
            receiver_address TEXT NOT NULL,
            block_number INTEGER,
            gas_used INTEGER,
            gas_price TEXT,
            status TEXT DEFAULT 'pending',
            risk_level TEXT DEFAULT 'low',
            risk_reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        # Generate built-in wallets for the demo users
        admin_acct = Account.create()
        public_acct = Account.create()

        c.execute('INSERT INTO users (username, password, real_name, wallet_address, private_key, ip_address, role) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 ('admin', 'admin123', 'Super Admin', admin_acct.address, admin_acct.key.hex(), '127.0.0.1', 'Admin'))
        c.execute('INSERT INTO users (username, password, real_name, wallet_address, private_key, ip_address, role) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 ('public', 'public123', 'John Doe', public_acct.address, public_acct.key.hex(), '127.0.0.1', 'User'))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    init_db()
    print("Database initialized successfully with built-in wallets.")
