# runinsights

## What is runinsights
What started off as a challenge to run a marathon (26.2 miles) has become a new hobby and lifestyle. The first thing my friends and I did was download Strava, the popular running and activity tracking app. Strava has helped us keep each other motivated and accountable for our marathon, and it has a lot of great features. However, unless you pay for a monthly subscription, all you can see is base-level analytics on your recorded runs. As someone who wants to improve and loves looking at my run data, I wanted a way to take a bigger deep dive into my runs. That's where the idea for runinsights came from: what if I could build something for myself that shows a lot more detail about my recorded runs?

runinsights connects to your Strava account, pulls your activity history into a database you own, and keeps it up to date. With your data in your own Postgres database, you can run your own analysis on it without a paywall.

> **Status:** early development. Data ingestion is the current focus. The analytics and insights layer is not built yet.

## What it does today

- **Strava sign-in (OAuth 2.0):** generates a Strava authorization link, handles the callback, and stores the athlete's access and refresh tokens. Tokens are refreshed automatically when they are within an hour of expiring.
- **User and connection setup:** the first time an athlete authorizes, runinsights creates a `User` from their Strava profile and a `StravaConnection` that links them to their Strava account. If they authorize again, the existing connection is reused.
- **First-time backfill:** for a new connection, runinsights pages through the athlete's whole Strava activity history and saves every activity.
- **Incremental sync:** after the backfill finishes, later runs only fetch activities newer than the most recent one already stored.
- **Strava rate-limit handling:** the ingestor reads Strava's rate-limit headers after each request. When the 15-minute limit gets close, it pauses. When the daily limit is reached, it records the paused state and stops.
- **Validation and safe upserts:** each activity is validated with Pydantic before it is written. Activities are upserted on their Strava ID, so re-running ingestion doesn't create duplicates, and edited names, distances and kudos counts get updated.

## How it works

```
 Strava OAuth ──► /oauth/callback ──► User + StravaConnection + StravaAuthToken
                                                │
                                                ▼
              /get-activities ──► StravaIngestor.run()
                                     │  for each StravaConnection:
                                     │    fetch / refresh token
                                     │    ├─ no backfill yet → initial_backfill()
                                     │    └─ backfill done   → incremental_ingest()
                                     │    rate limiter checks every request
                                     ▼
                              Postgres (activities table)
```

## Project structure

```
runinsights/
├── main.py                    # FastAPI app, routes, startup (creates tables)
├── core/
│   └── config.py              # Reads OAuth and database settings from the environment
├── dependencies/
│   ├── db.py                  # Database engine and per-request session for the API
│   ├── pipeline_db.py         # Standalone session for ingestion jobs
│   ├── strava_oauth.py        # Builds the OauthManager and rate limiter
│   └── ingestors.py           # Builds the StravaIngestor
├── models/
│   ├── user_models.py         # User table, StravaAthlete schema
│   ├── stravaconnection.py    # StravaConnection table, PipelineStatus enum
│   ├── token_models.py        # StravaAuthToken table, token schemas
│   └── activities.py          # Activities and ActivityStreams tables, raw input schemas
├── pipelines/
│   └── ingest/
│       ├── base.py            # BaseIngestor: shared run loop and logging
│       └── StravaIngestor.py  # Strava backfill and incremental sync
└── services/
    ├── oauthmanager.py        # Auth URL, token exchange, token refresh
    ├── strava_connect.py      # Finds or creates the User and StravaConnection
    └── strava_rate_limiter.py # Tracks Strava's 15-minute and daily read limits
```

## Data model

| Table | Purpose |
| --- | --- |
| `user` | A runinsights user, created from their Strava profile (name, location, sex, weight, height). |
| `stravaconnection` | Links a user to their Strava account and tracks ingestion state: backfill status, whether the backfill is complete, last sync time and total activities ingested. |
| `stravaauthtoken` | Access token, refresh token and expiry for a connection. |
| `activities` | One row per Strava activity: name, sport type, distance, moving time, start date, time zone, average and max speed, average and max heart rate, device and kudos. |
| `activitystreams` | Per-second samples for an activity (time, distance, heart rate). The table exists, but stream ingestion is still being built. |

Tables are created automatically when the app starts.

## Getting started

### Prerequisites
- Python 3.10+
- PostgreSQL
- A Strava API application. Create one at <https://www.strava.com/settings/api> and set **Authorization Callback Domain** to `localhost`.

### Install

```bash
git clone https://github.com/abeltran09/runinsights.git
cd runinsights
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install fastapi uvicorn sqlmodel psycopg2-binary requests python-dotenv
```

### Configure
Create a `.env` file in the project root. It is already listed in `.gitignore`.

```env
CLIENT_ID=your_strava_client_id
CLIENT_SECRET=your_strava_client_secret
REDIRECT_URL=http://localhost:8000/oauth/callback
DB_URL=postgresql://user:password@localhost:5432/runinsights
```

### Run

```bash
uvicorn main:app --reload
```

1. Open `http://localhost:8000/request-access`. It returns a Strava authorization link.
2. Open that link in your browser and approve access. Strava redirects you to `/oauth/callback`, which saves your account and tokens.
3. Open `http://localhost:8000/get-activities` to run ingestion. The first run downloads your full history. Later runs only pull new activities.

## API endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/request-access` | Returns the Strava authorization URL. |
| GET | `/oauth/callback` | Strava redirects here after you authorize. Exchanges the code for tokens and creates the user and connection. |
| GET | `/get-activities` | Runs ingestion for every connected account. |
| GET | `/get-token?connection_id=<id>` | Development only: returns a valid access token for a connection, refreshing it if needed. |

## Roadmap
- [x] Strava OAuth and token refresh
- [x] Full-history backfill
- [x] Incremental sync
- [x] Rate-limit handling
- [ ] Resume a paused backfill from where it stopped
- [ ] Activity streams (per-second pace, heart rate, cadence, elevation)
- [ ] Run ingestion on a schedule instead of through an endpoint
- [ ] Database migrations
- [ ] Insights: pace and heart-rate zones, heart-rate drift, grade-adjusted pace, weekly mileage and training load
- [ ] A dashboard to explore it all
