# SanStudio Remote Files

**Open the files on your home/office PC from anywhere — your phone, your laptop, any browser.
100% free. No domain. No port forwarding. No paid hosting.**

You turn the PC on → it shares itself automatically → you open one fixed web page → enter a password → you see your files, stream videos, and download anything.

---

## 💡 The idea

You have a PC with lots of files (big storage). You go somewhere else for a few days.
You want your files — but you don't want to call someone every day to *"start the server and send me the link"*.

The free way to put a PC on the internet is a **Cloudflare quick tunnel**, but its link **changes every time it starts**.
This project solves that:

1. When the PC starts, everything starts by itself.
2. The new tunnel link is saved to a Google Sheet automatically.
3. You open **one fixed GitHub page**, enter a password, and it shows you today's link.

---

## 🧭 How it works

```
 HOST PC (has your files)                         FREE CLOUD                          YOU (anywhere)
┌──────────────────────────┐
│ automation/autostart.py  │
│   │ starts               │
│   ├─► server/ (Flask)    │◄──────── Cloudflare quick tunnel ◄──────── 4. open link → server password
│   │   localhost:5000     │          https://xyz.trycloudflare.com            → browse / stream / download
│   │                      │
│   └─► cloudflared ───────┼── 1. new link ──► Google Apps Script ──► Google Sheet
│                          │      + secret      (backend/Code.gs)      (stores link)
└──────────────────────────┘                          ▲
                                                      │ 3. returns link only if password is right
                                        GitHub Pages (github-page/index.html)
                                                      ▲
                                                      └── 2. you open the page + access password
```

**Two passwords, two locks:**

| Password | Where it's stored | What it unlocks |
|---|---|---|
| **Access password** | Google Sheet → `viewer_password` | The GitHub page → shows the current link |
| **Server password** | `server/password.txt` on the host PC | The actual files |

---

## ✨ Features

