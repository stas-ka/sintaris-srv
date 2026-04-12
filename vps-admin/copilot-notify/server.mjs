#!/usr/bin/env node
/**
 * Sintaris Copilot Notify — MCP Server v2
 *
 * HTTP/SSE transport — runs persistently in Docker.
 * Provides bidirectional Telegram <-> Copilot communication with:
 *   - Unique correlation IDs per request (#reqId shown in every message)
 *   - Inline keyboard buttons for yes/no, options, new-task
 *   - reply_to_message routing
 *   - /help /status /cancel /task Telegram commands
 *   - Full-text results (auto-split for Telegram's 4096-char limit)
 *
 * MCP tools: tg_notify, tg_ask, tg_status, tg_complete
 * Docker: docker compose up -d
 * MCP config: { "url": "http://localhost:7340/sse" }
 */

import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import { z } from "zod";
import { createHmac, randomBytes } from "crypto";
import https from "https";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import os from "os";
import { EventEmitter } from "events";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ── Config ────────────────────────────────────────────────────────────────────

function loadEnv() {
  const cfg = {};
  const envFile = path.join(__dirname, ".env");
  if (fs.existsSync(envFile)) {
    for (const line of fs.readFileSync(envFile, "utf8").split("\n")) {
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
  `${os.hostname()}/${path.basename(process.env.COPILOT_PROJECT || process.env.PWD || process.cwd())}`;
const PORT = parseInt(CFG.NOTIFY_PORT || "7340", 10);
const STATE_DIR = CFG.STATE_DIR || os.tmpdir();
const STATE_FILE = path.join(STATE_DIR, "copilot-notify-state.json");

// ── Auth ──────────────────────────────────────────────────────────────────────

function hmac(secret, value) {
  return createHmac("sha256", secret).update(String(value)).digest("hex");
}

function verifyUserIdSig() {
  if (!NOTIFY_SECRET || !ALLOWED_USER_ID) return false;
  return hmac(NOTIFY_SECRET, ALLOWED_USER_ID) === ALLOWED_USER_ID_SIG;
}

function isAuthorized(userId) { return userId === ALLOWED_USER_ID; }

// ── Global state ──────────────────────────────────────────────────────────────

// reqEmitter: tg_ask/tg_complete promise resolvers subscribe here
const reqEmitter = new EventEmitter();
reqEmitter.setMaxListeners(200);

const state = {
  status:       "starting",
  lastUpdateId: 0,
  sessionCount: 0,
  // reqId -> { question, messageId, ts, answered, type, parentReqId? }
  pending:      {},
  // telegramMsgId -> reqId (for reply_to_message correlation)
  msgToReq:     {},
  // Last N status updates: [{ ts, text }]
  activityLog:  [],
};

const ACTIVITY_LOG_MAX = 10; // keep last 10 entries

function addActivity(text) {
  const ts = new Date().toISOString().slice(11, 16); // HH:MM UTC
  state.activityLog.unshift({ ts, text });
  if (state.activityLog.length > ACTIVITY_LOG_MAX) {
    state.activityLog.length = ACTIVITY_LOG_MAX;
  }
}

/** Build /status reply text — current status + recent activities (max 500 chars total) */
function buildStatusMessage() {
  const header = `Status: <b>${escHtml(state.status)}</b>`;
  if (state.activityLog.length === 0) return header;

  const lines = [];
  let used = header.length + 20; // reserve for "\n\nRecent:\n"
  for (const { ts, text } of state.activityLog) {
    const line = `• ${ts} ${escHtml(text)}`;
    if (used + line.length + 1 > 500) break;
    lines.push(line);
    used += line.length + 1;
  }
  if (lines.length === 0) return header;
  return `${header}\n\n<b>Recent:</b>\n${lines.join("\n")}`;
}

function loadPersistedState() {
  try {
    const s = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
    state.lastUpdateId = s.lastUpdateId || 0;
    if (Array.isArray(s.activityLog)) state.activityLog = s.activityLog;
  } catch (_) { /* fresh start */ }
}

function persistState() {
  try {
    fs.mkdirSync(STATE_DIR, { recursive: true });
    fs.writeFileSync(STATE_FILE,
      JSON.stringify({
        lastUpdateId: state.lastUpdateId,
        status: state.status,
        activityLog: state.activityLog,
      }, null, 2));
  } catch (e) { console.error("State persist:", e.message); }
}

// ── Telegram API ──────────────────────────────────────────────────────────────

async function tgCall(method, params) {
  const body = JSON.stringify(params || {});
  return new Promise((resolve, reject) => {
    const req = https.request({
      hostname: "api.telegram.org",
      path:     `/bot${BOT_TOKEN}/${method}`,
      method:   "POST",
      headers: {
        "Content-Type":   "application/json",
        "Content-Length": Buffer.byteLength(body),
      },
    }, (res) => {
      let data = "";
      res.on("data", (c) => { data += c; });
      res.on("end", () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`JSON parse: ${data.slice(0, 80)}`)); }
      });
    });
    req.on("error", reject);
    req.setTimeout(35000, () => req.destroy(new Error("timeout")));
    req.write(body);
    req.end();
  });
}

