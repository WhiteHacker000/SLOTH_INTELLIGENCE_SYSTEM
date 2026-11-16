# Deployment

One Ubuntu 24.04 server runs everything: PostgreSQL with pgvector, Ollama with Gemma, the FastAPI backend (which also serves the built frontend), and Caddy for HTTPS. No Docker.

## Server size

At least **8 GB RAM**. Gemma 3 4B uses about 3.5 GB and the embedding model about 1 GB. Without a GPU, answers take about 30–60 seconds.

## 1. System packages

```bash
apt update && apt install -y git python3-venv postgresql postgresql-16-pgvector caddy
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:4b
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```

## 2. Database

```bash
DB_PASSWORD=$(openssl rand -hex 16)
sudo -u postgres psql -c "CREATE ROLE decision_intelligence LOGIN PASSWORD '$DB_PASSWORD';"
sudo -u postgres createdb -O decision_intelligence decision_intelligence
sudo -u postgres psql -d decision_intelligence -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## 3. App

```bash
useradd --system --create-home --shell /usr/sbin/nologin app
git clone https://github.com/WhiteHacker000/SLOTH_INTELLIGENCE_SYSTEM.git /opt/decision-intelligence
cd /opt/decision-intelligence
cp .env.example .env   # set DATABASE_URL with $DB_PASSWORD; GITHUB_TOKEN is optional

cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# CPU-only PyTorch is about 200 MB instead of 2 GB.
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements-embeddings.txt
.venv/bin/alembic upgrade head
chown -R app:app /opt/decision-intelligence
```

Build the frontend (`npm ci && npm run build` in `frontend/`) on the server with Node 22, or build it locally and copy `frontend/dist` to `/opt/decision-intelligence/frontend/dist`.

## 4. Services

```bash
cp deploy/decision-intelligence.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now decision-intelligence

cp deploy/Caddyfile /etc/caddy/Caddyfile   # replace your-domain.example first
systemctl reload caddy
```

The backend listens only on `127.0.0.1:8000`; Caddy is the only public entry point.

## Copying an existing database

Importing and extracting a large repository takes hours, so copying a database that already has data is faster:

```bash
# On the machine with the data
pg_dump -Fc decision_intelligence > demo.dump
scp demo.dump root@SERVER:/tmp/

# On the server, before starting the backend
sudo -u postgres pg_restore --no-owner --role=decision_intelligence -d decision_intelligence /tmp/demo.dump
```

## Updating

```bash
cd /opt/decision-intelligence && sudo -u app git pull
sudo -u app backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
systemctl restart decision-intelligence
```

## Before sharing the URL

There is no login yet. Anyone with the URL can import repositories and start syncs or extractions, which use the server's CPU. Share the URL only with the people who need it.
