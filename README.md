# EHA — Email Helper Agent

AI-powered email assistant with smart notifications, draft generation, and calendar integration.

**EHA never sends emails automatically.** All draft replies are created in Gmail's draft folder — the user must review and send them manually.

## Features (v1 MVP)

- **Gmail Integration**: Real-time push notifications via Google Pub/Sub with polling fallback
- **Smart Rules**: Configurable rules to match emails by sender, subject, labels, keywords, and time windows
- **AI Assistant**: Email summaries, multi-tone draft replies, calendar event extraction
- **Calendar Integration**: On-device calendar writing with reminder support (iOS EventKit + Android CalendarContract)
- **Push Notifications**: APNs (iOS) and FCM (Android) for instant alerts
- **Security**: Encrypted token storage (libsodium), PKCE OAuth, JWT sessions, PII redaction in logs

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | React Native (Expo bare workflow) |
| Backend | Python 3.11 + FastAPI |
| Queue | Redis + Celery |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 + Alembic |
| AI | Provider-agnostic (OpenAI / Anthropic) |

## Prerequisites

- Docker & Docker Compose
- Node.js 20+
- Python 3.11+
- Google Cloud project with:
  - OAuth 2.0 credentials (Web application type)
  - Gmail API enabled
  - Cloud Pub/Sub API enabled
  - A Pub/Sub topic for Gmail push

## Setup

### 1. Clone and configure

```bash
git clone <repo-url> && cd eha
cp .env.example .env
# Edit .env with your credentials
```

### 2. Google Cloud Setup

1. **Create OAuth credentials** at [Google Cloud Console](https://console.cloud.google.com/apis/credentials):
   - Application type: Web application
   - Authorized redirect URI: `http://localhost:8000/api/v1/auth/google/callback`
   - Note the Client ID and Client Secret

2. **Enable APIs**:
   - Gmail API
   - Google Calendar API
   - Cloud Pub/Sub API

3. **Create Pub/Sub topic**:
   ```bash
   gcloud pubsub topics create gmail-push
   gcloud pubsub subscriptions create gmail-push-sub \
     --topic=gmail-push \
     --push-endpoint=https://your-domain/api/v1/gmail/webhook
   ```

4. **Grant Gmail publish permissions**:
   ```bash
   gcloud pubsub topics add-iam-policy-binding gmail-push \
     --member="serviceAccount:gmail-api-push@system.gserviceaccount.com" \
     --role="roles/pubsub.publisher"
   ```

### 3. Generate encryption key

```bash
python -c "import nacl.utils, base64; print(base64.b64encode(nacl.utils.random(32)).decode())"
```

Add the output as `ENCRYPTION_KEY` in `.env`.

### 4. Start backend

```bash
docker compose up -d
```

This starts: API (port 8000), PostgreSQL (port 5432), Redis (port 6379), Celery worker, Celery beat.

### 5. Run migrations

```bash
docker compose exec api alembic upgrade head
```

### 6. Start mobile app

```bash
cd apps/mobile
npm install
npx expo start
```

For iOS: `npx expo run:ios`
For Android: `npx expo run:android`

### 7. Push Notifications Setup

**FCM (Android)**:
1. Create a Firebase project
2. Download `service-account.json`
3. Set `FCM_CREDENTIALS_JSON` path in `.env`

**APNs (iOS)**:
1. Create an APNs key in Apple Developer Portal
2. Download the `.p8` key file
3. Set `APNS_KEY_PATH`, `APNS_KEY_ID`, `APNS_TEAM_ID` in `.env`

## API Documentation

With the backend running: http://localhost:8000/docs (Swagger UI)

Key endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/google/start` | Start OAuth PKCE flow |
| POST | `/api/v1/auth/google/callback` | Exchange code for tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/rules` | List user rules |
| POST | `/api/v1/rules` | Create rule |
| GET | `/api/v1/alerts` | List alerts |
| POST | `/api/v1/ai/summarize` | Summarize email |
| POST | `/api/v1/ai/drafts` | Generate draft replies |
| POST | `/api/v1/ai/extract-event` | Extract calendar event |
| POST | `/api/v1/drafts` | Create Gmail draft |
| POST | `/api/v1/events/confirm` | Confirm proposed event |
| DELETE | `/api/v1/users/me/data` | Delete all user data |

## Running Tests

```bash
cd services/api
pip install -e ".[dev]"
pytest tests/ -v
```

## Architecture

```
Mobile App ─── HTTPS ──> FastAPI Backend ──> PostgreSQL
                              │
                              ├──> Redis (rate limiting + cache)
                              ├──> Celery (async jobs)
                              ├──> Gmail API (read, drafts)
                              ├──> AI Provider (summaries, drafts, events)
                              └──> APNs/FCM (push notifications)
```

Gmail push flow:
```
Gmail → Google Pub/Sub → POST /gmail/webhook → Celery task
  → Fetch history → Match rules → Create alerts → Push notifications
```

## Security Highlights

- OAuth tokens encrypted at rest (libsodium NaCl SecretBox)
- PKCE flow for mobile OAuth (S256 code challenge)
- JWT sessions with 15-min TTL + 7-day refresh tokens
- Per-user rate limiting (100 req/min, Redis sliding window)
- All queries filtered by user_id (multi-tenant isolation)
- PII redaction in all structured logs
- Email body never permanently stored
- Webhook verification for Pub/Sub notifications
