# EHA Threat Model

## Overview

EHA processes sensitive email data and integrates with Google APIs. This document identifies the top 10 threats and their mitigations.

## Assets

1. **User OAuth tokens** (Google access + refresh tokens)
2. **Email content** (transient, in-memory only)
3. **User rules and preferences**
4. **Session tokens** (JWT access + refresh)
5. **Push notification tokens** (device tokens)

---

## Threat 1: OAuth Token Theft

**Risk**: HIGH — Stolen tokens grant access to user's Gmail and Calendar.

**Mitigations**:
- Tokens encrypted at rest using libsodium `crypto_secretbox` (XSalsa20-Poly1305)
- Encryption key stored in environment, KMS-ready for production
- Refresh tokens rotated on each use
- Scopes limited to `gmail.readonly`, `gmail.compose`, `calendar.events.readonly`
- **NO `gmail.send` scope** — prevents automated sending even with stolen tokens
- Token revocation on account deletion

## Threat 2: JWT Session Hijacking

**Risk**: MEDIUM — Stolen JWT grants temporary API access.

**Mitigations**:
- Short-lived access tokens (15 minutes)
- Refresh tokens (7 days) with single-use rotation
- Token bound to user ID (not transferable)
- HTTPS only in production
- No tokens in URL parameters

## Threat 3: Gmail Webhook Spoofing

**Risk**: HIGH — Fake webhooks could trigger unauthorized email processing.

**Mitigations**:
- Verification token validation on webhook endpoint
- Google Pub/Sub JWT bearer token validation (production)
- Idempotent processing (duplicate messages ignored via UNIQUE constraint)
- Webhook only triggers async job — no direct data access

## Threat 4: AI Prompt Injection

**Risk**: MEDIUM — Malicious email content could manipulate AI output.

**Mitigations**:
- Strict JSON schema validation on all AI outputs
- AI responses never directly executed (only presented to user)
- Email content truncated before AI processing (8000 chars max)
- Confidence scores flag uncertain outputs
- User must explicitly confirm all AI-proposed actions

## Threat 5: Email Data Leakage

**Risk**: HIGH — Permanent storage of email content violates privacy.

**Mitigations**:
- Full email body processed ONLY in-memory, never persisted to database
- Only metadata stored: message_id, thread_id, subject, from_addr, snippet
- PII redaction middleware on all structured logs
- Email addresses masked in logs (`[REDACTED_EMAIL]`)
- Data minimization principle applied across all storage

## Threat 6: Unauthorized Data Access (Multi-tenant)

**Risk**: HIGH — User A accessing User B's data.

**Mitigations**:
- Every database query filtered by `user_id` from JWT
- `user_id` extracted from validated JWT, never from request body
- Foreign key constraints prevent orphaned data
- Cascade delete ensures complete cleanup
- No admin endpoints expose other users' data

## Threat 7: Rate Limiting Bypass / DoS

**Risk**: MEDIUM — Abusive API usage could degrade service.

**Mitigations**:
- Per-user sliding window rate limiting (100 req/min)
- Redis-backed rate limiter with fail-open behavior
- Celery queue with worker prefetch limits
- API timeout configuration (30s default)
- Separate Celery queues for Gmail, notifications (isolation)

## Threat 8: Insecure Token Storage (Mobile)

**Risk**: MEDIUM — Device-level token theft.

**Mitigations**:
- expo-secure-store uses iOS Keychain and Android Keystore
- No tokens in AsyncStorage or localStorage
- Tokens cleared on logout
- Short-lived access tokens limit exposure window

## Threat 9: Push Notification Token Abuse

**Risk**: LOW — Stolen push tokens could send fake notifications.

**Mitigations**:
- Push tokens are device-specific, not universal
- Backend verifies user_id before sending
- Stale token cleanup (90-day automated purge)
- Notification payload doesn't contain sensitive data
- Critical actions require in-app authentication

## Threat 10: Audit Trail Tampering

**Risk**: LOW — Modifying audit logs to hide malicious activity.

**Mitigations**:
- Audit log is append-only (no update/delete endpoints)
- Audit entries include user_id, action, entity, timestamp
- Cascade delete only on user account deletion (by user themselves)
- Structured logging with immutable timestamps
- Production: forward logs to external SIEM

---

## Compliance Readiness

| Requirement | Status |
|-------------|--------|
| Data minimization | Implemented (no email body storage) |
| Right to deletion | `DELETE /users/me/data` cascade |
| Audit trail | `audit_log` table with all mutations |
| Encryption at rest | libsodium for tokens, KMS-ready |
| Consent | OAuth scopes require explicit consent |
| Data export | Planned for v2 |
