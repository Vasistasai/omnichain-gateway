# OmniChain Gateway 🔗

> **Hackathon Project** — A Hybrid Enterprise Web3 Application that bridges real-world identity tracking with live Ethereum blockchain transactions on the Sepolia testnet.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-2.x-black?logo=flask)
![Ethereum](https://img.shields.io/badge/Ethereum-Sepolia-purple?logo=ethereum)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🚀 Live Demo

> Run locally — see **Setup** below.

---

## ✨ Features

### 🔐 Authentication
- Traditional username/password login
- Role-based access control (Admin & Public User)

### 👤 Public User
- Connect MetaMask wallet to account
- Send **real ETH** on the Sepolia Testnet
- Live gas fee estimator before sending
- Full personal transaction history with Etherscan links

### 🛡️ Admin Portal
- **Intelligence Dashboard** — Total transactions, ETH volume, flagged count, risk stats
- **Full Ledger** — See every transaction with IRL Name + IP Address + Wallet unmasked
- **Fraud Detection Engine** — Auto-flags suspicious transactions:
  - 🔴 High Risk: Amount ≥ 1 ETH, or 3+ transfers to same address
  - 🟡 Medium Risk: Amount ≥ 0.5 ETH, or 2+ transfers to same address
- **Suspicious Activity Page** — Filtered view of all flagged transactions
- **Analytics Charts** — Transactions over time, risk distribution, top receivers
- **CSV Export** — Download full transaction report

### 🎨 UI
- Cyberpunk dark glassmorphism design
- Animated 3D crypto coins (Three.js)
- Sidebar navigation
- Toast notifications
- Responsive layout

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Flask (Python) |
| Database | SQLite |
| Frontend | HTML/CSS/Vanilla JS |
| Blockchain | Ethereum (Sepolia Testnet) |
| Web3 Library | ethers.js v6 |
| 3D Graphics | Three.js |
| Charts | Chart.js |
| Wallet | MetaMask |

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- [MetaMask](https://metamask.io/) browser extension
- Sepolia testnet ETH (get free from [Google Faucet](https://cloud.google.com/application/web3/faucet/ethereum/sepolia))

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/omnichain-gateway.git
cd omnichain-gateway
```

### 2. Install Python Dependencies
```bash
pip install flask
```

### 3. Initialize the Database
```bash
python database.py
```
This creates `real_crypto.db` with two demo accounts:
- **Admin:** `admin` / `admin123`
- **Public:** `public` / `public123`

### 4. Run the Server
```bash
python app.py
```

### 5. Open in Browser
```
http://127.0.0.1:8000
```

---

## 🦊 MetaMask Setup

1. Install MetaMask from [metamask.io](https://metamask.io/)
2. Open MetaMask → Click network dropdown → Enable "Show test networks"
3. Select **Sepolia** testnet
4. Get free Sepolia ETH from the [Google Faucet](https://cloud.google.com/application/web3/faucet/ethereum/sepolia)
5. Log in as `public/public123` on the website and click **Connect MetaMask**

---

## 📁 Project Structure

```
omnichain-gateway/
├── app.py              # Flask backend + API routes + fraud detection
├── database.py         # SQLite schema + seeding
├── real_crypto.db      # SQLite database (auto-generated)
├── templates/
│   ├── layout.html         # Base layout with 3D background + sidebar
│   ├── login.html          # Login page
│   ├── dashboard.html      # Public user dashboard
│   ├── admin.html          # Admin home
│   ├── admin_transactions.html  # Full transaction ledger
│   ├── admin_suspicious.html    # Flagged transactions
│   └── admin_analytics.html     # Charts & analytics
└── static/
    └── css/
        └── styles.css      # Full design system
```

---

## 🔑 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth` | Login with username/password |
| POST | `/api/bind-wallet` | Bind MetaMask wallet to account |
| POST | `/api/unbind-wallet` | Remove wallet binding |
| POST | `/api/sync-tx` | Sync confirmed blockchain TX to DB |
| GET | `/api/admin/analytics-data` | JSON data for charts |
| GET | `/admin/export-csv` | Download CSV report |

---

## 👥 Team

Built for [Hackathon Name] — May 2026

---

## 📄 License

MIT License — Free to use and modify.
