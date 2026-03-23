#!/usr/bin/env node
/**
 * OpenClaw MCP Server
 * Exposes the local OpenClaw gateway as MCP tools for GitHub Copilot CLI.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { execFile } from "child_process";
import { promisify } from "util";

const execFileAsync = promisify(execFile);
const OPENCLAW_BIN = process.env.OPENCLAW_BIN || "/home/stas/.local/bin/openclaw";

const server = new McpServer({
  name: "openclaw",
  version: "1.0.0",
});

// Tool: send a message to OpenClaw agent and get a response
server.tool(
  "openclaw_agent",
  "Send a message to the OpenClaw AI agent and get a response. Use this for tasks, questions, or commands that OpenClaw can handle.",
  {
    message: z.string().describe("The message or task to send to the OpenClaw agent"),
    session: z.string().optional().describe("Optional session key (e.g. agent:main:main)"),
  },
  async ({ message, session }) => {
    const args = ["agent", "--message", message, "--json"];
    if (session) {
      args.push("--session-id", session);
    }
    try {
      const { stdout, stderr } = await execFileAsync(OPENCLAW_BIN, args, {
        timeout: 120000,
        env: { ...process.env, OPENCLAW_NO_RESPAWN: "1" },
      });
      let result = stdout.trim();
      try {
        const parsed = JSON.parse(result);
        result = parsed.text || parsed.content || parsed.reply || JSON.stringify(parsed, null, 2);
      } catch {
        // not JSON, use as-is
      }
      return {
        content: [{ type: "text", text: result || "(no response)" }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Error: ${err.message}\n${err.stderr || ""}` }],
        isError: true,
      };
    }
  }
);

// Tool: check OpenClaw gateway health
server.tool(
  "openclaw_health",
  "Check the status and health of the OpenClaw gateway and connected channels.",
  {},
  async () => {
    try {
      const { stdout } = await execFileAsync(OPENCLAW_BIN, ["health"], {
        timeout: 15000,
        env: { ...process.env, OPENCLAW_NO_RESPAWN: "1" },
      });
      return {
        content: [{ type: "text", text: stdout.trim() }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// Tool: send a message to a Telegram user via OpenClaw
server.tool(
  "openclaw_message",
  "Send a message to a Telegram user or chat via the OpenClaw gateway.",
  {
    to: z.string().describe("Recipient: Telegram user ID, phone number, or @username"),
    text: z.string().describe("Message text to send"),
    channel: z.string().optional().default("telegram").describe("Channel to use (default: telegram)"),
  },
  async ({ to, text, channel }) => {
    try {
      const { stdout } = await execFileAsync(
        OPENCLAW_BIN,
        ["message", "send", "--to", to, "--text", text, "--channel", channel || "telegram"],
        {
          timeout: 15000,
          env: { ...process.env, OPENCLAW_NO_RESPAWN: "1" },
        }
      );
      return {
        content: [{ type: "text", text: stdout.trim() || "Message sent." }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