function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Split long text into <=4096-char parts on paragraph/line boundaries
function splitMsg(text, limit) {
  const max = limit || 4096;
  if (text.length <= max) return [text];
  const parts = [];
  let rem = text;
  while (rem.length > 0) {
    if (rem.length <= max) { parts.push(rem); break; }
    let cut = rem.lastIndexOf("\n\n", max);
    if (cut < max * 0.4) cut = rem.lastIndexOf("\n", max);
    if (cut < max * 0.4) cut = max;
    parts.push(rem.slice(0, cut));
    rem = rem.slice(cut).trimStart();
  }
  return parts;
}

// Send message, splitting if needed; keyboard only on last chunk
async function sendMsg(text, extra) {
  const parts = splitMsg(text);
  let lastRes;
  for (let i = 0; i < parts.length; i++) {
    const isLast = i === parts.length - 1;
    const params = Object.assign(
      { chat_id: ALLOWED_USER_ID, text: parts[i], parse_mode: "HTML", disable_web_page_preview: true },
      isLast && extra ? extra : {}
    );
    lastRes = await tgCall("sendMessage", params);
    if (!lastRes.ok) break;
  }
  return lastRes;
}

// Standard header for every message
function hdr(reqId) {
  const id = reqId ? ` <code>#${reqId}</code>` : "";
  return `<b>[${escHtml(INSTANCE_NAME)}]</b>${id}`;
}

// ── Inline keyboards ──────────────────────────────────────────────────────────

function kbYesNo(reqId) {
  return { inline_keyboard: [[
    { text: "Yes", callback_data: reqId + ":yes" },
    { text: "No",  callback_data: reqId + ":no"  },
    { text: "Skip", callback_data: reqId + ":skip" },
  ]] };
}

function kbOptions(reqId, opts) {
  const btns = opts.map((o) => ({ text: o, callback_data: reqId + ":" + o.slice(0, 50) }));
  const rows = [];
  for (let i = 0; i < btns.length; i += 2) rows.push(btns.slice(i, i + 2));
  rows.push([{ text: "Skip", callback_data: reqId + ":skip" }]);
  return { inline_keyboard: rows };
}

function kbComplete(reqId) {
  return { inline_keyboard: [[
    { text: "New task",  callback_data: reqId + ":new_task" },
    { text: "Status",    callback_data: "status:" },
  ]] };
}

function removeButtons(msgId) {
  if (!msgId) return;
  tgCall("editMessageReplyMarkup", {
    chat_id: ALLOWED_USER_ID, message_id: msgId,
    reply_markup: { inline_keyboard: [] },
  }).catch(() => {});
}

// ── Pending request helpers ───────────────────────────────────────────────────

function findPending(excludeType) {
  let latest = null, latestTs = 0;
  for (const [id, r] of Object.entries(state.pending)) {
    if (r.answered) continue;
    if (excludeType && r.type === excludeType) continue;
    if (r.ts > latestTs) { latestTs = r.ts; latest = id; }
  }
  return latest;
}

function findPendingOfType(type) {
  for (const [id, r] of Object.entries(state.pending)) {
    if (!r.answered && r.type === type) return id;
  }
  return null;
}

function resolveRequest(reqId, answer) {
  const req = state.pending[reqId];
  if (!req || req.answered) return false;
  req.answered = true;
  removeButtons(req.messageId);
  if (req.parentReqId) {
    reqEmitter.emit(req.parentReqId, answer);
  } else {
    reqEmitter.emit(reqId, answer);
  }
  return true;
}

function waitFor(reqId, ms) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => {
      reqEmitter.off(reqId, resolve);
      resolve("TIMEOUT");
    }, ms);
    reqEmitter.once(reqId, (val) => { clearTimeout(timer); resolve(val); });
  });
}

// ── Help text ─────────────────────────────────────────────────────────────────

