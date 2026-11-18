# Calendar modes and refresh

The header offers two independent calendar modes:

- **Interview demo:** five fictional commitments on a repeatable schedule. The clock starts at 9:30 AM on the conversation date. No personal calendar file is read.
- **My Google Calendar:** reads `.local/calendar.json`, initially retrieved through the Google Calendar connector in Codex. It uses the real current time in America/New_York, reports the refresh timestamp, and only knows the primary calendar's imported coverage.

The calendar and assignment sources are separate. Calendar mode does not make the example assignments real coursework. Expand the assignment panel to select project syllabus files if appropriate.

## Current connection

Codex can read your connected Google Calendar, but the local app cannot invoke Codex tools. The supplied snapshot is available now. Ask Codex to refresh your primary calendar for the next eight days when needed. The app refuses to propose verified free windows when the snapshot is more than 24 hours old or outside its covered period. Even a fresh snapshot may miss subsequent event changes; suggested windows are not reservations.

## Optional direct refresh

If you have an existing Google OAuth access token authorized for read-only calendar events, set `GOOGLE_CALENDAR_ACCESS_TOKEN` in the server environment or the ignored root `.env` file, and launch from the virtual environment so python-dotenv is available. Never put a token in JavaScript, a URL, a Git commit, or an interview transcript.

Click **Study hours & breaks → Refresh Google snapshot**. This uses only Google's read endpoint for the primary calendar, expands recurring events, follows pagination, ignores cancelled/declined/transparent events, and handles all-day busy events. A successful full retrieval replaces the snapshot. Failure keeps the previous one. The implementation follows [Google's events.list reference](https://developers.google.com/workspace/calendar/api/v3/reference/events/list).

The app does not implement Google account login, issue tokens, or renew expired access tokens. End-to-end direct refresh still needs verification with a user-supplied read-only token. A production deployment needs a proper OAuth flow and secure per-user token storage.

## Scheduling and exports

Study hours, buffer time, block duration, and breaks are adjustable below the chat. Changes apply to the next request. Tasks are ordered by deadline and placed only before the end of the listed due date; exact deadline times are unknown. Off-calendar commitments and task progress are also unknown. “After work” requires a matching calendar event title; unfamiliar employer names are not automatically classified as work.

**Download calendar blocks (.ics)** downloads events locally for explicit import. No Google events are created or updated automatically. Review the times before importing. Private-mode replies/transcripts may include event titles; use demo mode for anonymous, reproducible interview fixtures, or use the owner's calendar as authorized and document that choice. The private snapshot itself is never served as a static file.
