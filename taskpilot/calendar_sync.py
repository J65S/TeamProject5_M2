"""Optional direct Google refresh using an existing read-only OAuth access token."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = 'taskpilot'

from .calendar_planner import CALENDAR_FILE, ZONE
from .paths import ENV_FILE


def refresh_calendar():
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE)
    except ImportError:
        pass
    token = os.getenv('GOOGLE_CALENDAR_ACCESS_TOKEN')
    if not token:
        raise ValueError('Automatic Google refresh needs a read-only GOOGLE_CALENDAR_ACCESS_TOKEN in the server environment. Your Codex calendar connector can refresh the local snapshot separately.')
    now = datetime.now(ZONE)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=8)
    events, page = [], None
    for _ in range(100):
        query = dict(timeMin=start.isoformat(), timeMax=end.isoformat(), singleEvents='true', maxResults=250, timeZone=str(ZONE))
        if page:
            query['pageToken'] = page
        req = Request('https://www.googleapis.com/calendar/v3/calendars/primary/events?' + urlencode(query), headers={'Authorization': 'Bearer '+token})
        with urlopen(req, timeout=15) as response:
            data = json.load(response)
        for e in data.get('items', []):
            declined = any(a.get('self') and a.get('responseStatus') == 'declined' for a in e.get('attendees', []))
            if e.get('status') == 'cancelled' or e.get('transparency') == 'transparent' or declined:
                continue
            def stamp(value):
                if 'dateTime' in value:
                    result = datetime.fromisoformat(value['dateTime'].replace('Z', '+00:00'))
                    if result.tzinfo is None:
                        raise ValueError('Calendar event has no timezone.')
                    return result.isoformat()
                return datetime.fromisoformat(value['date']).replace(tzinfo=ZONE).isoformat()
            events.append(dict(title=e.get('summary') or 'Busy', start=stamp(e['start']), end=stamp(e['end'])))
        page = data.get('nextPageToken')
        if not page:
            break
    else:
        raise ValueError('Calendar has too many pages; refresh was not saved.')
    snapshot = dict(timezone=str(ZONE), synced_at=now.isoformat(), coverage_start=start.isoformat(), coverage_end=end.isoformat(), events=events)
    CALENDAR_FILE.parent.mkdir(exist_ok=True)
    temporary = CALENDAR_FILE.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(snapshot, out)
    temporary.replace(CALENDAR_FILE)
    return dict(synced_at=snapshot['synced_at'], event_count=len(events))


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Optional calendar refresh helper. Start TaskPilot with python agent.py; this file does not launch the app.')
    parser.add_argument('--refresh', action='store_true', help='Refresh the saved calendar using GOOGLE_CALENDAR_ACCESS_TOKEN')
    args = parser.parse_args()
    if not args.refresh:
        parser.print_help()
        return 0
    try:
        result = refresh_calendar()
    except (ValueError, OSError) as exc:
        print(f'Calendar refresh unavailable: {exc}', file=sys.stderr)
        return 1
    print(f"Calendar refreshed: {result['event_count']} events; synced at {result['synced_at']}.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
