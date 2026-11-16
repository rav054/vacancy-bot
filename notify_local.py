"""Windows desktop notifications for the vacancy tracker.

Run it after `python -m bot check`, or on its own with --from-url to pull the
state that GitHub Actions published, so your PC pops up the alerts even though
the checking happened in the cloud.

  python notify_local.py                      # toast anything new since last time
  python notify_local.py --open               # ...and open the dashboard
  python notify_local.py --from-url <base>    # pull data/ from a published site
  python notify_local.py --all                # re-toast everything, ignore history
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS = ROOT / "data" / "events.json"
VACANCIES = ROOT / "data" / "vacancies.json"
SEEN = ROOT / "data" / "notified_local.json"
DASHBOARD = ROOT / "docs" / "index.html"

MAX_TOASTS = 6

PS_TOAST = r"""
$ErrorActionPreference = 'Stop'
$title = $args[0]
$body  = $args[1]
try {
  [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
  [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime] | Out-Null
  $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
      [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
  $texts = $template.GetElementsByTagName('text')
  $texts.Item(0).AppendChild($template.CreateTextNode($title)) | Out-Null
  $texts.Item(1).AppendChild($template.CreateTextNode($body))  | Out-Null
  $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
  $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
  exit 0
} catch {
  Add-Type -AssemblyName System.Windows.Forms
  $icon = New-Object System.Windows.Forms.NotifyIcon
  $icon.Icon = [System.Drawing.SystemIcons]::Information
  $icon.BalloonTipTitle = $title
  $icon.BalloonTipText  = $body
  $icon.Visible = $true
  $icon.ShowBalloonTip(12000)
  Start-Sleep -Seconds 12
  $icon.Dispose()
  exit 0
}
"""


def toast(title: str, body: str) -> bool:
    """Show one Windows notification. Returns False if the shell call failed."""
    if sys.platform != "win32":
        print(f"[{title}] {body}")
        return True
    script = Path(tempfile.gettempdir()) / "vacbot_toast.ps1"
    script.write_text(PS_TOAST, encoding="utf-8")
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(script), title[:120], body[:240]],
            capture_output=True, text=True, timeout=40,
        )
        if result.returncode != 0:
            print(f"  toast failed: {result.stderr.strip()[:200]}", file=sys.stderr)
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  toast failed: {exc}", file=sys.stderr)
        return False


def pull(base_url: str) -> None:
    """Download data/events.json and data/vacancies.json from a published site."""
    import urllib.request

    base = base_url.rstrip("/")
    for name in ("events.json", "vacancies.json"):
        url = f"{base}/data/{name}"
        target = ROOT / "data" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
            target.write_bytes(response.read())
        print(f"  pulled {url}")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Desktop alerts for the vacancy tracker")
    parser.add_argument("--from-url", help="base URL of the published dashboard (GitHub Pages)")
    parser.add_argument("--open", action="store_true", help="open the dashboard afterwards")
    parser.add_argument("--all", action="store_true", help="ignore what was already notified")
    args = parser.parse_args(argv)

    if args.from_url:
        try:
            pull(args.from_url)
        except Exception as exc:  # noqa: BLE001
            print(f"could not pull published data: {exc}", file=sys.stderr)

    events = load_json(EVENTS, {}).get("events", [])
    store = load_json(VACANCIES, {"items": {}})
    seen = set() if args.all else set(load_json(SEEN, {}).get("keys", []))

    fresh = []
    for event in events:
        key = f"{event['id']}|{event['kind']}|{event.get('threshold', 'new')}"
        if key not in seen:
            fresh.append((key, event))

    undated = [i for i in store.get("items", {}).values()
               if not i.get("last_date") and not i.get("deadline_override")
               and not i.get("applied") and not i.get("dismissed")]

    if not fresh:
        print("nothing new to announce")
    else:
        print(f"{len(fresh)} new alert(s)")

    shown = 0
    for key, event in fresh:
        if shown >= MAX_TOASTS:
            break
        left = event.get("days_left")
        if event["kind"] == "new":
            head = f"New vacancy: {event['org'][:40]}"
            tail = "deadline not stated — open it and set the date" if left is None \
                else f"{left} days left"
        else:
            head = "LAST DAY TODAY" if left == 0 else f"{left} day(s) left — apply now"
            tail = event["org"][:40]
        if toast(head, f"{event['title'][:150]}\n{tail}"):
            shown += 1
        seen.add(key)

    extra = len(fresh) - shown
    if extra > 0:
        toast(f"+{extra} more alert(s)", "Open the dashboard for the full list")
    if undated and fresh:
        print(f"note: {len(undated)} tracked item(s) still have no deadline")

    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps({"keys": sorted(seen)}, indent=2), encoding="utf-8")

    if args.open and DASHBOARD.exists():
        webbrowser.open(DASHBOARD.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
