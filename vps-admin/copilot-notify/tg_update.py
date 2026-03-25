#!/usr/bin/env python3
"""
Helper: call tg_status or tg_notify via copilot-notify MCP (keeps SSE alive).
Usage:
  tg_update.py status "Working on X"
  tg_update.py notify "Done: ..." [info|success|warning|error]
  tg_update.py ask "Question?" "Yes,No"
"""
import sys, threading, time, json, urllib.request

BASE = "http://localhost:7340"
session_id = None
sse_running = True

def sse_keep_alive():
    global session_id
    req = urllib.request.Request(f"{BASE}/sse")
    with urllib.request.urlopen(req, timeout=60) as r:
        for raw in r:
            if not sse_running: break
            line = raw.decode().strip()
            if line.startswith("data:") and "sessionId=" in line:
                session_id = line.split("sessionId=")[1].split("&")[0]

t = threading.Thread(target=sse_keep_alive, daemon=True)
t.start()
for _ in range(40):
    if session_id: break
    time.sleep(0.25)
if not session_id:
    print("ERROR: no sessionId", file=sys.stderr); sys.exit(1)

def call_tool(name, args):
    payload = json.dumps({
        "jsonrpc":"2.0","id":1,"method":"tools/call",
        "params":{"name":name,"arguments":args}
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/messages?sessionId={session_id}",
        data=payload, headers={"Content-Type":"application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.request.HTTPError as e:
        return e.code, e.read().decode()

cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
arg1 = sys.argv[2] if len(sys.argv) > 2 else ""
arg2 = sys.argv[3] if len(sys.argv) > 3 else ""

if cmd == "status":
    s, b = call_tool("tg_status", {"status": arg1})
elif cmd == "notify":
    s, b = call_tool("tg_notify", {"message": arg1, "level": arg2 or "info"})
elif cmd == "ask":
    opts = [o.strip() for o in arg2.split(",")] if arg2 else None
    args = {"question": arg1}
    if opts: args["options"] = opts
    s, b = call_tool("tg_ask", args)
elif cmd == "complete":
    s, b = call_tool("tg_complete", {"summary": arg1, "wait_for_task": False})
else:
    print("Unknown command:", cmd); sys.exit(1)

print(f"{s}: {b[:100]}")
sse_running = False
