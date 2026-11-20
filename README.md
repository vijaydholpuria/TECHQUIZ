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
