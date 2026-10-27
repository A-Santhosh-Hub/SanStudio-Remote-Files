import os
import re
import sys
import hmac
import time
import secrets
import mimetypes
from datetime import timedelta
from pathlib import Path
from flask import (
    Flask, render_template, request, Response,
    abort, jsonify, send_file, session, redirect, url_for
)

BASE_DIR = Path(__file__).resolve().parent

# ─── Config ──────────────────────────────────────────────────────────────────
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)
UPLOAD_ROOT = UPLOAD_FOLDER.resolve()

HOST = "127.0.0.1"   # localhost only — Cloudflare Tunnel connects here, the office LAN can't
PORT = 5000

CHUNK_SIZE = 1024 * 1024  # 1 MB chunks for streaming

MAX_LOGIN_FAILS = 5
LOCKOUT_SECONDS = 5 * 60

ICONS = {
    "video":  ["mp4","mkv","webm","avi","mov","flv","wmv","m4v","ts","3gp"],
    "audio":  ["mp3","flac","wav","aac","ogg","m4a","opus","wma"],
    "image":  ["jpg","jpeg","png","gif","webp","bmp","svg","ico","tiff","avif"],
    "pdf":    ["pdf"],
    "zip":    ["zip","rar","7z","tar","gz","bz2","xz"],
    "code":   ["py","js","ts","html","css","json","xml","yaml","yml","sh","bat","c","cpp","java","go","rs"],
    "text":   ["txt","md","log","csv","ini","cfg","conf"],
    "doc":    ["doc","docx","xls","xlsx","ppt","pptx","odt","ods","odp"],
}

# ─── Password & secret key ───────────────────────────────────────────────────
def load_password():
    """Password comes from FILESERVER_PASSWORD env var, else first line of password.txt."""
    pw = os.environ.get("FILESERVER_PASSWORD", "").strip()
    if not pw:
        pw_file = BASE_DIR / "password.txt"
        if pw_file.exists():
            lines = pw_file.read_text(encoding="utf-8").splitlines()
            pw = lines[0].strip() if lines else ""
    return pw

def load_secret_key():
    """Kept in a file so logins survive a server restart."""
    key_file = BASE_DIR / ".secret_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    key_file.write_text(key, encoding="utf-8")
    return key

PASSWORD = load_password()

app = Flask(__name__)
app.secret_key = load_secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

# ip -> [fail_count, locked_until]
login_fails = {}

def client_ip():
    # Server only listens on localhost, so remote visitors arrive via the tunnel,
    # which sets CF-Connecting-IP to the real visitor address.
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or "?"

# ─── Helpers ─────────────────────────────────────────────────────────────────
def get_file_type(ext):
    ext = ext.lower().lstrip(".")
    for ftype, exts in ICONS.items():
        if ext in exts:
            return ftype
    return "file"

