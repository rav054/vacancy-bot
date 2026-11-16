# Agri & Soil Science Vacancy Bot

Watches the recruitment pages that matter for **B.Sc. Agriculture / M.Sc. Soil Science /
Ph.D. Soil Science**, tells you when something new appears, reminds you before each
deadline, and keeps a document checklist per exam so nothing is missing when you sit
down to fill the form.

## What it covers

31 sources across nine sectors. Sources marked **official** are read straight from the
organisation's own notice board, so they carry real dates; the rest are news feeds that
act as an early-warning net for sites that need JavaScript or block automated clients.

| Sector | Sources |
|---|---|
| **ICAR & research** | ASRB *(official)* — ARS, NET, SMS, STO, Technical Assistant, RMP · ICAR-IISS Bhopal *(official)* — Indian Institute of Soil Science · ICAR-IISR Kozhikode *(official, also carries NBSS&LUP and other institutes' notices)* · ICAR-IARI *(official)* · ICAR soil & land-resource institutes · KVK / ICAR project posts (SRF, YP, Technical Assistant) |
| **Central govt & ISRO** | ISRO incl. Space Applications Centre *(official, dated table)* · NRSC Hyderabad *(official)* · DRDO RAC / CEPTAM *(official)* · UPSC (IFoS, Assistant Director) · SSC & agriculture ministry · Forest service, ICFRE, soil conservation |
| **Banking** | IBPS *(official)* — AFO / CRP-SPL · NABARD *(official career notices)* · SBI / RRB / cooperative bank agriculture-officer posts |
| **PSUs** | IFFCO AGT · KRIBHCO, NFL, RCF, FACT, National Seeds, Paradeep, Coromandel · FCI, CWC & warehousing · NDDB, NAFED, SFAC, dairy & cooperative |
| **State services** | UPSSSC · UPPSC / UPESSC / UP agriculture dept (ADO) · all major state PSCs (BPSC, MPPSC, RPSC, TNPSC, APPSC, …) · state agriculture departments |
| **Universities** | Punjab Agricultural University *(official)* · Professor / Assistant Professor in Soil Science & Agronomy · State Agricultural Universities (TNAU, GBPUAT, OUAT, CCS HAU, ANGRAU, BHU) |
| **Fellowships** | JRF / SRF / RA / post-doc in soil & agricultural sciences |
| **Private** | ITC Agri, Godrej Agrovet, Syngenta, Bayer, UPL, Dhanuka, Mahindra Agri, Tata Chemicals |
| **International** | ICRISAT, IRRI, CIMMYT, FAO India, CGIAR |

Use the **sector** dropdown on the dashboard to look at one slice at a time.

---

## Quick start

```bash
pip install -r requirements.txt
```

```bash
python -m bot check
```

```bash
python notify_local.py --open
```

The first command fetches every source and rebuilds `docs/index.html`. The second pops
up Windows notifications for anything new or closing, then opens the dashboard.

Or just double-click **`run_check.cmd`**, which does both.

---

## The dashboard

`docs/index.html` is a single self-contained page. It groups everything by urgency:

| Group | Meaning |
|---|---|
| **Act now** | 3 days or less to the last date |
| **Closing this week** | 4–7 days |
| **Open** | more than a week |
| **Deadline not detected** | the source never stated a last date — open the notice and set it |
| **Applied** | you marked it done |
| **Closed** | kept for 30 days, then dropped |

Every card carries a checklist: the ~19 common documents plus the extras for that exam
family. Ticks are saved in your browser, so progress survives a refresh and a rebuild.

Items tagged **news lead** came from a news headline, not the official site. They are
early warnings — always confirm on the official notification before paying a fee.

---

## Commands

```bash
python -m bot check                 # fetch everything, alert, rebuild the dashboard
```

```bash
python -m bot check --no-enrich     # skip opening notices to hunt for the last date
```

```bash
python -m bot list --open-only      # print what is live, with the ids
```

```bash
python -m bot deadline <id> 2026-12-05
```

```bash
python -m bot applied <id>
```

```bash
python -m bot dismiss <id>
```

Ids come from `python -m bot list`; a unique prefix is enough. Setting a deadline
yourself resets the reminder history, so you still get the 21/14/7/3/1/0-day nudges.

---

## Running it in the cloud (GitHub Actions) — already set up

Repository: **https://github.com/rav054/vacancy-bot**
Live dashboard: **https://rav054.github.io/vacancy-bot/**

`.github/workflows/check.yml` runs the check twice a day (08:00 and 16:30 IST), commits
the refreshed `data/` and `docs/`, and publishes the dashboard to GitHub Pages. Pages is
set to the GitHub Actions source and Actions has read-and-write permission, so nothing
further needs configuring.

To run it on demand:

```bash
"/c/Program Files/GitHub CLI/gh.exe" workflow run "Check vacancies" --ref main
```

### Your PC and the cloud see different sites

This is worth knowing. Several Indian government sites answer only Indian IP addresses,
and a few `.icar.gov.in` hosts do not resolve on Indian ISPs at all. So the two runs
cover slightly different ground:

| Source | Your PC | GitHub runner |
|---|---|---|
| NABARD career notices | ✅ | ❌ refused |
| DRDO RAC | ✅ | ❌ refused |
| everything else (29 sources) | ✅ | ✅ |

Sources with this behaviour are marked `geo_restricted: true`, and the dashboard's
Source health panel reports them as a skip rather than an error. A local run therefore
adds real coverage — `run_check.cmd` does a `git pull --rebase --autostash` first so it
starts from the latest cloud result.

Nothing is pushed back automatically. To publish what a local run found:

```bash
git add data docs && git commit -m "Local check" && git push
```

### Desktop alerts from the cloud run

GitHub Actions cannot pop a toast on your machine, so pull its results and notify
locally:

```bash
python notify_local.py --from-url https://rav054.github.io/vacancy-bot
```

To have that happen by itself, register the scheduled task:

```powershell
powershell -ExecutionPolicy Bypass -File ".\install_alert_task.ps1"
```

It creates a task called **Vacancy alerts** that fires at **08:15 and 16:45** — fifteen
minutes after each cloud run — for the current user only, which is what lets the toasts
appear at all (a task running as SYSTEM has no desktop to show them on). No
administrator rights needed.

The important setting is `StartWhenAvailable`: if the PC was off or asleep at the
scheduled time, the check runs as soon as it comes back, so a deadline is never silently
missed. Output goes to `data/alerts.log`.

Test it immediately, change the times, or remove it:

```powershell
Start-ScheduledTask -TaskName "Vacancy alerts"
```

```powershell
powershell -ExecutionPolicy Bypass -File ".\install_alert_task.ps1" -Times 07:30,19:00
```

```powershell
Unregister-ScheduledTask -TaskName "Vacancy alerts" -Confirm:$false
```

Already-announced alerts are remembered in `data/notified_local.json`, so you are never
told the same thing twice.

---

## Tuning it

**`sources.yaml`**

- `settings.reminder_days` — when to nudge you (default 21, 14, 7, 3, 1, 0)
- `keywords` — relevance scoring. `strong` = 4 points, `medium` = 3, `weak` = 1,
  and anything in `exclude` is dropped outright. An item needs
  `relevance_threshold` (3) points to be kept.
- `news_filter` — the extra gate on news headlines, so press releases, results and
  "top colleges" listicles do not get in
- `news_window` (`45d`) — appended to every news query as Google News's `when:`
  operator. Without it the feeds rank by relevance and are swamped by years-old
  stories; with it, nearly every headline is recent.
- `news_lead_ttl_days` (45) — undated news leads older than this are dropped

Per source:

- `parser` — `anchors` for most notice boards, `news_rss` for a Google News RSS URL,
  `isro_table` for ISRO's dated table
- `category` — which sector dropdown it appears under
- `boost_phrases` — lifts titles that never say "agriculture" (IBPS's "CRP-SPL",
  NABARD's "Grade A RDBS")
- `require_in_title` — a headline must name one of these. Google News ranking leaks
  unrelated organisations into narrow feeds; this keeps an ICAR story out of the
  UPSC feed.
- `max_items` — cap on how far down a page to read, for notice boards that keep a
  long archive newest-first (IISS Bhopal keeps 131 entries; we read 30)
- `insecure: true` — the site serves a broken TLS chain; read it anyway

### Adding a state you care about

The state feeds cover UP in detail and the other commissions generically. For a
specific state, copy the `state-psc-news` block, swap the commission name into the
query, and set `require_in_title` to that commission's abbreviation.

**`checklists.yaml`** — the `common` block applies to every vacancy; each family block
adds its own. Edit freely; the dashboard picks changes up on the next rebuild.

---

## Honest limits

- **Not every site gives a deadline.** The official sources (ISRO, IISS Bhopal, IISR,
  NRSC, ASRB, IBPS, NABARD, PAU, DRDO) carry real dates, and those drive the reminders.
  UPSSSC, IFFCO, UPPSC and the PSU portals are JavaScript-only or need dropdown
  selections, so those arrive as news leads with no date and land in *Deadline not
  detected*. Set the date once with `python -m bot deadline <id> <date>` and the
  reminders work from then on.
- **`upsc.gov.in` answers automated clients with 403**, so it is not scraped. UPSC
  notices come through its news feed, and the card links straight to the official ORA
  vacancy list.
- **Some `*.icar.gov.in` hosts do not resolve from many Indian ISPs** (IISS, NBSS&LUP,
  CSSRI). IISS Bhopal is read from `iiss.res.in` instead, which works; NBSS&LUP and
  CSSRI notices arrive via ICAR-IISR's board and the ICAR soil news feed.
- **NABARD and DRDO RAC refuse the GitHub runner's IP**, so the cloud run skips them.
  Run locally now and then to cover those two.
- **`asrb.gov.in` serves an incomplete TLS chain**, so that one source is fetched with
  `insecure: true` in `sources.yaml`. It is a read-only fetch of a public notice board.
- **A quiet board is not a broken bot.** Check the *Source health* panel at the bottom
  of the dashboard: it shows matched-of-scanned per source for the last run.
- **Nothing is submitted for you.** The bot only watches, reminds and checklists; you
  fill the forms.
