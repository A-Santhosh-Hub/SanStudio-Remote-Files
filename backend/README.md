# SanStudio Link Backend (Google Apps Script)

Free backend that stores the current Cloudflare tunnel link in a Google Sheet.

- The **automation tool** (office PC) sends the new link + a secret key → saved in the sheet.
- The **GitHub page** sends your password → gets the link back only if the password is right.

---

## Setup (about 10 minutes, one time)

### 1. Create the Google Sheet
1. Go to https://sheets.new (logged in to your Google account).
2. Rename it to **SanStudio Links** (top-left).

### 2. Add the script
1. In the sheet: **Extensions → Apps Script**.
2. Delete everything in `Code.gs` and paste the full contents of [`Code.gs`](Code.gs) from this folder.
3. Click 💾 **Save**.

### 3. Run setup
1. In the toolbar function dropdown, choose **`setup`** → click **▶ Run**.
2. Google asks for permission → **Review permissions** → choose your account.
3. You'll see *"Google hasn't verified this app"* — this is normal for your own script.
   Click **Advanced → Go to (project name) (unsafe)** → **Allow**.
4. Go back to the sheet. You now have two tabs: **Settings** and **History**.

### 4. Set your viewer password
In the **Settings** tab, type your password in column **B** of the `viewer_password` row.
You can change it here any time — no redeploy needed.

### 5. Deploy as a web app
1. In Apps Script: **Deploy → New deployment**.
2. Click ⚙️ next to "Select type" → **Web app**.
3. Set:
   - **Execute as:** Me
   - **Who has access:** Anyone
4. **Deploy** → copy the **Web app URL** (ends with `/exec`).

### 6. Save these two values — the next steps need them
| Value | Where to find it | Used by |
|---|---|---|
| Web app URL | Step 5 | Automation tool + GitHub page |
| `tool_secret` | Settings tab, column B | Automation tool only — **never put it on GitHub** |

---

## Test it (PowerShell)

```powershell
$url    = "PASTE_YOUR_WEB_APP_URL"
$secret = "PASTE_TOOL_SECRET"

# Pretend to be the automation tool
Invoke-RestMethod $url -Method Post -Body (@{action="update"; secret=$secret; link="https://test-link.trycloudflare.com"} | ConvertTo-Json)

# Pretend to be the GitHub page
Invoke-RestMethod $url -Method Post -Body (@{action="get"; password="YOUR_PASSWORD"} | ConvertTo-Json)
```

The second command should print `ok: True` and `link: https://test-link.trycloudflare.com`.
Check the **History** tab — you'll see `link_changed` and `login_ok`.

---

## Good to know

- **Changed `Code.gs` later?** Use **Deploy → Manage deployments → ✏️ Edit → Version: New version → Deploy**.
  This keeps the same URL. ("New deployment" would give a new URL.)
- **Keep the sheet private.** Anyone who can open it sees the `tool_secret` and password.
- **Only `*.trycloudflare.com` links are accepted**, so even if the secret leaked, nobody could
  point your page at a fake website.
- **20 wrong passwords in 15 minutes** locks the page for 15 minutes (for everyone).
- **History** keeps the last 1000 events: link changes, logins, failed logins.
- `last_seen` updates every time the office PC checks in — if it's old, the PC is probably off or asleep.
