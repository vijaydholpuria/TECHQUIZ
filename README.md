# TechQuiz

TechQuiz is a responsive, real-time quiz competition site built with FastAPI, Supabase PostgreSQL, vanilla HTML/CSS/JavaScript, and WebSockets. It is a single-server application: FastAPI serves both the API and the browser interface.

## Features

- Secure cookie-based admin session; the admin username and password come from environment variables.
- Dynamic quiz builder with four options, answer key, and an individual 1–300 second time limit per question.
- QR join link generated from `BASE_URL`—there is no production URL hardcoded in the application.
- Authenticated WebSocket updates for joining, waiting room, question transitions, and live host status.
- Server-owned question windows, response timing, scoring, duplicate-answer prevention, and final ranking.
- Correct answer keys are never placed in participant-facing API or WebSocket messages.
- Final top-three podium, full leaderboard, and protected CSV export for the host.
- Supabase PostgreSQL cascade deletion and automatic 24-hour cleanup of quiz information.

## Technology stack

- Frontend: semantic HTML5, CSS3, vanilla JavaScript
- Backend: Python, FastAPI, Uvicorn, WebSockets
- Storage: Supabase PostgreSQL with SQLAlchemy ORM and Psycopg
- QR codes: `qrcode` with Pillow

## Project structure

```text
TECHQUIZ/
├── backend/             # routers, models, WebSocket manager, business services
├── frontend/            # static pages, CSS, browser JavaScript
├── database/            # optional local SQLite fallback (ignored by Git)
├── tests/               # API, scoring, ranking, and cleanup tests
├── .env.example
├── requirements.txt
└── README.md
```

## Installation

```powershell
cd TECHQUIZ
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

On Linux/macOS activate with `source venv/bin/activate` instead. Open `http://localhost:8000` after starting the server.

## Configuration

Set the following in `.env` before publishing the site:

- `DATABASE_URL`: Supabase **Direct connection** URI from the Dashboard → Connect, changed to use `postgresql+psycopg://` at the beginning. Include `?sslmode=require`. Use the Supabase Session Pooler URI for IPv4-only hosts.
- `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW`: keep these modest so this app does not exhaust your Supabase connection allowance.
- `ADMIN_USERNAME` and `ADMIN_PASSWORD`: admin login credential pair.
- `SECRET_KEY`: a long, unique random string used to sign the admin session cookie.
- `BASE_URL`: the public origin used in QR codes, for example `https://quiz.example.com`.
- `PORT`: optional deployment port, default `8000`.
- `COOKIE_SECURE=true`: enable on HTTPS deployments.

Do not use the development defaults for a public deployment. Keep the database password and every Supabase secret exclusively in `.env`; browser JavaScript does not need, and must not receive, a Supabase key or database URL.

## How to host a quiz

1. Go to `/admin/login`, sign in using the values in `.env`, and choose **Create new quiz**.
2. Add questions and all four options. Choose the correct answer and time limit for each.
3. Generate the quiz. The QR screen displays a QR code and a live participant list.
4. Start only when participants have joined. The server starts each question and advances automatically at its deadline.
5. Watch the live view or end a quiz early. The result page contains the ranking and protected CSV download.

Players scan the QR code (or open `/join/TECH-XXXXXX`), enter a name, and wait. Their session token is retained in browser session storage solely to reconnect them to their existing participant record. It is not an admin credential.

## Scoring and real-time behavior

For a time limit `T` and server-calculated response time `R`, `floor(max(0, T-R))` is the speed score. Correct answers receive an additional 100 points. Ranking is score descending, correct count descending, total response time ascending, then earliest final answer.

The WebSocket endpoint is `/ws/quiz/{quiz_id}`. A participant must present their generated participant token; host sockets must also carry the signed admin session cookie. Question payloads intentionally contain only the public question/options and server timestamps—not `correct_option`. The browser countdown is visual only; the server accepts no late answer even if a browser is inaccurate.

## Data retention and deployment

Each quiz gets `expires_at = created_at + 24 hours`. Startup and a recurring 15-minute background task remove expired quizzes; SQLAlchemy cascades remove their questions, participants, and answers. Deploy as one ASGI process and configure its Supabase database URL as an environment variable. Ensure the proxy supports WebSocket upgrade requests and set `BASE_URL` to the public HTTPS origin.

## Tests

Run the automated checks with:

```powershell
pytest -q
```

The test suite covers creation, joining, authentication, answer restrictions, scoring, tie-breaking, and expiry cleanup.

---

© 2026 TechQuiz · Created by Vijay Kumar Dholpuria
