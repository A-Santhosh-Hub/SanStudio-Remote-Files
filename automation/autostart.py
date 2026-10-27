"""SanStudio AutoStart — keeps the file server (../server) and a Cloudflare quick tunnel
running, and publishes the current tunnel link to the Apps Script backend.

    pythonw autostart.py    no window (Task Scheduler uses this)
    python  autostart.py    same, but also prints the log in the console

Everything is logged to automation.log next to this file.
"""
import ctypes
import json
import logging
import logging.handlers
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config.json"
LOG_FILE = HERE / "automation.log"
PIDS_FILE = HERE / "pids.json"

# Quick-tunnel link as printed by cloudflared (api.trycloudflare.com is its own API, not our link)
LINK_RE = re.compile(r"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
INSTANCE_PORT = 47123          # bound while running, so a second copy exits
RESTART_DELAY = 60             # seconds between restart attempts of a crashed process
PUBLIC_CHECK_GRACE = 120       # new tunnel links need a moment before they work
PUBLIC_MAX_FAILS = 3           # failed public checks in a row before restarting the tunnel

DEFAULTS = {
    "server_dir": "../server",
    "port": 5000,
    "cloudflared": "",          # blank = find it automatically
    "check_seconds": 30,
    "heartbeat_minutes": 5,
    "public_check_minutes": 5,
}

CLOUDFLARED_PATHS = [
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    r"C:\Program Files\cloudflared\cloudflared.exe",
]

log = logging.getLogger("autostart")


# ─── Setup helpers ───────────────────────────────────────────────────────────
def setup_logging():
    fmt = logging.Formatter("%(asctime)s  %(name)-11s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    if sys.stdout is not None:          # None under pythonw
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        root.addHandler(sh)


def load_config():
    if not CONFIG_FILE.exists():
        raise SystemExit("config.json not found — copy config.example.json to config.json and fill it in")
    cfg = dict(DEFAULTS)
    cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    for key in ("apps_script_url", "tool_secret"):
        if not cfg.get(key) or "PASTE" in cfg[key]:
            raise SystemExit(f"config.json: '{key}' is not filled in")
    cfg["server_dir"] = str((HERE / cfg["server_dir"]).resolve())
    return cfg


def find_cloudflared(configured):
    for candidate in [configured, shutil.which("cloudflared"), *CLOUDFLARED_PATHS]:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit("cloudflared not found — install it: winget install --id Cloudflare.cloudflared")


def single_instance():
    """Returns the bound socket (keep a reference!) or None if another copy runs."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", INSTANCE_PORT))
    except OSError:
        s.close()
        return None
    return s


def prevent_sleep():
    """Keeps Windows awake while this thread is alive. No admin, no settings changed."""
    if os.name == "nt":
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def kill_leftovers():
    """Kill server/tunnel processes left behind if the tool was killed last time."""
    try:
        old = json.loads(PIDS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if os.name != "nt":
        return
    for pid, image in old.items():
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
        ).stdout
        if f'"{image.lower()}"' in out.lower():
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, creationflags=CREATE_NO_WINDOW)
            log.info("killed leftover %s (pid %s)", image, pid)
    PIDS_FILE.unlink(missing_ok=True)


def http_ok(url, timeout=15):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as res:
            return res.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


# ─── Child process wrapper ───────────────────────────────────────────────────
class Child:
    def __init__(self, name, args, cwd, env=None, on_line=None):
        self.name, self.args, self.cwd, self.env, self.on_line = name, args, cwd, env, on_line
        self.proc = None
        self.started_at = 0.0
        self.log = logging.getLogger(name)

    def start(self):
        self.proc = subprocess.Popen(
            self.args, cwd=self.cwd, env=self.env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=CREATE_NO_WINDOW,
        )
        self.started_at = time.time()
        threading.Thread(target=self._pump, args=(self.proc,), daemon=True).start()
        self.log.info("started (pid %s)", self.proc.pid)

    def _pump(self, proc):
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self.log.info(line)
                if self.on_line:
                    self.on_line(line)

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.alive():
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.log.info("stopped")


# ─── Supervisor ──────────────────────────────────────────────────────────────
class Supervisor:
    def __init__(self, cfg, cloudflared):
        self.cfg = cfg
        port = cfg["port"]
        self.local_url = f"http://127.0.0.1:{port}"

        env = dict(os.environ, PYTHONUNBUFFERED="1")
        self.server = Child("server", [sys.executable, "server.py"], cfg["server_dir"], env=env)
        self.tunnel = Child(
            "cloudflared",
            [cloudflared, "tunnel", "--no-autoupdate", "--url", self.local_url],
            str(HERE), on_line=self._on_tunnel_line,
        )

        self.link = None              # latest link seen in cloudflared output
        self.published_link = None    # latest link the backend accepted
        self.last_publish = 0.0
        self.last_public_check = 0.0
        self.public_fails = 0
        self.next_try = {"server": 0.0, "cloudflared": 0.0}
        self.stopping = threading.Event()

    def _on_tunnel_line(self, line):
        m = LINK_RE.search(line)
        if m and m.group(0) != self.link:
            self.link = m.group(0)
            log.info("tunnel link: %s", self.link)

    # ── backend ──
    def publish(self, link):
        payload = {"action": "update", "secret": self.cfg["tool_secret"], "link": link}
        req = urllib.request.Request(
            self.cfg["apps_script_url"], data=json.dumps(payload).encode(),
            headers={"Content-Type": "text/plain"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                reply = json.loads(res.read().decode())
        except (urllib.error.URLError, OSError, ValueError) as e:
            log.warning("could not reach backend: %s", e)
            return False
        if not reply.get("ok"):
            log.error("backend refused the link: %s", reply.get("error"))
            return False
        return True

    # ── one supervision pass ──
    def ensure_running(self, child, now):
        if child.alive():
            return False
        if child.proc is not None:
            child.log.warning("exited (code %s)", child.proc.returncode)
            child.proc = None
            self.next_try[child.name] = now + RESTART_DELAY if now - child.started_at < 30 else now
        if now < self.next_try[child.name]:
            return False
        child.start()
        self.save_pids()
        return True

    def step(self):
        now = time.time()
        self.ensure_running(self.server, now)
        if self.ensure_running(self.tunnel, now):
            self.link = None
            self.public_fails = 0

        link = self.link
        if link:
            due = now - self.last_publish >= self.cfg["heartbeat_minutes"] * 60
            if link != self.published_link or due:
                if self.publish(link):
                    if link != self.published_link:
                        log.info("published new link to backend")
                    self.published_link = link
                    self.last_publish = now

        self.check_public(now)

    def check_public(self, now):
        """Quick tunnels can die silently; if the public link stops working, restart it."""
        link = self.link
        if (not link or link != self.published_link
                or now - self.tunnel.started_at < PUBLIC_CHECK_GRACE
                or now - self.last_public_check < self.cfg["public_check_minutes"] * 60):
            return
        self.last_public_check = now
        if not http_ok(self.local_url + "/login"):
            return   # server itself is down; that's handled separately
        if http_ok(link + "/login", timeout=30):
            self.public_fails = 0
            return
        self.public_fails += 1
        log.warning("public link check failed (%d/%d)", self.public_fails, PUBLIC_MAX_FAILS)
        if self.public_fails >= PUBLIC_MAX_FAILS:
            log.warning("restarting tunnel to get a fresh link")
            self.tunnel.stop()

    def save_pids(self):
        pids = {str(c.proc.pid): Path(c.args[0]).name for c in (self.server, self.tunnel) if c.alive()}
        PIDS_FILE.write_text(json.dumps(pids), encoding="utf-8")

    def run(self):
        log.info("serving %s via %s", self.cfg["server_dir"], self.local_url)
        try:
            while not self.stopping.is_set():
                try:
                    self.step()
                except Exception:
                    log.exception("unexpected error (continuing)")
                self.stopping.wait(self.cfg["check_seconds"])
        finally:
            self.tunnel.stop()
            self.server.stop()
            PIDS_FILE.unlink(missing_ok=True)
            log.info("AutoStart stopped")


def main():
    setup_logging()
    lock = single_instance()
    if lock is None:
        log.info("already running — exiting")
        return
    log.info("=" * 50)
    log.info("AutoStart starting")
    cfg = load_config()
    cloudflared = find_cloudflared(cfg["cloudflared"])
    kill_leftovers()
    prevent_sleep()

    sup = Supervisor(cfg, cloudflared)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sup.stopping.set())
    sup.run()


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code not in (None, 0):
            log.error(str(e.code))
        raise
