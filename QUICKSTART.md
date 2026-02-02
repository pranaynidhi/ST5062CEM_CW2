# HoneyGrid Quick Start Guide

## 🚀 Getting Started

### Prerequisites

- Python 3.10+ installed
- Windows 10/11 (64-bit)
- Virtual environment activated

### Installation

```cmd
# Navigate to project directory
cd "D:\College\ST5062CEM Programming and Algorithms 2\ST5062CEM_CW2"

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies (already done)
pip install -r requirements.txt

# Generate SSL certificates (already done)
python scripts\generate_certs.py
```

## 📋 Running the System

### Step 1: Start the Server

Open Terminal 1:

```cmd
python server\server.py
```

Expected output:

```text
============================================================
HoneyGrid Server Starting
============================================================
✓ TLS context created (mutual authentication required)
✓ Server listening on 0.0.0.0:9000
✓ Database: data\honeygrid.db
✓ Nonce cache size: 1000
============================================================
```

### Step 2: Launch the GUI Dashboard

Open Terminal 2:

```cmd
python gui_tk\app.py
```

The dashboard window will open showing:

- **Left Panel**: Network map with agent nodes
- **Right Panel**: Alerts and statistics tabs

### Step 3: Deploy an Agent

**Create a test honeytoken directory:**

```cmd
mkdir C:\honeytokens
echo "This is a decoy file" > C:\honeytokens\secret.txt
```

**Start an agent** (Terminal 3):

```cmd
python agent\agent.py ^
    --agent-id agent-001 ^
    --server-host localhost ^
    --watch-path C:\honeytokens ^
    --token-id token-001 ^
    --client-cert certs\client_client-001.crt ^
    --client-key certs\client_client-001.key
```

Expected output:

```text
============================================================
HoneyGrid Agent Starting: agent-001
============================================================
Initializing file system monitor...
✓ Monitoring 1 path(s)
Initializing secure sender...
✓ Connected to server: localhost:9000
============================================================
✓ Agent running (Ctrl+C to stop)
============================================================
```

### Step 4: Trigger a Honeytoken

**Access the monitored file:**

```cmd
notepad C:\honeytokens\secret.txt
```

**What happens:**

1. Agent detects file access
2. Event sent to server via TLS
3. Server stores event in encrypted database
4. GUI dashboard shows alert:
   - Agent node turns **RED** on map
   - Alert appears in right panel
5. Server logs: `🚨 [agent-001] HONEYTOKEN TRIGGERED!`

## 🎮 Testing the System

### Manual Test Sequence

1. **Verify server is running** - Check Terminal 1 for listening message
2. **Open GUI** - Should show "No agents connected" initially
3. **Start agent** - GUI should update to show agent node (green)
4. **Trigger honeytoken** - Modify/open monitored file
5. **Check GUI** - Agent turns red, alert appears
6. **Check server logs** - Shows event details
7. **Export alerts** - Click "Export CSV" in GUI

### Component Tests

```cmd
# Test protocol module
python server\protocol.py

# Test database module
python server\db.py

# Test map frame
python gui_tk\map_frame.py

# Test alert frame
python gui_tk\alert_frame.py
```

## 📊 GUI Features

### Network Map (Left Panel)

- **Green node**: Healthy agent
- **Yellow node**: Warning state
- **Red node**: Honeytoken triggered
- **Gray node**: Offline agent
- **Click node**: Show agent details

### Alert Panel (Right Panel)

- **Event list**: Chronological order (newest first)
- **Search/Filter**: Filter by agent, token, type, or path
- **Double-click event**: Show detailed information
- **Export CSV**: Save events to file
- **Clear**: Clear alert list
- **Refresh**: Update from database

### Statistics Tab (Right Panel)

- **Overview**: Total agents, events, tokens, last 24h
- **Breakdowns**: Event counts by agent, type, and token

### Menu Bar

