# FaceID · Flask Web Application
Face recognition system — DeepFace + ArcFace — Flask + SocketIO

---

## Project Structure

```
faceid_flask/
├── app/
│   ├── __init__.py          # App factory + SocketIO init
│   ├── models.py            # SQLAlchemy User model (app.db)
│   ├── face_engine.py       # DeepFace ArcFace wrapper + terrorist.db helpers
│   ├── auth/routes.py       # Login, logout, user management
│   ├── admin/routes.py      # Manage persons DB, reload embeddings
│   ├── recognize/routes.py  # Upload image + SocketIO webcam
│   └── api/routes.py        # JSON REST endpoints
├── templates/               # Jinja2 HTML (dark cyber UI)
├── static/css/main.css      # Full dark theme (matches gui_app.py palette)
├── static/js/
│   ├── profile.js           # Profile card renderer (shared)
│   ├── upload.js            # Drag/drop + AJAX upload
│   └── webcam.js            # Browser webcam → SocketIO → annotated frame
├── config.py                # Dev + prod config
├── run.py                   # Dev server entry point
├── gunicorn.conf.py         # Production server config
├── nginx.conf               # Nginx reverse proxy config
├── requirements.txt
│
│   [Your existing files — place in project root]
├── face_db.pkl              # ArcFace embeddings (from create_db.py)
├── terrorist.db             # SQLite persons + activities
└── data/
    └── app.db               # Flask user accounts (auto-created)
```

---

## Quick Start (Development)

```bash
# 1. Clone / copy project
cd faceid_flask

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Place your data files in the project root
#    face_db.pkl  →  faceid_flask/face_db.pkl
#    terrorist.db →  faceid_flask/terrorist.db

# 5. Run development server
python run.py

# 6. Open browser → http://localhost:5000
#    Default login: admin / admin123  ← CHANGE THIS IMMEDIATELY
```

---

## Production Deployment (On-Premise)

### 1. Install system dependencies
```bash
sudo apt update
sudo apt install python3-venv nginx -y
```

### 2. Set up the app
```bash
cd /opt
sudo git clone <your-repo> faceid_flask   # or scp your files
cd faceid_flask
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set environment variables
```bash
export SECRET_KEY="your-very-long-random-secret-key-here"
```
Or add to `/etc/environment` for persistence.

### 4. Create log directory
```bash
sudo mkdir -p /var/log/faceid
sudo chown $USER:$USER /var/log/faceid
```

### 5. Start with Gunicorn
```bash
gunicorn -c gunicorn.conf.py "app:create_app('config.ProductionConfig')"
```

### 6. Run as a systemd service (auto-start on reboot)
Create `/etc/systemd/system/faceid.service`:
```ini
[Unit]
Description=FaceID Flask App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/faceid_flask
Environment="SECRET_KEY=your-secret-key-here"
ExecStart=/opt/faceid_flask/venv/bin/gunicorn -c gunicorn.conf.py "app:create_app('config.ProductionConfig')"
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable faceid
sudo systemctl start faceid
```

### 7. Configure Nginx
```bash
sudo cp nginx.conf /etc/nginx/sites-available/faceid
# Edit nginx.conf — replace /path/to/faceid_flask with /opt/faceid_flask
# Edit nginx.conf — replace yourdomain.com with your actual domain
sudo ln -s /etc/nginx/sites-available/faceid /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 8. Add SSL (optional but recommended)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
# Then uncomment the HTTPS block in nginx.conf
```

---

## Roles

| Role   | Upload Image | Webcam | View Profiles | Admin Panel | Manage Users |
|--------|:-----------:|:------:|:-------------:|:-----------:|:------------:|
| viewer | ✅          | ✅     | ✅            | ❌          | ❌           |
| admin  | ✅          | ✅     | ✅            | ✅          | ✅           |

---

## API Endpoints

| Method | Endpoint                  | Auth   | Description                    |
|--------|---------------------------|--------|--------------------------------|
| GET    | /api/health               | No     | Health check                   |
| GET    | /api/persons              | Yes    | List all persons                |
| GET    | /api/persons/<name>       | Yes    | Get person profile by name     |
| GET    | /api/db/status            | Yes    | Embedding count + person count |
| POST   | /recognize/process        | Yes    | Upload image → JSON detections |
| WS     | /socket.io/               | Yes    | Webcam frame streaming         |

---

## Reloading Face Embeddings

After running `create_db.py` to update `face_db.pkl`:
1. Go to **Admin → Dashboard**
2. Click **⟳ Reload Embeddings**

This reloads the pkl into memory without restarting the server.

---

## Troubleshooting

**DeepFace slow on first request** — Normal. ArcFace model downloads ~500MB on first run and is then cached.

**Webcam not working in browser** — Browser requires HTTPS for `getUserMedia`. Either use localhost, or add SSL cert.

**face_db.pkl not found** — Run `create_db.py` first from your original pipeline, then copy `face_db.pkl` to the project root.

**SocketIO disconnects** — Ensure `eventlet` is installed. Check Nginx has the `Upgrade` headers for `/socket.io/`.
