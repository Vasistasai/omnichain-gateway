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
            btc_wallet TEXT,
            sol_wallet TEXT,
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
            currency TEXT DEFAULT 'ETH',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        # Generate built-in wallets for the demo users
        admin_acc = Account.create()
        public_acc = Account.create()
        
        c.execute("INSERT INTO users (real_name, username, password, role, wallet_address, private_key, btc_wallet, sol_wallet, ip_address) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  ("Admin", "admin", "admin123", "Admin", "", "", "", "", "127.0.0.1"))
                  
        c.execute("INSERT INTO users (real_name, username, password, role, wallet_address, private_key, btc_wallet, sol_wallet, ip_address) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  ("Public User", "public", "public123", "User", public_acc.address, public_acc.key.hex(), "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh", "7hVnL5K2L9o3b2HnX2V5t4qPqj4e3yL1xV9uR4pW2qX", "192.168.1.5"))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    init_db()
    print("Database initialized successfully with built-in wallets.")