- **File** → Refresh Data, Exit
- **View** → Refresh Agents, Clear Alerts
- **Actions** → Deploy Token, Database Statistics
- **Help** → About

## 🔧 Configuration

### Agent Configuration File

Create `agent\config.json`:

```json
{
  "agent_id": "agent-001",
  "server_host": "localhost",
  "server_port": 9000,
  "watch_paths": ["C:\\honeytokens", "C:\\decoy_docs"],
  "token_mapping": {
    "C:\\honeytokens": "token-001",
    "C:\\decoy_docs": "token-002"
  }
}
```

**Use config file:**

```cmd
python agent\agent.py --config agent\config.json
```

### Server Configuration

```cmd
python server\server.py ^
    --host 0.0.0.0 ^
    --port 9000 ^
    --db data\honeygrid.db ^
    --db-password your_secure_password
```

## 🔍 Troubleshooting

### "No connection could be made"

- **Cause**: Server not running
- **Solution**: Start server first (Step 1)

### "Certificate file not found"

- **Cause**: SSL certificates not generated
- **Solution**: Run `python scripts\generate_certs.py`

### "Path does not exist"

- **Cause**: Watch path not found
- **Solution**: Create directory: `mkdir C:\honeytokens`

### GUI shows "No agents connected"

- **Cause**: No agents started or not connected
- **Solution**: Start an agent (Step 3)

### Agent can't connect to server

- **Cause**: Firewall blocking port 9000
- **Solution**: Allow Python through Windows Firewall

## 📈 Monitoring Multiple Agents

**Generate additional client certificates:**

```cmd
python scripts\generate_certs.py 3
```

This creates:

- `client_client-001.crt/key`
- `client_client-002.crt/key`
- `client_client-003.crt/key`

**Start multiple agents:**

Terminal 3:

```cmd
python agent\agent.py --agent-id agent-001 --server-host localhost --watch-path C:\honeytokens\agent1 --token-id token-001
```

Terminal 4:

```cmd
python agent\agent.py --agent-id agent-002 --server-host localhost --watch-path C:\honeytokens\agent2 --token-id token-002
```

Terminal 5:

```cmd
python agent\agent.py --agent-id agent-003 --server-host localhost --watch-path C:\honeytokens\agent3 --token-id token-003
```

**GUI will show:**

- 3 nodes in circular layout
- Each with independent status

## 💡 Usage Tips

1. **Deploy strategically**: Place honeytokens in attractive locations (e.g., "passwords.txt", "backup.zip")
2. **Monitor logs**: Watch server terminal for real-time alerts
3. **Regular backups**: Back up `data\honeygrid.db` regularly
4. **Unique passwords**: Change default DB password in production
5. **Network deployment**: Use actual IP addresses instead of localhost
6. **Rate limiting**: Default 10 events/sec prevents flooding

## 🎯 Next Steps

1. **Deploy to network**: Use server IP instead of localhost
2. **Create more honeytokens**: Add realistic decoy files
3. **Test scenarios**: Simulate attacker behavior
4. **Review events**: Analyze patterns in alert panel
5. **Export data**: Generate CSV reports
6. **Write tests**: Add unit and integration tests
7. **Document findings**: Prepare coursework report

## 📝 Important Files

- `data\honeygrid.db` - Encrypted event database
- `certs\*.crt` - SSL certificates (don't commit .key files!)
- `agent\config.json` - Agent configuration
- Server runs on: `0.0.0.0:9000`
- GUI auto-refreshes: Every 5 seconds

## 🔒 Security Notes

- ✅ Mutual TLS authentication (client & server certs)
- ✅ Encrypted database (Fernet AES-256)
- ✅ Replay protection (nonce-based)
- ✅ Rate limiting (token bucket)
- ✅ Timestamp validation (±60 sec tolerance)
- ⚠️ Change default database password!
- ⚠️ Never commit private keys to git!

---

**Ready to test?** Follow the 4 steps above to see HoneyGrid in action! 🚀
