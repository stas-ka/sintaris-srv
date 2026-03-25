#!/usr/bin/env node
/**
 * Sintaris Copilot Notify — MCP Server
 *
 * Provides Telegram notification + bidirectional communication tools
 * for GitHub Copilot CLI sessions.
 *
 * Tools:
 *   tg_notify  — send one-way notification
 *   tg_ask     — ask user question, wait for reply
 *   tg_status  — update current status
 *   tg_complete — signal task done, optionally wait for new task
 *
 * Security: authorized user ID is HMAC-signed (tamper-proof, changeable)
 * Config: ./env file (never committed)
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { createHmac, randomBytes } from "crypto";
import https from "https";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import os from "os";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ENV_FILE = path.join(__dirname, ".env");

// ── Config ────────────────────────────────────────────────────────────────────

function loadEnv() {
  const cfg = {};
  if (fs.existsSync(ENV_FILE)) {
    for (const line of fs.readFileSync(ENV_FILE, "utf8").split("\n")) {
      const t = line.trim();
      if (t && !t.startsWith("#") && t.includes("=")) {
        const [k, ...v] = t.split("=");
        cfg[k.trim()] = v.join("=").trim().replace(/^["']|["']$/g, "");
      }
    }
  }
  return { ...cfg, ...process.env };
}

const CFG = loadEnv();
const BOT_TOKEN = CFG.NOTIFY_BOT_TOKEN || CFG.BOT_TOKEN;
const ALLOWED_USER_ID = parseInt(CFG.ALLOWED_USER_ID || "0", 10);
const ALLOWED_USER_ID_SIG = CFG.ALLOWED_USER_ID_SIG || "";
const NOTIFY_SECRET = CFG.NOTIFY_SECRET || "";
const INSTANCE_NAME = CFG.INSTANCE_NAME ||
  `${os.hostname()}/${path.basename(process.env.PWD || process.cwd())}`;

// ── Auth ─────────────────────────────────────────────────────────────────────

function hmac(secret, value) {
  return createHmac("sha256", secret).update(String(value)).digest("hex");
}

function verifyUserIdSig() {
  if (!NOTIFY_SECRET || !ALLOWED_USER_ID) return false;
  return hmac(NOTIFY_SECRET, ALLOWED_USER_ID) === ALLOWED_USER_ID_SIG;
}

function isAuthorized(userId) {
  return userId === ALLOWED_USER_ID;
}

// ── State (persisted in /tmp) ─────────────────────────────────────────────────

const STATE_FILE = path.join(
  os.tmpdir(),
  `copilot-notify-${INSTANCE_NAME.replace(/[^a-z0-9]/gi, "_")}.json`
);

function loadState() {
  try { return JSON.parse(fs.readFileSync(STATE_FILE, "utf8")); }
  catch { return { lastUpdateId: 0, status: "idle", sessionId: null }; }
}

function saveState(patch) {
  const s = { ...loadState(), ...patch };
  fs.writeFileSync(STATE_FILE, JSON.stringify(s, null, 2));
  return s;
}

// ── Telegram API ──────────────────────────────────────────────────────────────

async function tgCall(method, params = {}) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(params);
    const req = https.request({
      hostname: "api.telegram.org",
      path: `/bot${BOT_TOKEN}/${method}`,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(body),
      },
    }, (res) => {
      let data = "";
      res.on("data", (c) => { data += c; });
      res.on("end", () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`JSON parse error: ${data}`)); }
      });
    });
    req.on("error", reject);
    req.setTimeout(35000, () => { req.destroy(new Error("Request timeout")); });
    req.write(body);
    req.end();
  });
}

async function sendMsg(text, extra = {}) {
  return tgCall("sendMessage", {
    chat_id: ALLOWED_USER_ID,
    text,
    parse_mode: "HTML",
    disable_web_page_preview: true,
    ...extra,
  });
}

// Long-poll Telegram, return when non-command message arrives or timeout
async function pollForReply(timeoutSec = 120) {
  const deadline = Date.now() + timeoutSec * 1000;
  let { lastUpdateId } = loadState();
  let offset = lastUpdateId + 1;

  while (Date.now() < deadline) {
    const remaining = Math.max(1, Math.floor((deadline - Date.now()) / 1000));
    const pollSec = Math.min(25, remaining);

    try {
      const res = await tgCall("getUpdates", {
        offset,
        timeout: pollSec,
        allowed_updates: ["message"],
      });

      if (!res.ok) {
        await sleep(2000);
        continue;
      }

      for (const update of res.result || []) {
        offset = update.update_id + 1;
        saveState({ lastUpdateId: update.update_id });

        const msg = update.message;
        if (!msg?.from) continue;
        if (!isAuthorized(msg.from.id)) {
          // Silently skip unauthorized
          continue;
        }

        const text = (msg.text || "").trim();

        // /status command — answer and keep polling
        if (text.startsWith("/status")) {
          const s = loadState();
          await sendMsg(
            `📊 <b>[${INSTANCE_NAME}]</b>\n` +
            `Status: <b>${escHtml(s.status)}</b>\n` +
            `Session: <code>${s.sessionId || "none"}</code>`
          );
          continue;
        }

        // /cancel — abort the wait
        if (text.startsWith("/cancel")) {
          return { reply: null, cancelled: true, timedOut: false };
        }

        // Any other text = user reply
        return { reply: text, cancelled: false, timedOut: false };
      }
    } catch (e) {
      // Transient network error
      await sleep(3000);
    }
  }

  return { reply: null, cancelled: false, timedOut: true };
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

function escHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function header(emoji) {
  const { sessionId } = loadState();
  return `${emoji} <b>[${escHtml(INSTANCE_NAME)}]</b>` +
    (sessionId ? ` <code>#${sessionId}</code>` : "");
}

// ── Startup checks ────────────────────────────────────────────────────────────

if (!BOT_TOKEN) {
  process.stderr.write("ERROR: NOTIFY_BOT_TOKEN not set in .env\n");
  process.exit(1);
}

if (!verifyUserIdSig()) {
  process.stderr.write(
    `ERROR: ALLOWED_USER_ID signature is invalid.\n` +
    `Run: node setup.mjs --set-user-id ${ALLOWED_USER_ID || "<user_id>"}\n`
  );
  process.exit(1);
}

// Init session state
const sessionId = randomBytes(4).toString("hex");
saveState({ status: "connecting", sessionId });

// ── MCP Server ────────────────────────────────────────────────────────────────

const server = new McpServer({ name: "copilot-notify", version: "1.0.0" });

// ── Tool: tg_notify ───────────────────────────────────────────────────────────
server.tool(
  "tg_notify",
  "Send a Telegram notification to the user (fire-and-forget). " +
  "Use when pausing for input, reporting progress, or signalling issues. " +
  "HTML supported: <b>, <i>, <code>.",
  {
    message: z.string().describe("Notification message text"),
    level: z.enum(["info", "warning", "error", "success"])
      .optional()
      .describe("Notification level (default: info)"),
  },
  async ({ message, level = "info" }) => {
    const icons = { info: "ℹ️", warning: "⚠️", error: "🔴", success: "✅" };
    const icon = icons[level] ?? "ℹ️";
    const res = await sendMsg(`${icon} ${header("")}\n\n${message}`);
    return {
      content: [{
        type: "text",
        text: res.ok ? "Notification sent." : `Telegram error: ${res.description}`,
      }],
    };
  }
);

// ── Tool: tg_ask ──────────────────────────────────────────────────────────────
server.tool(
  "tg_ask",
  "Send a question to the user via Telegram and WAIT for their reply. " +
  "The Copilot session is paused until the user responds or the timeout expires. " +
  "Returns the user's reply text, or TIMEOUT if no reply arrived.",
  {
    question: z.string().describe("The question or prompt to show the user"),
    timeout_sec: z.number()
      .optional()
      .describe("How long to wait for a reply in seconds (default: 120, max: 600)"),
  },
  async ({ question, timeout_sec = 120 }) => {
    const timeout = Math.min(timeout_sec, 600);
    saveState({ status: `⏳ waiting: ${question.slice(0, 60)}` });

    await sendMsg(
      `❓ ${header("")}\n\n${escHtml(question)}\n\n` +
      `<i>Reply to continue · timeout ${timeout}s · /cancel to skip</i>`
    );

    const { reply, timedOut, cancelled } = await pollForReply(timeout);
    saveState({ status: "running" });

    if (cancelled) {
      await sendMsg(`↩️ ${header("")}\nQuestion skipped via /cancel.`);
      return { content: [{ type: "text", text: "CANCELLED: User skipped the question." }] };
    }
    if (timedOut) {
      await sendMsg(`⏰ ${header("")}\nNo reply after ${timeout}s — continuing.`);
      return { content: [{ type: "text", text: `TIMEOUT: No user reply after ${timeout}s.` }] };
    }
    return { content: [{ type: "text", text: reply }] };
  }
);

// ── Tool: tg_status ───────────────────────────────────────────────────────────
server.tool(
  "tg_status",
  "Update the current status shown when the user sends /status to the bot. " +
  "Call this when starting significant work phases.",
  {
    status: z.string().describe("Human-readable current status description"),
  },
  async ({ status }) => {
    saveState({ status });
    return { content: [{ type: "text", text: `Status set: ${status}` }] };
  }
);

// ── Tool: tg_complete ─────────────────────────────────────────────────────────
server.tool(
  "tg_complete",
  "Notify user that all tasks are complete. " +
  "Optionally wait for the user to send a new task via Telegram.",
  {
    summary: z.string().describe("What was accomplished"),
    wait_for_task: z.boolean()
      .optional()
      .describe("If true, wait up to 5 minutes for user to send a new task via Telegram"),
  },
  async ({ summary, wait_for_task = false }) => {
    saveState({ status: "idle — task complete" });

    const prompt = wait_for_task
      ? "\n\n💬 <i>Send me a new task to continue, or /status to check state.</i>"
      : "";

    await sendMsg(`✅ ${header("")} Done!\n\n${escHtml(summary)}${prompt}`);

    if (!wait_for_task) {
      return { content: [{ type: "text", text: "Task complete notification sent." }] };
    }

    const { reply, timedOut, cancelled } = await pollForReply(300);
    if (!timedOut && !cancelled && reply) {
      saveState({ status: `running: ${reply.slice(0, 60)}` });
      return { content: [{ type: "text", text: `New task from user: ${reply}` }] };
    }
    return { content: [{ type: "text", text: "No new task received within 5 minutes." }] };
  }
);

// ── Start ─────────────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
saveState({ status: "connected" });
