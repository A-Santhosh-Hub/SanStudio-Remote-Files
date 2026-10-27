# AutoStart (automation tool)

Runs on the **host PC** (the computer that has your files). When Windows starts it automatically:

1. starts the file server (`../server/server.py`)
2. starts a free Cloudflare quick tunnel → gets the `https://….trycloudflare.com` link
3. sends the link to your Google Apps Script backend (with the secret key)
4. keeps watching every 30 seconds:
   - server crashed → restart it
   - tunnel crashed → restart it → send the **new** link
   - public link stopped working (checked every 5 min) → new tunnel → new link
   - every 5 min → "I'm alive" check-in (updates `last_seen` in the sheet)
5. keeps the PC from going to sleep while it runs

No window, nobody needs to click anything. Uses only the Python standard library.

---

## Files

| File | What |
|---|---|
| `autostart.py` | The tool |
| `config.example.json` | Template — copy to `config.json` and fill in |
| `config.json` | Your Apps Script URL + `tool_secret` — **never upload this** (in `.gitignore`) |
| `install_autostart.ps1` | Adds it to Windows Task Scheduler and starts it |
| `uninstall_autostart.ps1` | Stops and removes it |
| `automation.log` | Log of everything (created when it runs) |

---

## Setup

### 1. Create `config.json`
Copy `config.example.json` → `config.json` and fill in:
```json
{
  "apps_script_url": "https://script.google.com/macros/s/…/exec",
  "tool_secret": "…from the Settings tab of your Google Sheet…"
}
```
Optional extra settings (defaults shown):
```json
  "server_dir": "../server",
  "port": 5000,
  "cloudflared": "",
  "check_seconds": 30,
  "heartbeat_minutes": 5,
  "public_check_minutes": 5
```
`cloudflared` blank = found automatically.

### 2. Try it once by hand
```powershell
cd automation
python autostart.py
```
Within ~30 seconds you should see `tunnel link: https://….trycloudflare.com` and
`published new link to backend`. Check the Google Sheet → `current_link`. Press **Ctrl+C** to stop.

### 3. Install auto-start
Pick **one**:

**A. PC logs in to Windows by itself** (or someone logs in after a restart):
```powershell
powershell -ExecutionPolicy Bypass -File .\install_autostart.ps1
```

**B. PC stays on the login screen after a restart** (e.g. after Windows Update):
Open PowerShell **as Administrator**, then:
```powershell
powershell -ExecutionPolicy Bypass -File .\install_autostart.ps1 -AtStartup
```
It asks for your Windows password once (Task Scheduler stores it to run before anyone logs in).

### 4. Restart the PC and check
After restart, wait 2 minutes, then open your GitHub page — it should say **Server online**.

---

## Everyday

| I want to… | Do this |
|---|---|
| See what happened | Open `automation.log` |
| Stop it | `.\uninstall_autostart.ps1` |
| Start it again | `.\install_autostart.ps1` |
| Change the access (GitHub page) password | Edit it in the Google Sheet — nothing to restart |
| Change the file-server password | Edit `server\password.txt`, then restart the PC (or uninstall + install) |
