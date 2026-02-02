# HoneyGrid – GUI-Driven Distributed Honeytoken Deployment & Monitor

A secure, distributed honeytoken monitoring system with mutual TLS authentication, encrypted database storage, and a real-time tkinter GUI dashboard for Windows environments.

## 🎯 Project Overview

HoneyGrid enables security teams to deploy and monitor honeytokens (decoy files) across distributed agents. When an attacker accesses a honeytoken, the system triggers immediate alerts through a centralized dashboard with network visualization.

### Key Features

- **Distributed Agent Monitoring**: Watchdog-based file system monitoring on each endpoint
- **Mutual TLS Security**: Certificate-based authentication between agents and server
- **Encrypted Storage**: Application-level encryption (Fernet) for sensitive database fields
- **Real-time GUI Dashboard**: tkinter-based network map, alerts, and statistics tabs
- **Rate Limiting & Replay Protection**: DoS mitigation and nonce-based replay prevention
- **Token Deployment**: Remote honeytoken deployment via GUI dialog
- **Notifications**: Email and Discord webhook alerts with severity filtering
- **Agent Health Monitoring**: Offline/warning detection with status indicators
- **Alert Search/Filter**: Filter alerts by agent, token, type, or path

## 📋 Requirements

- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.10 or higher
- **Dependencies**: See `requirements.txt`

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/pranaynidhi/ST5062CEM_CW2.git
cd ST5062CEM_CW2
```

### 2. Set Up Virtual Environment

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```cmd
pip install -r requirements.txt
```

### 4. Generate SSL Certificates

```cmd
python scripts\generate_certs.py
```

This creates a Certificate Authority (CA) and generates signed certificates for the server and clients in the `certs\` directory.

### 5. Initialize Database

```cmd
python server\db.py --init
```

### 6. Start the Server

```cmd
python server\server.py --host 0.0.0.0 --port 9000
```

### 7. Launch GUI Dashboard

In a new terminal:

```cmd
python gui_tk\app.py
```

### 8. Deploy Agents

On each monitored endpoint:

```cmd
python agent\agent.py --server-host <SERVER_IP> --server-port 9000 --agent-id agent-001
```

## 📁 Project Structure

```text
HoneyGrid\
├── agent\                  # Agent components
│   ├── agent.py           # Main agent coordinator
│   ├── monitor.py         # File system monitoring (watchdog)
│   ├── sender.py          # Secure TLS event sender
│   └── config.py          # Agent configuration
├── server\                 # Server components
│   ├── server.py          # Asyncio TLS server
│   ├── db.py              # Encrypted SQLite database manager
│   └── protocol.py        # Frame parsing & validation
│   ├── config_loader.py   # YAML configuration loader
│   └── notifiers\         # Notification channels
│       ├── base.py         # Notifier base classes
│       ├── email_notifier.py
│       └── discord_notifier.py
├── gui_tk\                 # tkinter GUI
│   ├── app.py             # Main dashboard window
│   ├── map_frame.py       # Network visualization
│   ├── alert_frame.py     # Alert list & details
│   ├── stats_frame.py     # Statistics dashboard
│   └── deploy_dialog.py   # Token deployment dialog
├── certs\                  # SSL certificates (generated)
│   ├── ca.crt             # Certificate Authority
│   ├── server.crt         # Server certificate
│   ├── server.key         # Server private key
│   └── client_*.crt       # Agent certificates
├── tests\                  # Test suites
│   ├── unit\              # Unit tests
│   └── integration\       # Integration tests
├── scripts\                # Utility scripts
│   └── generate_certs.py  # SSL certificate generation
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔒 Security Architecture

### Mutual TLS Authentication

- **Server**: Requires valid agent certificate signed by CA
- **Agent**: Verifies server certificate against CA
- **Cipher Suites**: TLS 1.3 with strong ciphers only

### Replay Protection

- Per-agent nonce cache (LRU, max 1,000 entries)
- Timestamp validation (±60 second window)
- Automatic rejection of duplicate nonces

### Rate Limiting

- **Agent-side**: Token bucket (10 events/sec, burst 20)
- **Server-side**: Per-agent asyncio semaphore limiting

### Data Encryption

- **In Transit**: TLS 1.3 encryption
- **At Rest**: Application-level encryption via cryptography library

## 🧪 Testing

### Run Unit Tests

```cmd
pytest tests\unit -v
```

### Run Live Notification Tests (Optional)

These require real SMTP/Discord credentials and are skipped by default.

```cmd
set HONEYGRID_RUN_LIVE_NOTIFICATIONS=1
pytest tests\test_notifications.py -v
```

### Run Integration Tests

```cmd
pytest tests\integration -v
```

### Generate Coverage Report

```cmd
pytest --cov=agent --cov=server --cov=gui_tk --cov-report=html
```

View coverage report: `htmlcov\index.html`

## 🎮 Usage

### Deploying a Honeytoken

1. Open GUI Dashboard
2. Click **Actions → Deploy Token**
3. Enter Token ID and file path
4. Select target agents
5. Click **Deploy Now** or **Schedule...**

### Viewing Alerts

- **Network Map** (left panel): Agent nodes color-coded by status
  - 🟢 Green: Healthy, no recent events
  - 🟡 Yellow: Warning state
  - 🔴 Red: Token triggered recently
- **Alert Panel** (right panel): Chronological event list
- **Search/Filter**: Filter alerts by agent, token, type, or path
- **Statistics Tab**: Event counts by agent, token, and type
- Click event for detailed pop-up (token_id, path, timestamp)

### Exporting Data

- Click **Export Alerts to CSV** in alert panel
- Select date range and destination

## 📊 Configuration

### Agent Configuration (`agent\config.py`)

```python
SERVER_HOST = "192.168.1.100"
SERVER_PORT = 9000
AGENT_ID = "agent-001"
WATCH_PATHS = ["C:\\honeytokens"]
RATE_LIMIT = 10  # events per second
```

### Server Configuration (`server\server.py`)

```python
BIND_HOST = "0.0.0.0"
BIND_PORT = 9000
DB_PATH = "data\\events.db"
DB_PASSWORD = "your-secure-password"
MAX_NONCE_CACHE = 1000
TIMESTAMP_TOLERANCE = 60  # seconds
```

## 🛠️ Development

### Branching Strategy

- `main` – Stable releases
- `develop` – Integration branch
- `feature/*` – Feature branches
- `release/*` – Release candidates

### Code Quality

```cmd
# Format code
black .

# Lint code
pylint agent server gui_tk
```

## 📄 License

Academic Project – Coventry University

## 🙏 Acknowledgments

- **watchdog**: Python library for file system monitoring
- **cryptography**: Python cryptographic recipes and primitives
- **SQLCipher**: Encrypted SQLite database

---

**⚠️ Disclaimer**: This system is designed for educational and authorized security testing purposes only. Unauthorized deployment or use may violate laws and policies.
