# Documents-api

A document management service: a **Django REST API** with a **React** client.

Users keep their documents in folders by type (with version history), request
documents from other people through secure one-time links, get reminders before
documents expire, and buy a plan to lift the upload limit. Accounts support
email/password and Google sign-in, two-factor authentication and per-device
session management.

---

## 🚀 Tech stack

| Backend | Frontend |
|---|---|
| Python 3.12, Django, Django REST Framework | React, TypeScript, Vite |
| PostgreSQL, Redis | React Router, TanStack Query, axios |
| Celery + Celery Beat (emails, reminders) | React Hook Form + zod, Tailwind CSS |
| SimpleJWT, Google Identity, Twilio (SMS) | Vitest, Testing Library, MSW |
| Stripe subscriptions, AWS S3 (private, signed URLs) | oxlint, Prettier |
| drf-yasg (Swagger), pytest + factory_boy, flake8, pylint, black | |

Everything runs in Docker Compose.

---

## ▶️ Quick start

```bash
cp .env.example .env          # fill in DB, SECRET_KEY, AWS, Stripe, Google keys
docker compose up --build -d
docker compose exec app python manage.py migrate
docker compose exec app python manage.py createsuperuser
```

| | URL |
|---|---|
| Web app | http://localhost:5173 |
| API | http://localhost:8000/api/ |
| Swagger / ReDoc | http://localhost:8000/swagger/ · http://localhost:8000/redoc/ |
| Django admin | http://localhost:8000/admin/ |
| pgAdmin | http://localhost:8080 |

Then, in the admin, add a few **Document types** and (for payments) a paid **Plan**
with its Stripe price id. The FREE plan is created by a migration.

### Development notes

- **Emails** (email confirmation links, 2FA codes, document requests) are printed to
  the logs by default — `docker compose logs -f celery`. Set `EMAIL_BACKEND` to the
  SMTP backend to really send them.
- **SMS codes** are logged as `[DEV 2FA MOCK]` while `DJANGO_DEBUG=True`.
- **Stripe webhooks** need the Stripe CLI:
  `stripe listen --forward-to localhost:8000/api/billing/webhook/`, then put the
  printed `whsec_…` into `STRIPE_WEBHOOK_SECRET`. Test card: `4242 4242 4242 4242`.
- **Google sign-in**: add `http://localhost:5173` to *Authorized JavaScript origins*
  of the OAuth client; the frontend reads `GOOGLE_CLIENT_ID` from the root `.env`.
- `FRONTEND_URL` (default `http://localhost:5173`) is used for links in emails and
  Stripe redirects.

---

## 📦 Features

**Authentication**
- Registration with email confirmation; login / logout with JWT (rotating refresh tokens)
- Google sign-in (account is created or linked automatically)
- Two-factor authentication by email or SMS (phone confirmed first): 6-digit code,
  valid 20 minutes, 3 attempts, resend cooldown
- "Trust this device" for 90 days; every login is a device session — users see
  browser, IP, location and last login, and can end any session (its tokens stop
  working immediately) or all other sessions

**Profile** — name, avatar (S3), password change; Google-only accounts can set a password.

**Documents**
- Upload PDF / XLS / XLSX / CSV (≤ 10 MB) with a type and expiration date
- One folder per type: the newest upload is *active*, older ones *replaced*;
  deleting the active one restores the previous version
- Search, sorting, expiration date filters; files are served via expiring signed URLs
- Users never see other users' documents

**Document requests** — ask anyone by email for a document type; they upload once
through a public link (30 days, unguessable token), no account needed. Resend at most
once per hour, cancel at any time.

**Plans & payments** — FREE has an upload limit; paid plans via Stripe Checkout remove
it. Plan change and cancellation at the end of the billing period.

**Notifications & reminders** — every email is logged; a daily Celery task reminds about
documents expiring within 30 days (once per document).

**Admin** — users with profile fields and plan, block/activate and change plans in bulk,
all documents read-only with search by name and author.

---

## 🧪 Tests and code quality

```bash
# Backend: pytest (uses in-memory file storage, never the real S3 bucket)
docker compose exec app python -m pytest -c ../pytest.ini
docker compose exec app flake8 --config ../.flake8 .

# Frontend
docker compose exec frontend npm test
docker compose exec frontend npm run lint
docker compose exec frontend npm run typecheck
```

---

## 🗂 Project structure

```
app/                  Django project
  config/             settings, urls, celery
  apps/accounts/      users, auth, 2FA, device sessions
  apps/documents/     document types, documents, requests
  apps/billing/       plans, subscriptions, Stripe
  apps/notifications/ emails, reminders
frontend/             React client (see frontend/README.md)
```

Git workflow: one feature branch and pull request per task, merged into `develop`.
