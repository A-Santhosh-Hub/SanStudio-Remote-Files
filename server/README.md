# SanStudio File Server

A fast, beautiful file server — stream 6.8 GB videos, browse images, play audio, and download anything. Expose your PC to the internet for free with **Cloudflare Tunnel**.

---

## 📁 Folder Structure

```
server/
├── server.py          ← Backend (Flask + Waitress)
├── requirements.txt
├── password.txt       ← ← ← YOUR PASSWORD (create this, first line only)
├── start.bat          ← Windows launcher
├── start.sh           ← Linux/Mac launcher
├── templates/
│   ├── index.html     ← Frontend UI
│   └── login.html     ← Password page
└── uploads/           ← ← ← PUT YOUR FILES HERE
```

---

## ⚡ Quick Start

### 1. Install Python (3.10+)
Download from https://python.org

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your files
Put all your videos, audio, images, etc. inside the **`uploads/`** folder.
You can create subfolders too — they'll appear as clickable folders in the UI.

### 4. Set a password
Create **`password.txt`** next to `server.py` and put your password on the first line.
(Or set the `FILESERVER_PASSWORD` environment variable.) The server will not start without one.

### 5. Start the server
**Windows:**
```
Double-click start.bat
```

**Mac/Linux:**
```bash
bash start.sh
```

Local URL: **http://localhost:5000**

---

## 🌐 Expose to Internet Free with Cloudflare Tunnel

### Step 1 — Install cloudflared

**Windows:**
```
winget install --id Cloudflare.cloudflared
```
Or download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

**Mac:**
```
brew install cloudflared
```

**Linux (Debian/Ubuntu):**
```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
```

### Step 2 — Run the tunnel (No account needed!)
With your server already running on port 5000, open a **new terminal** and run:

```bash
cloudflared tunnel --url http://localhost:5000
```

You'll see output like:
```
Your quick Tunnel has been created! Visit it at:
https://random-name-abc123.trycloudflare.com
```

✅ Open that link from anywhere — you'll be asked for the password from `password.txt`.

> **Note:** The free quick tunnel URL changes every time you restart cloudflared.  
> For a permanent URL, create a free Cloudflare account and set up a named tunnel.

---

## 🎬 Features

| Feature | Details |
|---|---|
| **Video Streaming** | HTTP Range requests — streams 6.8 GB videos without buffering issues |
| **Audio Player** | In-browser playback for MP3, FLAC, AAC, WAV, OGG, M4A |
| **Image Viewer** | JPG, PNG, GIF, WEBP, AVIF, SVG |
| **Fast Download** | Direct chunked transfer — full speed downloads |
| **File Browser** | Grid & list view, search, sort, type filters |
| **Folder Support** | Navigate into subfolders |
| **All File Types** | ZIP, PDF, DOCX, code files — all downloadable |
| **Secure** | Password login, path traversal protection, localhost-only |

---

## 🔧 Configuration

Edit the top of `server.py` to change settings:

```python
UPLOAD_FOLDER = BASE_DIR / "uploads"   # Change to any folder path
HOST = "127.0.0.1"                     # localhost only (safe for Cloudflare Tunnel)
PORT = 5000                            # Change port here
CHUNK_SIZE = 1024 * 1024               # 1MB chunks
```

---

## 🛡️ Security Notes

- **Password login** on every page and file — 5 wrong tries locks that visitor out for 5 minutes
- The server **only serves files inside `uploads/`** — path traversal is blocked
- Hidden files (starting with `.`) are never listed or served
- Listens on **localhost only** — other PCs on the same network can't open it directly; use the tunnel
- Never commit `password.txt` or `.secret_key` (already in `.gitignore`)

---

*Developed by [SanStudio](https://a-santhosh-hub.github.io/in/)*
