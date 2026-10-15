# Documents — Frontend

React client for the Documents API (Django backend lives in `../app`).

**Stack:** Vite · React · TypeScript · React Router · TanStack Query · axios · Tailwind CSS · Vitest + Testing Library · oxlint · Prettier

## Run

With Docker (from the repository root, together with the backend):

```bash
docker compose up --build
```

Locally (Node 24+), backend running on `http://localhost:8000`:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open http://localhost:5173. Requests to `/api` and `/media` are proxied to Django by the
Vite dev server, so no CORS setup is needed in development.

## Scripts

| Command                | Purpose                         |
| ---------------------- | ------------------------------- |
| `npm run dev`          | Dev server with hot reload      |
| `npm run build`        | Type-check and production build |
| `npm run typecheck`    | TypeScript only                 |
| `npm run lint`         | oxlint                          |
| `npm run format`       | Prettier (write)                |
| `npm run format:check` | Prettier (check, for CI)        |
| `npm test`             | Run tests once                  |
| `npm run test:watch`   | Tests in watch mode             |

## Structure

```
src/
  api/        axios client, error parsing, API modules per backend app
  layouts/    MainLayout (authenticated), AuthLayout (guest pages)
  lib/        token storage and helpers
  pages/      route pages
  routes/     route paths and router config
  test/       test setup
```

Routes `/confirm-email`, `/upload/:token`, `/billing/success` and `/billing/cancel`
are also used by the backend in emails and Stripe redirects — see `src/routes/paths.ts`.
