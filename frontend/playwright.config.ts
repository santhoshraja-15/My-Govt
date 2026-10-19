import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against a REAL stack: FastAPI + a disposable PostgreSQL database
 * (mygovt_test_e2e, created by `python -m scripts.e2e_env`) + the production Next.js build.
 *
 * Required environment:
 *   E2E_PG_PORT / E2E_PG_HOST / E2E_PG_USER   connection to a disposable PostgreSQL server
 * Optional: E2E_ADMIN_PASSWORD (fixture credential for the throw-away database)
 */
const API_PORT = 8010;
const WEB_PORT = 3010;
const pgHost = process.env.E2E_PG_HOST ?? "localhost";
const pgPort = process.env.E2E_PG_PORT ?? "5432";
const pgUser = process.env.E2E_PG_USER ?? "postgres";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,         // tests share one database
  workers: 1,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "./e2e/results.json" }]],
  use: { baseURL: `http://localhost:${WEB_PORT}`, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `python -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../backend",
      url: `http://localhost:${API_PORT}/api/v1/public/stats`,
      timeout: 60_000,
      reuseExistingServer: false,
      env: {
        APP_ENV: "development",
        POSTGRES_HOST: pgHost, POSTGRES_PORT: pgPort, POSTGRES_USER: pgUser,
        POSTGRES_PASSWORD: process.env.E2E_PG_PASSWORD ?? "",
        POSTGRES_DB: "mygovt_test_e2e",
        APP_CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
        FEATURE_GRAPH: "false",
        RATE_LIMIT_REGISTER_PER_HOUR: "1000", RATE_LIMIT_LOGIN_PER_MIN: "1000", RATE_LIMIT_CHAT_PER_MIN: "1000",
        PYTHONIOENCODING: "utf-8",
      },
    },
    {
      command: `npx next start -p ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}`,
      timeout: 60_000,
      reuseExistingServer: false,
      env: { NEXT_PUBLIC_API_URL: `http://localhost:${API_PORT}`, NEXT_TELEMETRY_DISABLED: "1" },
    },
  ],
});
