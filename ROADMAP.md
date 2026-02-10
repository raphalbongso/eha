# EHA Roadmap

## v1.0 — MVP (Current)

### Core Features
- [x] Google OAuth with PKCE (gmail.readonly, gmail.compose, calendar.events.readonly)
- [x] Gmail push notifications via Google Pub/Sub + polling fallback
- [x] Configurable email matching rules (from, subject, label, keywords, attachments, time window)
- [x] Rule match alerts with push notifications
- [x] AI email summarization
- [x] AI draft reply generation (multiple tones)
- [x] Gmail draft creation (NEVER auto-send)
- [x] AI calendar event extraction with confidence scores
- [x] On-device calendar write with reminders (EventKit + CalendarContract)
- [x] User data deletion endpoint

### Infrastructure
- [x] FastAPI backend with async support
- [x] PostgreSQL with Alembic migrations
- [x] Redis + Celery for async job processing
- [x] Docker Compose local development
- [x] GitHub Actions CI pipeline
- [x] Encrypted token storage (libsodium)
- [x] Per-user rate limiting
- [x] PII redaction in logs
- [x] Audit logging

---

## v2.0 — Intelligence & Travel

### Route-Based Leave Reminders
- [x] Google Maps / Apple Maps integration via RouteProvider
- [x] Travel time calculation between home/work and event location
- [x] "Time to leave" push notifications with traffic-aware timing
- [x] User preference for transport mode (driving, transit, cycling, walking)
- [x] Home and work address configuration

### Enhanced AI
- [x] Smart reply suggestions based on user's writing style
- [x] Thread context awareness (multi-email conversations)
- [x] Priority inbox scoring (heuristic + AI-assisted)
- [x] Email categorization (invoices, meetings, newsletters, action-required)

### Data & Privacy
- [ ] Full data export endpoint (GDPR Article 20)
- [ ] Optional email content storage (user opt-in, encrypted)
- [ ] User preference for AI data retention

### Platform
- [ ] Prometheus + Grafana metrics dashboard
- [ ] Sentry error tracking integration
- [ ] WebSocket for real-time alert updates
- [ ] Background app refresh for iOS

---

## v3.0 — Automation & Integrations

### Smart Automation
- [x] Auto-categorize and label emails (with user approval)
- [x] Follow-up reminders ("No reply in 3 days")
- [x] Meeting prep summaries (aggregate emails related to upcoming meetings)
- [x] Digest emails (daily/weekly summary of matched rules)

### Integrations
- [ ] Microsoft Outlook / Office 365 support
- [x] Slack notifications as alternative to push
- [ ] Todoist / Notion task creation from action items
- [ ] Google Calendar two-way sync

### Multi-User
- [ ] Team/organization accounts
- [ ] Shared rules
- [ ] Delegation ("respond on behalf of")

### Platform
- [ ] Web app (React)
- [ ] Expo EAS build pipeline
- [ ] Blue/green deployments
- [ ] Multi-region infrastructure