const HELP_TEXT =
`<b>Sintaris Copilot Notify v2 — Command Guide</b>

<b>Status queries:</b>
/status — Show Copilot's current status and session info
/help   — This message

<b>Answering questions:</b>
Tap inline buttons (Yes/No/options) when shown.
Or: reply directly to the bot's question message.
Or: send <code>REQID your answer</code> (6-char ID in message header).
The latest unanswered question also accepts any free text.
To skip: /cancel or /cancel REQID

<b>Sending a new task to Copilot:</b>
Tap <b>New task</b> button on a completion message.
Or: /task Your full instructions here
Or: just send a message when Copilot is idle.

<b>Message IDs (#reqId):</b>
Every bot message shows a <code>#reqId</code> in the header.
When replying manually, include that ID for precise routing:
  abc123 My answer here

<b>Supported levels in tg_notify:</b>
info / warning / error / success`;

// ── Telegram update handler ───────────────────────────────────────────────────

async function handleUpdate(upd) {
  // Callback query (inline button press)
  if (upd.callback_query) {
    const cq = upd.callback_query;
    if (!isAuthorized(cq.from && cq.from.id)) {
      await tgCall("answerCallbackQuery", { callback_query_id: cq.id, text: "Unauthorized" });
      return;
    }
    await tgCall("answerCallbackQuery", { callback_query_id: cq.id });

    const data = cq.data || "";
    const sep = data.indexOf(":");
    const reqId = sep !== -1 ? data.slice(0, sep) : data;
    const choice = sep !== -1 ? data.slice(sep + 1) : "";

    if (reqId === "status") {
      await sendMsg(`${hdr("")}\n${buildStatusMessage()}`);
      return;
    }

    if (choice === "new_task") {
      const taskReqId = newReqId();
      state.pending[taskReqId] = {
        type: "task_input", parentReqId: reqId, ts: Date.now(), answered: false,
      };
      const res = await sendMsg(
        `${hdr(taskReqId)}\n\nSend your new task for Copilot.\n` +
        `<i>Reply to this message or send:\n` +
        `<code>${taskReqId} Your task here</code>\n` +
        `Or: /task Your task here</i>`
      );
      if (res && res.ok) state.msgToReq[res.result.message_id] = taskReqId;
      return;
    }

    const req = state.pending[reqId];
    if (!req || req.answered) return;
    resolveRequest(reqId, choice);
    await sendMsg(
      `${hdr(reqId)}\nAnswer for <code>#${reqId}</code>: <code>${escHtml(choice)}</code>`,
      req.messageId ? { reply_to_message_id: req.messageId } : {}
    );
    return;
  }

  // Text message
  const msg = upd.message;
  if (!msg || !msg.from || !isAuthorized(msg.from.id)) return;

  const text = (msg.text || "").trim();
  const replyTo = msg.reply_to_message && msg.reply_to_message.message_id;

  if (text === "/status") {
    await sendMsg(`${hdr("")}\n${buildStatusMessage()}`);
    return;
  }
  if (text === "/help") {
    await sendMsg(HELP_TEXT);
    return;
  }
  if (text.startsWith("/cancel")) {
    const parts = text.split(/\s+/);
    const id = parts[1] || findPending();
    const req = id ? state.pending[id] : null;
    if (req && !req.answered) {
      resolveRequest(id, "CANCELLED");
      await sendMsg(`${hdr(id)}\nRequest <code>#${id}</code> cancelled.`);
    } else {
      await sendMsg(`No pending request to cancel.`);
    }
    return;
  }
  if (text.startsWith("/task ")) {
    const task = text.slice(6).trim();
    const taskId = findPendingOfType("task_input") || findPendingOfType("new_task");
    if (taskId) {
      resolveRequest(taskId, task);
      await sendMsg(
        `${hdr(taskId)}\nNew task registered.`,
        { reply_to_message_id: msg.message_id }
      );
    } else {
      await sendMsg(`No pending task slot. Is Copilot active?`);
    }
    return;
  }

  // Correlation: reply_to_message
  if (replyTo && state.msgToReq[replyTo]) {
    const id = state.msgToReq[replyTo];
    if (resolveRequest(id, text)) {
      await sendMsg(
        `${hdr(id)}\nAnswer for <code>#${id}</code> recorded.`,
        { reply_to_message_id: msg.message_id }
      );
      return;
    }
  }

  // Correlation: explicit prefix "abc123 reply text"
  const m = text.match(/^([0-9a-f]{6})\s+([\s\S]+)/);
  if (m) {
    const id = m[1];
    const reply = m[2];
    if (resolveRequest(id, reply)) {
      await sendMsg(
        `${hdr(id)}\nAnswer recorded.`,
        { reply_to_message_id: msg.message_id }
      );
      return;
    }
  }

  // Fallback: most recent unanswered request
  const fallback = findPending();
  if (fallback && resolveRequest(fallback, text)) {
    await sendMsg(
      `${hdr(fallback)}\nAnswer for <code>#${fallback}</code> recorded.`,
      { reply_to_message_id: msg.message_id }
    );
    return;
  }

  await sendMsg(`${hdr("")}\nNo pending question. Send /help for usage.`);
}

