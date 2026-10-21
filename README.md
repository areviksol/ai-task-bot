# AI Task Bot

**An Omni-Channel Task Management System powered by Telegram, FastAPI, React, PostgreSQL, Redis, and Celery.**

AI Task Bot allows users to create and manage tasks through Telegram text messages, voice messages, and a responsive web dashboard. Tasks are synchronized in real time, with asynchronous voice transcription and reliable background processing.

## Features

### Telegram Bot
- Create tasks by sending text messages.
- Create tasks using voice messages transcribed with OpenAI.
- Receive confirmations and error notifications.
- Sign in to the web dashboard using a secure, single-use Telegram login link.
- Prevent duplicate tasks from repeated Telegram message delivery.

### Web Dashboard
- Responsive React and TypeScript interface.
- Kanban board with Pending, In Progress, and Completed columns.
- Drag-and-drop task status updates.
- Create, view, update, and delete tasks.
- Real-time synchronization using WebSockets.
- Authenticated access to each user's tasks.

### Backend and Reliability
- FastAPI REST API.
- PostgreSQL persistence with SQLAlchemy and Alembic migrations.
- Redis as a Celery message broker and real-time event transport.
- Dedicated Celery worker for voice transcription.
- Celery Beat for periodic recovery of interrupted voice jobs.
- Retry handling for transient failures.
- Voice-job lease ownership, renewal, and stale-worker protection.
- Idempotent task creation and user-level data isolation.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | React, TypeScript, Vite |
| Telegram Bot | aiogram |
| Database | PostgreSQL, SQLAlchemy |
| Migrations | Alembic |
| Background Processing | Celery, Celery Beat |
| Message Broker | Redis |
| Voice Transcription | OpenAI API |
| Real-Time Updates | WebSockets, Redis Pub/Sub |
| Containerization | Docker, Docker Compose |
| Testing | pytest |
| Continuous Integration | GitHub Actions |
| Frontend Web Server | Nginx |

## Architecture

```text
                     Telegram User
                           |
                    Text / Voice
                           |
                      aiogram Bot
                           |
                  +--------+--------+
                  |                 |
              Text Task         Voice Job
                  |                 |
                  v                 v
              PostgreSQL       Redis Queue
                                    |
                               Celery Worker
                                    |
                            OpenAI Transcription
                                    |
                                PostgreSQL
                                    |
                           Redis Pub/Sub Event
                                    |
                                 FastAPI
                                    |
                                WebSocket
                                    |
                             React Dashboard
```

The React dashboard also communicates with FastAPI through authenticated HTTP requests to read and update tasks.

## Running with Docker Compose

### Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose
- A Telegram bot token obtained from [BotFather](https://t.me/BotFather)
- An OpenAI API key with available transcription credits

### 1. Clone the repository

```bash
git clone https://github.com/areviksol/ai-task-bot.git
cd ai-task-bot
```

### 2. Configure environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your local configuration.

The application uses variables including:

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | PostgreSQL database name |
| `POSTGRES_HOST` | PostgreSQL hostname |
| `POSTGRES_PORT` | PostgreSQL port |
| `REDIS_HOST` | Redis hostname |
| `REDIS_PORT` | Redis port |
| `TELEGRAM_BOT_TOKEN` | Telegram bot authentication |
| `OPENAI_API_KEY` | OpenAI transcription API |
| `FRONTEND_URL` | URL used in Telegram login links |
| `SESSION_COOKIE_SECURE` | Controls HTTPS-only session cookies |

For the Docker Compose setup, use the internal service hostnames:

```dotenv
POSTGRES_HOST=db
POSTGRES_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

FRONTEND_URL=http://localhost:8080
SESSION_COOKIE_SECURE=false
```

Set the remaining values in your local `.env` file, including your database credentials and API keys.

**Security:** Never commit `.env` or real credentials. `.env.example` must contain placeholders only. `SESSION_COOKIE_SECURE=false` is intended for local HTTP development; use secure cookies with HTTPS in production.

### 3. Start the application

```bash
docker compose up -d --build
```

Check service status:

```bash
docker compose ps
```

The Docker Compose configuration orchestrates seven services:

| Service | Responsibility |
|---|---|
| `frontend` | React application served by Nginx |
| `api` | FastAPI HTTP and WebSocket endpoints |
| `bot` | Telegram bot |
| `worker` | Asynchronous transcription processing |
| `beat` | Periodic recovery scheduling |
| `db` | PostgreSQL |
| `redis` | Message broker and Pub/Sub |

### 4. Apply database migrations

```bash
docker compose exec api alembic upgrade head
```

### 5. Open the dashboard

Visit:

**http://localhost:8080**

The frontend uses Nginx to forward API and WebSocket traffic to FastAPI.

### 6. Log in through Telegram

1. Open your Telegram bot.
2. Send `/start`.
3. Send `/login`.
4. Open the newly generated login link.
5. View your tasks in the dashboard.

Login links are single-use and expire. Do not share them with other users.

## Example Workflows

### Text Task Creation

1. Send a message to the Telegram bot:

   `Prepare the project presentation`

2. The bot creates a task in PostgreSQL.
3. The backend publishes a task-change notification through Redis.
4. The dashboard receives the event through WebSockets.
5. The Kanban board refreshes without manually reloading the page.

### Voice Task Creation

1. Send a Telegram voice message.
2. The bot registers a voice-processing job and queues background work.
3. A Celery worker claims the job using a time-limited lease.
4. The worker sends the audio for transcription.
5. The transcribed text becomes a task.
6. The bot sends a confirmation and the dashboard updates.

Voice transcription requires an OpenAI API key with sufficient credits.

### Task Status Updates

Tasks move between three statuses:

- **Pending**
- **In Progress**
- **Completed**

Users can change task status through the dashboard, including drag-and-drop on the Kanban board.

## Resilience and Error Handling

### Duplicate Prevention

Telegram may deliver the same update more than once. The application uses message identifiers and database constraints to prevent duplicate task creation.

### Voice Job Reliability

Voice-processing jobs are tracked in PostgreSQL.

The processing system includes:

- Explicit job states and attempt tracking.
- Atomic job claiming.
- Lease tokens to identify the active worker.
- Lease renewal while processing.
- Protection against stale workers completing another worker's job.
- Retries for transient connection and API failures.
- Handling for exhausted OpenAI API quotas.
- Periodic recovery of interrupted or abandoned jobs.

### Authentication and Authorization

The application uses single-use Telegram login tokens and HTTP-only session cookies. Task operations are scoped to the authenticated user.

## Testing

The backend includes unit and integration tests covering:

- Authentication and session handling.
- Task API operations and authorization.
- Telegram message idempotency.
- Voice job state transitions.
- Lease claiming and renewal.
- Worker heartbeat behavior.
- Voice recovery scheduling.
- Successful and duplicate voice processing.
- Failure handling, retries, and retry exhaustion.

The integration tests use an isolated PostgreSQL test database and apply schema migrations through Alembic.

To run tests from the `backend` directory, ensure the local Python dependencies and dedicated test database are configured, then execute:

```bash
python -m pytest -v
```

The test database connection is configured using `TEST_DATABASE_URL`. **Never point this variable to a development or production database.**

### Continuous Integration

GitHub Actions automatically performs:

- Backend tests with a PostgreSQL service.
- Frontend TypeScript and production build checks.
- Docker Compose configuration validation.

The CI workflow uses separate test credentials and does not require real Telegram or OpenAI requests.

## Useful Commands

Start containers:

```bash
docker compose up -d --build
```

Check container status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f api bot worker
```

Run migrations:

```bash
docker compose exec api alembic upgrade head
```

Stop containers:

```bash
docker compose down
```

Do not use `docker compose down -v` unless you intentionally want to remove persistent Docker volumes, including database data.

## Engineering Decisions

**FastAPI:** Provides a modular Python backend with REST and WebSocket support.

**PostgreSQL:** Maintains durable task, user, authentication, and voice-job records.

**Redis + Celery:** Moves voice transcription out of the Telegram message-handling path so slow external API calls do not block bot responsiveness.

**Lease-based voice processing:** Reduces the risk of conflicting workers and supports recovery from interrupted processing.

**WebSockets + Redis Pub/Sub:** Synchronizes task changes across Telegram and the web dashboard.

**Docker Compose:** Provides a reproducible development and assessment environment with the required infrastructure and application services.

## Limitations and Future Improvements

- Live voice transcription requires valid OpenAI API credits.
- The provided Docker Compose setup is intended for local evaluation. Public production hosting would additionally require HTTPS, production secret management, backup policies, and deployment hardening.
- Future improvements could include task due dates, priorities, reminders, and advanced filtering.

## Repository

[github.com/areviksol/ai-task-bot](https://github.com/areviksol/ai-task-bot)

---

Developed as a full-stack automation engineering technical assessment, demonstrating Telegram integration, asynchronous processing, reliable task management, real-time synchronization, and Docker-based orchestration.
