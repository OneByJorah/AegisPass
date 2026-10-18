// Captures real screenshots of the running demo stack with Playwright.
// Usage (stack already running):  BASE_URL=http://127.0.0.1:8000 node scripts/screenshots.mjs
// Requires: npm install --no-save playwright && npx playwright install chromium
//
// Safety: every page is scanned for private IPs, tailnet IPs, emails, and forbidden words
// BEFORE a screenshot is written. If anything matches, the script exits 1 and saves nothing.
// Extra patterns: SCRUB_PATTERNS="mycompany,internal-host" (comma-separated regexes).

import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const OUT = process.env.OUT_DIR || "docs/screenshots";
const RECORD = process.env.RECORD === "1";
const DEMO_USER = process.env.DEMO_USERNAME || "demo.user";
const DEMO_PASS = process.env.DEMO_PASSWORD || "demo";

// Edit this list per project: one entry per meaningful screen worth showing.
const PAGES = [
  { name: "login", path: "/login", waitFor: ".auth-title" },
  { name: "dashboard", path: "/app#dashboard", waitFor: "#deviceBox .num", login: true },
];

const FORBIDDEN = [
  { label: "private IPv4", re: /\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b/ },
  { label: "tailnet IPv4", re: /\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b/ },
  { label: "email address", re: /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i },
  { label: "school domain", re: /\bk12\.vi\b/i },
  ...(process.env.SCRUB_PATTERNS || "")
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => ({ label: `custom:${p}`, re: new RegExp(p, "i") })),
];

fs.mkdirSync(OUT, { recursive: true });
const videoDir = path.join("tmp", "videos");
if (RECORD) fs.mkdirSync(videoDir, { recursive: true });

async function login(page) {
  await page.goto(new URL("/login", BASE).toString(), { waitUntil: "networkidle" });
  await page.waitForSelector("#username", { timeout: 15000 });
  await page.fill("#username", DEMO_USER);
  await page.fill("#password", DEMO_PASS);
  await page.click("#login");
  // Wait for the SPA shell to load after the JSON login response.
  await page.waitForURL(/\/app/, { timeout: 15000 });
  await page.waitForSelector("#app", { timeout: 15000 });
}

async function captureOne(context, suffix = "") {
  let failed = false;
  for (const p of PAGES) {
    const page = await context.newPage();
    if (p.login) {
      await login(page);
      // After login, navigate to the requested view in the same session.
      await page.goto(new URL(p.path, BASE).toString(), { waitUntil: "networkidle" });
    } else {
      await page.goto(new URL(p.path, BASE).toString(), { waitUntil: "networkidle" });
    }
    if (p.waitFor) {
      await page.waitForSelector(p.waitFor, { timeout: 15000 });
    }
    // Let any in-flight dashboard data settle.
    await page.waitForTimeout(500);

    const text = (await page.evaluate(() => document.body.innerText)) + "\n" + (await page.title());
    const hits = FORBIDDEN.filter((f) => f.re.test(text)).map((f) => f.label);
    if (hits.length) {
      console.error(`SCRUB FAIL on ${p.name}${suffix}: found ${hits.join(", ")}. No screenshot written.`);
      failed = true;
      await page.close();
      continue;
    }

    const file = path.join(OUT, `${p.name}${suffix}.png`);
    await page.screenshot({ path: file, fullPage: true });
    console.log(`saved ${file}`);
    await page.close();
  }
  return failed;
}

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: process.env.NO_SANDBOX === "1" ? ["--no-sandbox"] : [],
});

// Desktop captures at 1440x900 @2x, dark colour scheme.
const desktopContext = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: "dark",
  ...(RECORD ? { recordVideo: { dir: videoDir, size: { width: 1280, height: 720 } } } : {}),
});
let failed = await captureOne(desktopContext, "");
await desktopContext.close();

// Mobile captures of the login/reset portal.
const mobileContext = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 2,
  colorScheme: "dark",
  userAgent:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
});
failed = (await captureOne(mobileContext, "-mobile")) || failed;
await mobileContext.close();

await browser.close();

if (RECORD && !failed) {
  const vids = fs.readdirSync(videoDir).filter((f) => f.endsWith(".webm")).sort();
  if (vids.length) {
    const src = path.join(videoDir, vids[vids.length - 1]);
    const dst = path.join(OUT, "demo.gif");
    const r = spawnSync(
      "ffmpeg",
      ["-y", "-i", src, "-vf", "fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", dst],
      { stdio: "inherit" },
    );
    if (r.status === 0) console.log(`saved ${dst}`);
  }
}

process.exit(failed ? 1 : 0);
