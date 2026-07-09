# Flashbook Dashboard — self-updating site

A live funnel-tests dashboard that **rebuilds itself** every time you add fresh Stripe data.
You drop new CSVs into `data/`, commit, and GitHub republishes the site in ~1–2 minutes. No terminal needed after setup.

---

## How it works (the loop)

1. You export **Customers** and **Payments** (unified) from Stripe.
2. You add those two CSVs into the `data/` folder in this repo (drag-and-drop in the GitHub website).
3. GitHub Actions runs `build_dashboard.py`, which **merges every CSV in `data/`** (dedupes by id, so history is kept), recomputes all metrics, and publishes the dashboard.
4. Your dashboard URL updates automatically.

You never overwrite old files — just keep adding new exports. The merge handles the rest.

---

## One-time setup (~10 minutes, all in the browser)

**1. Create the repo**
- Go to github.com → **New repository** → name it e.g. `flashbook-dashboard` → Private is fine → Create.

**2. Upload these files**
- On the repo page: **Add file → Upload files** → drag in *everything from this folder* (keep the structure: `build_dashboard.py`, `funnel_config.py`, `requirements.txt`, the `data/` folder, and the `.github/` folder).
- If the browser won't let you upload the `.github/workflows/build.yml` via drag-drop, use **Add file → Create new file**, type `.github/workflows/build.yml` as the name, and paste the file's contents.
- Commit.

**3. Turn on Pages**
- Repo **Settings → Pages** → under **Build and deployment**, set **Source = GitHub Actions**. Save.

**4. First build**
- Go to the **Actions** tab → you should see "Build & deploy dashboard" running (or click **Run workflow**).
- When it finishes (green check), open **Settings → Pages** — your live URL is shown there (looks like `https://<you>.github.io/flashbook-dashboard/`).

That URL is your dashboard. Share it with the team.

---

## Updating the data (the recurring 30-second task)

1. Export the two CSVs from Stripe (Customers + Payments).
2. In the repo, open the **`data/`** folder → **Add file → Upload files** → drag both CSVs in → **Commit changes**.
3. That's it. The Actions tab will show a new build; ~1–2 min later the URL shows fresh numbers.

**Notes**
- Filenames don't matter — the script detects customers vs payments by their columns.
- Keep the old files in `data/`. The newest Stripe export only covers a short recent window; the script needs the history to rebuild full cohorts. More files = more complete.

---

## Updating ad spend / ROAS

Ad spend isn't in Stripe, so it lives in the `SPEND` block at the top of **`build_dashboard.py`**.
- Edit it in the browser: open `build_dashboard.py` → pencil icon → update the `spend` numbers / windows → commit. The site rebuilds.
- Each test has a slot; fill `spend` with the actual Meta "amount spent" for that test's window.

## Adding a new funnel / changing prices

Everything about funnels and prices lives in **`funnel_config.py`** (one source of truth).
- New funnel: add a line to `FUNNELS` and `BANDS`.
- Price change: update the band in `BANDS`.
- Commit → site rebuilds.

---

## Files

| File | What it is |
|---|---|
| `build_dashboard.py` | Builds the dashboard. Merges `data/`, computes metrics, writes `site/index.html`. Holds the editable `SPEND` block. |
| `funnel_config.py` | Funnels, prices, and amount→plan/upsell bands. The single source of truth. |
| `data/` | Your Stripe CSV exports (customers + payments). Keep adding; never overwrite. |
| `.github/workflows/build.yml` | The automation: rebuild + publish on every change. |
| `requirements.txt` | Python dependency (pandas). |

## Test it locally (optional)

```
pip install -r requirements.txt
python build_dashboard.py        # reads data/, writes site/index.html
```
Open `site/index.html` in a browser.