// ── Telegram poll loop ────────────────────────────────────────────────────────

async function pollForever() {
  console.log("Telegram polling started…");
  while (true) {
    try {
      const res = await tgCall("getUpdates", {
        offset:          state.lastUpdateId + 1,
        timeout:         25,
        allowed_updates: ["message", "callback_query"],
      });
      if (res.ok) {
        for (const upd of res.result || []) {
          state.lastUpdateId = upd.update_id;
          persistState();
          handleUpdate(upd).catch((e) => console.error("handleUpdate:", e.message));
        }
      }
    } catch (e) {
      console.error("Poll error:", e.message);
      await new Promise((r) => setTimeout(r, 3000));
    }
  }
}

// ── MCP Server factory ────────────────────────────────────────────────────────

function newMcpServer() {
  const srv = new McpServer({ name: "copilot-notify", version: "2.0.0" });

  srv.tool(
    "tg_notify",
    "Send a Telegram notification (fire-and-forget). " +
    "Use at every pause, error, or significant milestone. " +
    "Full text is sent in its entirety — no need to truncate. " +
    "HTML supported: <b>, <i>, <code>.",
    {
      message: z.string().describe("Full notification text (auto-split if >4096 chars)"),
      level:   z.enum(["info", "warning", "error", "success"]).optional()
               .describe("Severity level: info (default), warning, error, success"),
    },
    async ({ message, level }) => {
      const lvl = level || "info";
      const icons = { info: "ℹ️", warning: "⚠️", error: "🔴", success: "✅" };
      const reqId = newReqId();
      const text = icons[lvl] + " " + hdr(reqId) + "\n\n" + message;
      const res = await sendMsg(text);
      if (res && res.ok) state.msgToReq[res.result.message_id] = reqId;
      return {
        content: [{ type: "text", text: res && res.ok ? "Sent #" + reqId : "Error: " + (res && res.description) }],
      };
    }
  );

  srv.tool(
    "tg_ask",
    "Ask user a question via Telegram and WAIT for their reply. " +
    "Copilot session pauses until the user responds or timeout expires. " +
    "Use options=['Yes','No'] for yes/no confirmation with inline buttons. " +
    "Returns user reply text, TIMEOUT, or CANCELLED.",
    {
      question:    z.string().describe("The question or prompt to display to the user"),
      options:     z.array(z.string()).optional()
                   .describe("Inline button choices. ['Yes','No'] shows yes/no/skip buttons."),
      timeout_sec: z.number().optional()
                   .describe("Seconds to wait for a reply (default: 120, max: 600)"),
    },
    async ({ question, options, timeout_sec }) => {
      const timeout = Math.min(timeout_sec || 120, 600);
      const reqId = newReqId();
      state.pending[reqId] = { type: "question", ts: Date.now(), answered: false };
      addActivity("❓ Asked: " + question.slice(0, 70));
      state.status = "waiting #" + reqId + ": " + question.slice(0, 50);

      const isYesNo = options && options.length === 2 &&
        options[0].toLowerCase() === "yes" && options[1].toLowerCase() === "no";
      const keyboard = isYesNo ? kbYesNo(reqId)
                     : (options && options.length) ? kbOptions(reqId, options)
                     : null;
      const replyHint = keyboard ? ""
        : "\n\n<i>Reply to this message, or send: <code>" + reqId + " your answer</code></i>";

      const text =
        "❓ " + hdr(reqId) + "\n\n" + escHtml(question) + replyHint +
        "\n\n<i>Timeout: " + timeout + "s · /cancel " + reqId + "</i>";

      const res = await sendMsg(text, keyboard ? { reply_markup: keyboard } : {});
      if (res && res.ok) {
        state.pending[reqId].messageId = res.result.message_id;
        state.msgToReq[res.result.message_id] = reqId;
      }

      const reply = await waitFor(reqId, timeout * 1000);
      state.status = "running";
      delete state.pending[reqId];

      if (reply === "TIMEOUT") {
        await sendMsg("⏰ " + hdr(reqId) + "\nNo reply after " + timeout + "s — continuing.");
        return { content: [{ type: "text", text: "TIMEOUT: No reply after " + timeout + "s." }] };
      }
      if (reply === "CANCELLED") {
        return { content: [{ type: "text", text: "CANCELLED: User skipped this question." }] };
      }
      return { content: [{ type: "text", text: reply }] };
    }
  );

  srv.tool(
    "tg_status",
    "Update the status shown when user sends /status to the bot. " +
    "Call at the start of each major work phase.",
    {
      status: z.string().describe("Human-readable current activity description"),
    },
    async ({ status }) => {
      addActivity(status);
      state.status = status;
      persistState();
      return { content: [{ type: "text", text: "Status: " + status }] };
    }
  );

  srv.tool(
    "tg_complete",
    "Send FULL task results to the user via Telegram and signal completion. " +
    "Pass the complete output text — it will be split automatically if too long. " +
    "Set wait_for_task=true to show a 'New task' button and wait up to 5 minutes.",
    {
      summary:       z.string().describe("Complete results / summary text — sent in full, no truncation"),
      wait_for_task: z.boolean().optional()
                     .describe("Show 'New task' button and wait for next instruction (default: false)"),
    },
    async ({ summary, wait_for_task }) => {
      const reqId = newReqId();
      addActivity("✅ Task complete: " + summary.slice(0, 80).replace(/\n/g, " "));
      state.status = "idle — task complete";
      persistState();

      const body = "✅ " + hdr(reqId) + " Task complete!\n\n" + escHtml(summary);
      const extra = wait_for_task ? { reply_markup: kbComplete(reqId) } : {};
      const res = await sendMsg(
        body + (wait_for_task ? "\n\n<i>Tap New task or send /task Your instructions here</i>" : ""),
        extra
      );
      if (res && res.ok) state.msgToReq[res.result.message_id] = reqId;

      if (!wait_for_task) {
        return { content: [{ type: "text", text: "Results sent #" + reqId + "." }] };
      }

      state.pending[reqId] = { type: "new_task", ts: Date.now(), answered: false };
      const newTask = await waitFor(reqId, 300000);
      delete state.pending[reqId];

      if (newTask === "TIMEOUT") {
        return { content: [{ type: "text", text: "No new task received within 5 minutes." }] };
      }
      state.status = "running: " + newTask.slice(0, 60);
      return { content: [{ type: "text", text: "New task: " + newTask }] };
    }
  );

  return srv;
}

