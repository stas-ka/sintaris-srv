#!/usr/bin/env node
/**
 * Sintaris Copilot Notify — Setup Script
 *
 * Usage:
 *   node setup.mjs                         # Interactive first-time setup
 *   node setup.mjs --set-user-id <id>      # Change authorized Telegram user ID
 *   node setup.mjs --verify                # Verify current config is valid
 */

import { createHmac, randomBytes } from "crypto";
import { readFileSync, writeFileSync, existsSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { createInterface } from "readline";
import https from "https";
import os from "os";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ENV_FILE = path.join(__dirname, ".env");

// ── Helpers ───────────────────────────────────────────────────────────────────

function hmac(secret, value) {
  return createHmac("sha256", secret).update(String(value)).digest("hex");
}

function loadEnv() {
  if (!existsSync(ENV_FILE)) return {};
  const cfg = {};
  for (const line of readFileSync(ENV_FILE, "utf8").split("\n")) {
    const t = line.trim();
    if (t && !t.startsWith("#") && t.includes("=")) {
      const [k, ...v] = t.split("=");
      cfg[k.trim()] = v.join("=").trim().replace(/^["']|["']$/g, "");
    }
  }
  return cfg;
}

function writeEnv(cfg) {
  const lines = Object.entries(cfg).map(([k, v]) => `${k}=${v}`);
  writeFileSync(ENV_FILE, lines.join("\n") + "\n", { mode: 0o600 });
  console.log(`✅ Config written to ${ENV_FILE} (mode 600)`);
}

async function tgGetMe(token) {
  return new Promise((resolve, reject) => {
    https.get(`https://api.telegram.org/bot${token}/getMe`, (res) => {
      let d = "";
      res.on("data", (c) => { d += c; });
      res.on("end", () => {
        try { resolve(JSON.parse(d)); }
        catch (e) { reject(e); }
      });
    }).on("error", reject);
  });
}

function prompt(rl, question) {
  return new Promise((r) => rl.question(question, r));
}

// ── CLI dispatch ──────────────────────────────────────────────────────────────

const args = process.argv.slice(2);

if (args[0] === "--verify") {
  const cfg = loadEnv();
  if (!cfg.NOTIFY_SECRET || !cfg.ALLOWED_USER_ID || !cfg.ALLOWED_USER_ID_SIG) {
    console.error("❌ Missing required keys. Run node setup.mjs first.");
    process.exit(1);
  }
  const expected = hmac(cfg.NOTIFY_SECRET, cfg.ALLOWED_USER_ID);
  if (expected !== cfg.ALLOWED_USER_ID_SIG) {
    console.error("❌ ALLOWED_USER_ID_SIG is INVALID — ID may have been tampered with.");
    process.exit(1);
  }
  console.log(`✅ User ID ${cfg.ALLOWED_USER_ID} signature is valid.`);
  console.log(`   Instance: ${cfg.INSTANCE_NAME || "(auto)"}`);
  console.log(`   Token ends with: ...${cfg.NOTIFY_BOT_TOKEN?.slice(-8) || "?"}`);
  process.exit(0);
}

if (args[0] === "--set-user-id") {
  const newId = args[1];
  if (!newId || isNaN(parseInt(newId, 10))) {
    console.error("Usage: node setup.mjs --set-user-id <telegram_user_id>");
    process.exit(1);
  }
  const cfg = loadEnv();
  if (!cfg.NOTIFY_SECRET) {
    console.error("❌ No NOTIFY_SECRET found. Run node setup.mjs first.");
    process.exit(1);
  }
  cfg.ALLOWED_USER_ID = newId;
  cfg.ALLOWED_USER_ID_SIG = hmac(cfg.NOTIFY_SECRET, newId);
  writeEnv(cfg);
  console.log(`✅ Authorized user ID changed to ${newId} and re-signed.`);
  process.exit(0);
}

// ── Interactive setup ─────────────────────────────────────────────────────────

console.log("╔═══════════════════════════════════════╗");
console.log("║  Sintaris Copilot Notify — Setup      ║");
console.log("╚═══════════════════════════════════════╝\n");

const existing = loadEnv();
const rl = createInterface({ input: process.stdin, output: process.stdout });

const token = await prompt(rl,
  `Bot token [${existing.NOTIFY_BOT_TOKEN ? "keep existing" : "required"}]: `
) || existing.NOTIFY_BOT_TOKEN;

if (!token) {
  console.error("❌ Bot token is required.");
  rl.close();
  process.exit(1);
}

// Validate token
process.stdout.write("Verifying token with Telegram… ");
let botName = "?";
try {
  const me = await tgGetMe(token);
  if (!me.ok) throw new Error(me.description);
  botName = me.result.username;
  console.log(`✅  @${botName}`);
} catch (e) {
  console.error(`\n❌ Token invalid: ${e.message}`);
  rl.close();
  process.exit(1);
}

const userId = await prompt(rl,
  `Authorized Telegram user ID [${existing.ALLOWED_USER_ID || "required"}]: `
) || existing.ALLOWED_USER_ID;

if (!userId || isNaN(parseInt(userId, 10))) {
  console.error("❌ User ID is required and must be numeric.");
  rl.close();
  process.exit(1);
}

const defaultInstance = `${os.hostname()}/${path.basename(process.env.PWD || process.cwd())}`;
const instanceName = await prompt(rl,
  `Instance name [${existing.INSTANCE_NAME || defaultInstance}]: `
) || existing.INSTANCE_NAME || defaultInstance;

rl.close();

// Generate or reuse secret
const secret = existing.NOTIFY_SECRET || randomBytes(32).toString("hex");
const sig = hmac(secret, userId);

const cfg = {
  NOTIFY_BOT_TOKEN: token,
  ALLOWED_USER_ID: userId,
  ALLOWED_USER_ID_SIG: sig,
  NOTIFY_SECRET: secret,
  INSTANCE_NAME: instanceName,
};

writeEnv(cfg);

console.log("\n📋 Configuration summary:");
console.log(`   Bot:       @${botName}`);
console.log(`   User ID:   ${userId} (HMAC-signed)`);
console.log(`   Instance:  ${instanceName}`);
console.log(`   Secret:    ${secret.slice(0, 8)}… (keep this safe!)`);
console.log("\n✅ Setup complete. Test with: node server.mjs");
console.log("   Then add to ~/.copilot/mcp-config.json (see README.md)");
