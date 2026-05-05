/**
 * PM2 process file — keeps Next.js dev server alive across crashes and (with `pm2 startup`)
 * brings it back after reboot. Does NOT run while the laptop is fully off or asleep.
 *
 * Usage (from repo root or apps/web):
 *   cd apps/web && npx pm2 start ecosystem.config.cjs
 *   npx pm2 logs investbest-web
 *   npx pm2 stop investbest-web
 *
 * One-time so PM2 respawns after login:
 *   npx pm2 save
 *   npx pm2 startup   # follow the printed command
 */
module.exports = {
  apps: [
    {
      name: "investbest-web",
      cwd: __dirname,
      script: "npm",
      args: "run dev",
      interpreter: "none",
      autorestart: true,
      max_restarts: 50,
      min_uptime: "10s",
      exp_backoff_restart_delay: 2000,
      watch: false,
      env: {
        NODE_ENV: "development",
      },
    },
  ],
};
