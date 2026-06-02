# 📚 Manga Update Checker

Automatically checks manga sites for recent chapter updates and sends a
notification to **Microsoft Teams** and/or **Email** when an update is detected.

Runs on **GitHub Actions** — free, no server required.

---

## Files

```
manga-checker/
├── manga_checker.py              ← Main script (edit MANGA_URLS here)
├── requirements.txt              ← Python dependencies
└── .github/
    └── workflows/
        └── manga_check.yml      ← Schedule & secrets config
```

---

## Setup (5 steps)

### 1 · Create a GitHub Repository

1. Go to https://github.com/new
2. Name it e.g. `manga-checker`, set it to **Private**
3. Upload all these files (drag & drop or use GitHub Desktop)

---

### 2 · Add Your Manga URLs

Open `manga_checker.py` and edit the `MANGA_URLS` list:

```python
MANGA_URLS = [
    "https://kaliscan.com/manga/solo-bug-player",
    "https://kaliscan.com/manga/another-manga",   # add as many as you like
]
```

---

### 3 · Set Up a Teams Incoming Webhook

1. Open the Teams channel where you want notifications
2. Click **…** (More options) → **Workflows**
3. Search for **"Post to a channel when a webhook request is received"**
4. Follow the setup, copy the **webhook URL** at the end

> ⚠️ If you see "Connectors" instead of "Workflows", use that — both produce a URL.

---

### 4 · Add Secrets to GitHub

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name        | Value                                    |
|--------------------|------------------------------------------|
| `TEAMS_WEBHOOK_URL`| The webhook URL from Step 3              |
| `EMAIL_FROM`       | *(optional)* your Gmail address          |
| `EMAIL_TO`         | *(optional)* destination email           |
| `EMAIL_PASSWORD`   | *(optional)* Gmail App Password          |

> For email: use a **Gmail App Password**, not your regular password.
> Get one at https://myaccount.google.com/apppasswords

---

### 5 · Enable Actions

1. Go to the **Actions** tab in your repo
2. Click **"I understand my workflows, go ahead and enable them"**
3. The schedule starts automatically. Use **"Run workflow"** to test immediately.

---

## Adjusting the Schedule

Edit `.github/workflows/manga_check.yml`:

```yaml
# Every 30 minutes (default)
- cron: "0,30 * * * *"

# Every hour
- cron: "0 * * * *"

# Every 15 minutes
- cron: "*/15 * * * *"
```

Note: GitHub Actions can't do exact 45-minute intervals (cron limitation),
so 30 minutes is the closest practical option.

---

## Adjusting the Update Threshold

In `manga_checker.py`, change `UPDATE_THRESHOLD_MINUTES`:

```python
UPDATE_THRESHOLD_MINUTES = 60   # notify if updated within 60 minutes
```

Since the script runs every 30 min, a 60-minute window ensures nothing is missed.

---

## Adding More Websites

The script works on any manga site that shows a "Last update: X minutes ago"
text on the manga's detail page. Just paste the URL into `MANGA_URLS`.

If a site uses JavaScript rendering and the script can't detect updates,
open an issue — it can be extended with a headless browser.

---

## Troubleshooting

- **No notification received** — Check the Actions run log (Actions tab → click the run)
- **"Could not detect" update text** — The site may use a different HTML structure;
  check the run log and compare with the site's page source
- **Teams webhook errors** — Regenerate the webhook URL in Teams and update the secret