- 🎬 **Stream huge videos** (made for 6+ GB files) with seeking — HTTP Range support
- 🎵 Audio player, 🖼️ image viewer, ⬇️ download any file type
- 📁 Folders, search, sort, filters, grid/list view, works on mobile
- 🔐 Password login on the server, 5 wrong tries → 5-minute lockout
- 🛡️ Path-traversal protection, hidden files never served, listens on localhost only
- 🤖 **Auto-start** with Windows, **auto-restart** if the server or tunnel crashes
- 🔁 Detects a dead tunnel, makes a new one, publishes the new link — by itself
- 🟢 GitHub page shows **Server online / offline** (from the PC's 5-minute check-in)
- 😴 Keeps the PC awake while running
- 📜 History of link changes and logins in the Google Sheet
- 💸 Everything free: Cloudflare quick tunnel, Google Apps Script, GitHub Pages

---

## 📂 Project structure

```
SanStudio-Remote-Files/
├── server/                 ← File server (Python Flask + Waitress)
│   ├── server.py
│   ├── templates/          ← index.html (file browser), login.html
│   ├── requirements.txt
│   ├── start.bat / start.sh
│   └── uploads/            ← put your files here (created on first run)
├── automation/             ← Auto-start + tunnel + link publisher
│   ├── autostart.py
│   ├── config.example.json ← copy to config.json
│   ├── install_autostart.ps1
│   └── uninstall_autostart.ps1
├── backend/                ← Google Apps Script (stores the link)
│   ├── Code.gs
│   └── test_backend.py
└── github-page/            ← The fixed page you open from anywhere
    └── index.html
```

Each folder has its own `README.md` with more details.

---

## ✅ What you need

- A **Windows 10/11 PC** to host the files (the server also runs on Mac/Linux; auto-start scripts are Windows-only)
- A **Google account** (for the Sheet + Apps Script)
- A **GitHub account** (for the page)
- About **30 minutes** for the first setup

---

## 🚀 Setup — step by step

### Part 1 — Install Python and cloudflared (host PC)

Open **PowerShell** and run:
```powershell
winget install --id Python.Python.3.14 --scope user
winget install --id Cloudflare.cloudflared
```
Close and reopen PowerShell, then check:
```powershell
python --version
cloudflared --version
```

### Part 2 — File server (host PC)

1. Put this whole project folder somewhere, e.g. `D:\SanStudio-Remote-Files\`.
2. Install the Python packages:
   ```powershell
   cd D:\SanStudio-Remote-Files\server
   pip install -r requirements.txt
   ```
3. Create **`server\password.txt`** — put your **server password** on the first line.
4. Start it: double-click **`start.bat`** → open http://localhost:5000 → log in.
5. Put your files in **`server\uploads\`** (subfolders are fine). Close the window when done testing.

### Part 3 — Google Sheet + Apps Script backend

1. Go to **https://sheets.new** → name it e.g. *Remote Files*.
2. **Extensions → Apps Script** → delete the sample code → paste all of **`backend/Code.gs`** → 💾 Save.
3. Pick **`setup`** in the function dropdown → **▶ Run** → allow permissions.
   *"Google hasn't verified this app"* is normal for your own script → **Advanced → Go to … (unsafe) → Allow**.
4. Back in the sheet → **Settings** tab → type your **access password** in column B of `viewer_password`.
5. **Deploy → New deployment → ⚙️ Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
   → **Deploy** → copy the **Web app URL** (ends with `/exec`).
6. Copy the **`tool_secret`** value from the Settings tab.

More detail: [`backend/README.md`](backend/README.md)

### Part 4 — Automation (host PC)

1. In `automation\`, copy **`config.example.json` → `config.json`** and paste your two values:
   ```json
   {
     "apps_script_url": "https://script.google.com/macros/s/…/exec",
     "tool_secret": "…"
   }
   ```
2. *(Optional)* check the backend: `python backend\test_backend.py` → all **PASS**.
3. Run it once by hand:
   ```powershell
   cd D:\SanStudio-Remote-Files\automation
   python autostart.py
   ```
   Wait ~30 s for `tunnel link: https://….trycloudflare.com` and `published new link to backend`.
   The Google Sheet's `current_link` now shows it. Press **Ctrl+C**.
4. Make it start with Windows:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install_autostart.ps1
   ```
   If your PC stays on the **login screen** after a restart, use instead (PowerShell **as Administrator**):
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install_autostart.ps1 -AtStartup
   ```

More detail: [`automation/README.md`](automation/README.md)

### Part 5 — GitHub page

1. Open **`github-page/index.html`** in any editor. Near the bottom, find:
   ```js
   const API_URL = "PASTE_WEB_APP_URL_HERE";
   ```
   Paste your **Web app URL** there and save. (This URL is safe to publish — it gives nothing without the password.)
2. Test it: double-click `index.html` → enter the access password → you should see the link.
3. On GitHub: **New repository** (e.g. `files`, **Public**) → **uploading an existing file** → drop `index.html` → **Commit**.
4. Repo **Settings → Pages** → Source: **Deploy from a branch** → **main** / **(root)** → **Save**.
5. After ~1 minute open `https://<your-username>.github.io/<repo-name>/` — bookmark it / add to your phone's home screen.

### Part 6 — Final test

- [ ] Restart the host PC → wait 2 minutes → GitHub page says 🟢 **Server online**
- [ ] On your phone using **mobile data** (not the same Wi-Fi): GitHub page → access password → **Open my files** → server password → your files
- [ ] Windows power settings: **never sleep / hibernate** (backup — the tool already keeps the PC awake, but not a closed laptop lid)

---

## 📱 Daily use

1. Open your GitHub page.
2. Enter the access password (tick *Remember on this device* if it's your phone).
3. Tap **Open my files ↗** → enter the server password → done.

| I want to… | Do this |
|---|---|
| Change the access password | Edit `viewer_password` in the Google Sheet — instant |
| Change the server password | Edit `server\password.txt`, restart the PC |
| See what the host PC did | `automation\automation.log` |
| See who logged in | Google Sheet → **History** tab |
| Stop everything | `automation\uninstall_autostart.ps1` |

---

## 🔐 Security — please read

- **Never upload** `automation/config.json`, `server/password.txt` or `server/.secret_key`. They're already in `.gitignore`.
- **Keep the Google Sheet private** — it contains the `tool_secret` and the access password.
- The backend only accepts `*.trycloudflare.com` links, so even a leaked secret can't redirect your page to a fake site.
- Use **strong, different** passwords for the access page and the server.
- Anyone with the tunnel link still needs the **server password** to see any file.
- **Using a work/office PC?** Ask your IT team first. Exposing a company PC to the internet can break company rules, and many company networks block `cloudflared`.
- Cloudflare quick tunnels are meant for testing and personal use — no uptime guarantee.

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| GitHub page: *"Setup needed: paste your Apps Script URL"* | Put your `/exec` URL in `API_URL` in `index.html` |
| GitHub page: *"Server offline"* | Host PC is off, asleep, or has no internet. Check `automation.log` |
| GitHub page: *"Wrong password"* | That's the **access** password from the Google Sheet, not the server one |
| Log says `backend refused the link: Unauthorized` | `tool_secret` in `config.json` doesn't match the sheet |
| Server window closes immediately | Missing `server\password.txt` |
| `cloudflared not found` | `winget install --id Cloudflare.cloudflared`, then reopen PowerShell |
| `.mkv` / `.avi` video won't play | Browsers can't play every format. `.mp4` works best — or just download |
| Changed `Code.gs` but nothing changed | **Deploy → Manage deployments → ✏️ → Version: New version → Deploy** |

---

## 🙌 Credits

Idea by **[SanStudio](https://a-santhosh-hub.github.io/in/)** — built with the help of Claude.

Free services used: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/), [Google Apps Script](https://developers.google.com/apps-script), [GitHub Pages](https://pages.github.com/).