def human_size(size):
    for unit in ["B","KB","MB","GB","TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"

def safe_path(rel_path):
    """Resolve a user-supplied path inside UPLOAD_ROOT, or abort."""
    rel = Path(rel_path)
    if any(part.startswith(".") for part in rel.parts):
        abort(404)   # hidden files/folders and ".." are never served
    target = (UPLOAD_ROOT / rel).resolve()
    if not target.is_relative_to(UPLOAD_ROOT):
        abort(403)
    return target

def safe_file(rel_path):
    target = safe_path(rel_path)
    if not target.is_file():
        abort(404)
    return target

def list_dir(rel_path=""):
    target = safe_path(rel_path)
    if not target.is_dir():
        abort(404)

    items = []
    try:
        entries = sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        abort(403)

    for entry in entries:
        if entry.name.startswith("."):
            continue
        is_dir = entry.is_dir()
        size = 0
        if not is_dir:
            try:
                size = entry.stat().st_size
            except OSError:
                pass
        ext = entry.suffix if not is_dir else ""
        ftype = "folder" if is_dir else get_file_type(ext)
        items.append({
            "name":    entry.name,
            "type":    ftype,
            "ext":     ext.lstrip(".").lower(),
            "size":    human_size(size) if not is_dir else "",
            "size_raw": size,
            "is_dir":  is_dir,
            "path":    str(Path(rel_path) / entry.name).replace("\\", "/"),
        })
    return items

# ─── Auth ────────────────────────────────────────────────────────────────────
@app.before_request
def require_login():
    if request.endpoint in ("login", "static"):
        return
    if session.get("auth"):
        return
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        ip = client_ip()
        fails, locked_until = login_fails.get(ip, [0, 0])
        now = time.time()
        if locked_until > now:
            mins = int((locked_until - now) // 60) + 1
            error = f"Too many wrong attempts. Try again in {mins} min."
        elif hmac.compare_digest(request.form.get("password", "").encode(), PASSWORD.encode()):
            login_fails.pop(ip, None)
            session.clear()
            session["auth"] = True
            session.permanent = True
            return redirect(url_for("index"))
        else:
            fails += 1
            if fails >= MAX_LOGIN_FAILS:
                login_fails[ip] = [0, now + LOCKOUT_SECONDS]
                error = "Too many wrong attempts. Try again in 5 min."
            else:
                login_fails[ip] = [fails, 0]
                error = "Wrong password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/files")
def api_files():
    rel = request.args.get("path", "").strip("/")
    items = list_dir(rel)
    return jsonify({"ok": True, "path": rel, "items": items})

@app.errorhandler(403)
@app.errorhandler(404)
def http_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": e.name}), e.code
    return e

@app.route("/stream/<path:filepath>")
def stream_file(filepath):
    """Stream file with Range request support — handles 6.8 GB videos."""
    target = safe_file(filepath)

    file_size = target.stat().st_size
    mime, _ = mimetypes.guess_type(str(target))
    mime = mime or "application/octet-stream"

    range_header = request.headers.get("Range")
    if range_header:
        # Parse bytes=start-end, bytes=start- and bytes=-suffix
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match or not (match.group(1) or match.group(2)):
            return Response(status=416, headers={"Content-Range": f"bytes */{file_size}"})
        if match.group(1):
            start = int(match.group(1))
            end   = int(match.group(2)) if match.group(2) else file_size - 1
        else:
            suffix = int(match.group(2))
            start  = max(file_size - suffix, 0)
            end    = file_size - 1
        end = min(end, file_size - 1)
        if start >= file_size or start > end:
            return Response(status=416, headers={"Content-Range": f"bytes */{file_size}"})
        length = end - start + 1

        def generate():
            with open(target, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    yield chunk
                    remaining -= len(chunk)

        headers = {
            "Content-Range":  f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges":  "bytes",
            "Content-Length": str(length),
            "Content-Type":   mime,
        }
        return Response(generate(), 206, headers=headers)
    else:
        # Full file stream
        def generate_full():
            with open(target, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk

        headers = {
            "Accept-Ranges":  "bytes",
            "Content-Length": str(file_size),
            "Content-Type":   mime,
        }
        return Response(generate_full(), 200, headers=headers)

@app.route("/download/<path:filepath>")
def download_file(filepath):
    """Force-download with Content-Disposition: attachment."""
    target = safe_file(filepath)
    return send_file(target, as_attachment=True)

if __name__ == "__main__":
    if not PASSWORD:
        print("ERROR: No password set.")
        print(f"  Create {BASE_DIR / 'password.txt'} with your password on the first line,")
        print("  or set the FILESERVER_PASSWORD environment variable.")
        sys.exit(1)

    from waitress import serve
    print("=" * 55)
    print(f"  SanStudio File Server  —  http://localhost:{PORT}")
    print("  Upload folder:", UPLOAD_ROOT)
    print("=" * 55)
    serve(app, host=HOST, port=PORT, threads=16, channel_timeout=300)
