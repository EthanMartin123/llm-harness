# Automated LLM Security Harness - Lab

A deliberately vulnerable RAG help-desk chatbot used as a target for automated
OWASP LLM Top 10 security testing.

## Architecture

The model runs on the **Windows host** (GPU); everything else runs in the **Ubuntu VM**.

```
WINDOWS HOST (GPU)                      UBUNTU VM (sandbox)
┌────────────────────┐                  ┌───────────────────────────────┐
│ Ollama + models    │ ◀── 10.0.2.2 ─── │ FastAPI app (lab/)            │
│  qwen2.5:3b        │      :11434      │ RAG + ChromaDB + mock tools  │
│  nomic-embed-text  │                  │ synthetic data + canaries    │
└────────────────────┘                  └───────────────────────────────┘
```

- **Host:** serves the chat + embedding models over the network.
- **VM:** runs the vulnerable app, holds all documents and fake data, and is what gets attacked.
- They talk over HTTP. The app reaches the host at `http://10.0.2.2:11434` (the VirtualBox NAT gateway).

> **Host address is environment-specific.** `10.0.2.2` is VirtualBox's fixed address for
> "the host, as seen from a NAT guest." If your setup differs, set `OLLAMA_HOST` in `.env`
> to the right value instead:
> - **VirtualBox NAT** (this setup): `http://10.0.2.2:11434`
> - **Bridged / host-only / VMware:** the host's actual LAN IP (find it on the host with
>   `ipconfig` on Windows or `ip a` on Linux/Mac), e.g. `http://192.168.1.50:11434`
> - **Model running in the same VM or same machine as the app:** `http://127.0.0.1:11434`
>
> Verify with `curl -s http://<host-address>:11434/api/tags` from inside the VM before starting.

---

## Daily startup (everything already installed)

### 1. On the Windows host — make sure Ollama is running and reachable

Ollama normally starts on login (tray icon). Confirm it's listening on the network:

```powershell
netstat -ano | findstr LISTENING | findstr 11434
```

You want `0.0.0.0:11434` (not `127.0.0.1`). If it shows `127.0.0.1`, quit Ollama from
the tray and relaunch it (the `OLLAMA_HOST=0.0.0.0` user variable must be set).

### 2. Start the VM and SSH in

```bash
ssh -p 2222 <vm-user>@localhost
cd ~/llm-harness
source .venv/bin/activate          # prompt shows (.venv)
```

### 3. Confirm the VM can see the host's models

```bash
curl -s http://10.0.2.2:11434/api/tags
```

Should list both `qwen2.5:3b` and `nomic-embed-text`.

### 4. Start the lab

```bash
mkdir -p results
uvicorn lab.main:app --host 127.0.0.1 --port 8000 --reload
```

Leave this running. Open a **second** SSH session for the commands below.

### 5. Build the document store and smoke-test

```bash
cd ~/llm-harness && source .venv/bin/activate
TOKEN=change-me-local-only

curl -s -XPOST localhost:8000/admin/reset -H "x-admin-token: $TOKEN"   # -> {"chunks": N}
curl -s localhost:8000/health | jq                                     # model = qwen2.5:3b
curl -s -XPOST localhost:8000/chat -H 'content-type: application/json' -d '{"message":"What are the hours for the Sierra Hall computer lab?"}' | jq '.answer'
```

If you get a grounded answer, the full chain works: VM app -> host GPU -> back to the VM.

**To stop:** `Ctrl-C` in the uvicorn window. The VM and host Ollama can stay up.

---

## First-time setup (fresh machine)

### On the Windows host

1. Install Ollama from <https://ollama.com/download>.
2. Set a **User** environment variable `OLLAMA_HOST=0.0.0.0`, then quit + relaunch Ollama.
3. Allow the port for the VM subnet (admin PowerShell):
   ```powershell
   New-NetFirewallRule -DisplayName "Ollama for VM" -Direction Inbound -Protocol TCP -LocalPort 11434 -RemoteAddress 10.0.2.0/24 -Action Allow
   ```
4. Pull the models:
   ```powershell
   ollama pull qwen2.5:3b
   ollama pull nomic-embed-text
   ```

### In the Ubuntu VM

1. Install prerequisites:
   ```bash
   sudo apt update && sudo apt install -y git python3.12 python3.12-venv sqlite3 jq
   ```
2. Clone and set up the virtualenv:
   ```bash
   git clone <your-repo-url> llm-harness && cd llm-harness
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Create `.env` from the example and confirm it points at the host:
   ```bash
   cp .env.example .env
   # .env should contain:
   #   LAB_MODEL=qwen2.5:3b
   #   EMBED_MODEL=nomic-embed-text
   #   OLLAMA_HOST=http://10.0.2.2:11434
   #   HARDENED=0
   #   LAB_DEBUG=1
   #   ADMIN_TOKEN=change-me-local-only
   ```
4. Generate the synthetic data (from the repo root):
   ```bash
   mkdir -p data/corpus data/files data/secrets data/uploads results
   python3 scripts/gen_corpus.py && python3 scripts/gen_users.py
   echo "Q4 budget draft: CANARY-FILE-5d21. Do not share." > data/secrets/budget.txt
   echo "Welcome to the help desk shared drive." > data/files/readme.txt
   ```
5. Start the lab (Daily startup step 4) and reset to build the store (Daily startup step 5).

