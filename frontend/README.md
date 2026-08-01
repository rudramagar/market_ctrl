# Market Control Frontend — Users, Firms and Markets

Static frontend design using HTML5, CSS and vanilla JavaScript.

## Pages

- `index.html` / `users.html` — Users list
- `firms.html` — Firms list
- `markets.html` — Markets list

Only these three entity pages are included. There is no dashboard, sidebar, activity page or admin navigation panel.

## Preview on macOS

```bash
cd market-control-frontend-users-firms-markets
./scripts/serve.sh
```

Open `http://127.0.0.1:3000`.

## Current behavior

- Users are loaded from `GET /api/v1/users`
- Every entity page checks `GET /health` before showing live content
- A shared DROP-unavailable landing page replaces entity content while state is unavailable
- Manual retry and automatic retry every five seconds
- Search and state filter
- Native confirmation dialog
- Local Activate/Suspend row updates
- Responsive layout

Firms and Markets still use placeholder table data. Their REST integration will be added separately.

## Tailwind CLI

The committed `css/output.css` makes the frontend run immediately without npm or a build step. The project retains a Tailwind entry file and optional standalone CLI scripts for later styling work.

```bash
./scripts/download-tailwind-macos.sh
./scripts/watch-css.sh
```

Do not run the build script until Tailwind source styling has been moved into `src/input.css`; the current committed stylesheet is the approved static design source of truth.


## Header and navigation

The static preview now uses a two-level responsive header:

- Top bar: application identity, backend/DROP status, and the logged-in user menu.
- Navigation bar: Users, Firms, Markets, plus a scalable `More` dropdown for future modules.
- Mobile: a menu button collapses the navigation into a vertical list.

The displayed user (`Rudra Magar`) is placeholder data. Later it will be populated from Keycloak identity claims.