function newReqId() { return randomBytes(3).toString("hex"); }

// ── HTTP + SSE server ─────────────────────────────────────────────────────────

const app = express();
app.use(express.json());

const sessions = {};  // sessionId -> { transport, server }

app.get("/health", (_req, res) => {
  const pending = Object.values(state.pending).filter((r) => !r.answered).length;
  res.json({
    ok: true,
    instance: INSTANCE_NAME,
    status: state.status,
    activeSessions: Object.keys(sessions).length,
    pendingRequests: pending,
  });
});

app.get("/sse", async (req, res) => {
  const srv = newMcpServer();
  const transport = new SSEServerTransport("/messages", res);
  sessions[transport.sessionId] = { transport, server: srv };
  state.sessionCount++;
  state.status = "connected (session #" + state.sessionCount + ")";

  res.on("close", () => {
    delete sessions[transport.sessionId];
    if (Object.keys(sessions).length === 0) state.status = "idle — no active session";
  });

  await srv.connect(transport);
});

app.post("/messages", async (req, res) => {
  const sessionId = req.query.sessionId;
  const session = sessions[sessionId];
  if (!session) return res.status(404).json({ error: "Session not found" });
  await session.transport.handlePostMessage(req, res, req.body);
});

// ── Startup ───────────────────────────────────────────────────────────────────

if (!BOT_TOKEN) {
  console.error("ERROR: NOTIFY_BOT_TOKEN not set in .env");
  process.exit(1);
}
if (!verifyUserIdSig()) {
  console.error("ERROR: ALLOWED_USER_ID signature invalid.");
  console.error("Run: node setup.mjs --set-user-id " + (ALLOWED_USER_ID || "<user_id>"));
  process.exit(1);
}

loadPersistedState();

app.listen(PORT, "0.0.0.0", () => {
  console.log("Copilot Notify v2 — " + INSTANCE_NAME);
  console.log("HTTP:  http://0.0.0.0:" + PORT);
  console.log("MCP:   http://localhost:" + PORT + "/sse");
  console.log("Auth:  user " + ALLOWED_USER_ID + " (HMAC verified)");
  state.status = "ready";
  persistState();
  pollForever().catch((e) => { console.error("Poll fatal:", e); process.exit(1); });
});
