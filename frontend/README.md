# ClientPulse Frontend

Modern client and ticket management interface built with React, TypeScript, and Vite.

## Overview

The ClientPulse frontend provides a responsive interface for managing customers, support tickets, users, and business activity.

It communicates with the ClientPulse REST API.

## Technology Stack

- **React 19** — UI components
- **TypeScript** — Type safety
- **Vite** — Development server and production build
- **Tailwind CSS 4** — Styling
- **Lucide React** — Icons
- **Recharts** — Data visualization
- **ESLint** — Code quality

## Project Structure

```text
frontend/
├── public/
├── src/
│   ├── assets/
│   ├── services/
│   │   └── api.ts
│   ├── App.tsx
│   ├── App.css
│   ├── index.css
│   └── main.tsx
├── .env.example
├── package.json
├── package-lock.json
├── tsconfig.json
└── vite.config.ts
```

## Requirements

- Node.js 22 or later
- npm

## Installation

Run these commands from the `frontend` directory:

```powershell
npm ci
Copy-Item .env.example .env
```

## Environment Configuration

The local `.env.example` contains:

```env
VITE_API_URL=http://127.0.0.1:8000
```

Change `VITE_API_URL` only when the backend API uses a different local address.

For production, configure `VITE_API_URL` in the Render Static Site environment settings with the public HTTPS URL of the deployed ClientPulse backend.

Do not store passwords, API keys, or private credentials in frontend environment variables. Variables prefixed with `VITE_` are exposed to the browser and embedded in the client build.

## Development

Start the development server:

```powershell
npm run dev
```

Vite displays the local development URL in the terminal.

## Quality Checks

Run ESLint:

```powershell
npm run lint
```

Create a production build:

```powershell
npm run build
```

Preview the production build locally:

```powershell
npm run preview
```

The generated production files are placed in the `dist/` directory.

## API Integration

API communication is centralized in:

```text
src/services/api.ts
```

The API base URL is configured through `VITE_API_URL`, with a local development fallback.

## Deployment on Render

Deploy this frontend as a **Render Static Site**.

### Render service settings

| Setting | Value |
|---|---|
| Repository | `mariemL123/ClientPulse` |
| Branch | `main` |
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |

### Production environment variable

In the Render Static Site settings, define:

```env
VITE_API_URL=https://<your-backend-service>.onrender.com
```

Replace the placeholder with the actual public HTTPS URL of the deployed ClientPulse API. The backend must allow the exact frontend origin in its `CORS_ORIGINS` configuration.

### Deployment notes

- Deploy the backend API and configure its production database before relying on the frontend deployment.
- Set `VITE_API_URL` before building the production frontend. Changes to this variable require a new frontend build/deploy.
- `VITE_` variables are public client-side configuration, not a secure place for secrets.
- The frontend deployment is not considered complete until the deployed site can authenticate and communicate successfully with the production API.

See the [Render deployment guide](https://render.com/docs/your-first-deploy) and the [Vite static deployment guide](https://vite.dev/guide/static-deploy) for platform instructions.
