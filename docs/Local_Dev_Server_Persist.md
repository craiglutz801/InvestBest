# Keep the InvestBest dev server reliable (macOS)

## What actually happens when you “close” the computer

- **Sleep / lid closed:** macOS suspends processes. `localhost:3000` stops responding until the machine wakes. Nothing in this repo can make a dev server run *inside* a sleeping laptop.
- **Shut down or reboot:** Any `npm run dev` you started in a terminal is gone until you start it again.

So “always on while my laptop is closed” is only possible if the app runs **somewhere else** (Vercel, Railway, Fly.io, a small VPS, or a home server that stays awake).

What we *can* do locally:

1. **Survive crashes** and **restart after reboot/login** using PM2.
2. **Optional:** avoid sleep while developing (power settings or `caffeinate`).

---

## Option A — PM2 (recommended for local “set and forget”)

`pm2` is a **devDependency** of `apps/web`, so you do not need a global install.

From `apps/web`:

```bash
# Stop any manual `npm run dev` first (or: lsof -ti tcp:3000 | xargs kill -9)
npm run dev:pm2
npm exec pm2 status
```

Logs:

```bash
npm run dev:pm2:logs
# or: npm exec pm2 logs investbest-web
```

Stop:

```bash
npm run dev:pm2:stop
```

**After reboot** — one-time setup so PM2 restores saved processes:

```bash
cd apps/web
npm exec pm2 save
npm exec pm2 startup
# Run the command PM2 prints (often involves sudo and launchctl).
```

Then after each successful `npm run dev:pm2`, run `npm exec pm2 save` again.

---

## Option B — Production mode on the same machine

If you only need the site up (not hot reload):

```bash
cd apps/web
npm run build
npm start   # listens on PORT or 3000
```

You can still wrap `npm start` in PM2 the same way (change `args` to `start --port 3000` and `script` stays `next`).

---

## Option C — True remote URL (laptop closed)

Deploy `apps/web` to [Vercel](https://vercel.com) or similar, point `DATABASE_URL` at a hosted Postgres (Neon, Supabase, RDS). Then the site is available from any device regardless of your laptop.

---

## Postgres

If the site “won’t work” after wake, sometimes **Postgres** stopped or Docker did not resume. Check:

- Homebrew: `brew services list` → `postgresql@…` running  
- Docker: Docker Desktop running and `docker compose ps`

Then open http://localhost:3000 again.
