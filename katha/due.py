"""Which Shorts slot is due right now? Stdlib only, so the workflow can ask BEFORE
installing anything (the repo is private: Actions minutes are a budget).

    python katha/due.py      -> prints a slot number (0-3), or "none"

GitHub delays and drops scheduled runs (Quizora's notes: hours late; this repo's
06:35 slot on its first day never fired at all). So every trigger posts the
EARLIEST slot whose time has passed today and that is not in the ledger yet.
The slot crons and a 2-hourly backup cron therefore all converge on the same
plan, and a dropped trigger is made up at the next one.
"""
import datetime as dt, json
from pathlib import Path

SLOT_UTC = {0: (2, 35), 1: (6, 35), 2: (12, 35), 3: (15, 5)}   # keep in sync with katha.yml
LATEST_CATCHUP_H = 20          # don't post a slot later than 20:00 UTC (01:30 IST): dead hours


def due(now=None, ledger_path=Path(__file__).parent / "ledger.json"):
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.hour >= LATEST_CATCHUP_H:
        return None
    today = str(now.date())
    led = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else []
    done = {r.get("slot") for r in led if r.get("date") == today and r.get("status") == "posted"}
    for slot, (h, m) in sorted(SLOT_UTC.items()):
        if (now.hour, now.minute) >= (h, m) and slot not in done:
            return slot
    return None


if __name__ == "__main__":
    s = due()
    print("none" if s is None else s)
