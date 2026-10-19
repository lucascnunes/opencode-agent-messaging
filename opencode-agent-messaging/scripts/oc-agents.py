#!/usr/bin/env python3
"""
Talk to other OpenCode agents through the shared background service.

OpenCode is client-server: every TUI/CLI (including aliases like `opencode2`)
is just a client of one background service that owns every session. This helper
finds another agent's session and reads or writes its conversation.

Usage:
    oc-agents.py list [--dir PATH] [--model ID] [--limit N]
    oc-agents.py show <session-id> [--limit N]
    oc-agents.py send <session-id> [MESSAGE_FILE|-]
    oc-agents.py active

All calls go through `opencode api`, which performs the same service discovery
and authentication as the TUI, so no token handling is needed here.
"""

import json
import subprocess
import sys
from pathlib import Path


def api(method: str, path: str, body: dict | None = None) -> dict:
    """Call the OpenCode service. Raises on a non-JSON response."""
    cmd = ["opencode", "api", method, path]
    if body is not None:
        cmd += ["--data", json.dumps(body)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"opencode api {method} {path} failed:\n{proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        # Almost always a missing /api prefix: the server answers unknown paths
        # with the SPA HTML, which parses as neither JSON nor an error.
        head = proc.stdout.lstrip()[:80].replace("\n", " ")
        raise SystemExit(
            f"Expected JSON from {path}, got: {head!r}\n"
            "Check that the path starts with /api/."
        )


def message_text(msg: dict) -> str:
    """Concatenate the text parts of a message."""
    return " ".join(
        c.get("text", "")
        for c in msg.get("content", [])
        if c.get("type") == "text"
    ).strip()


def message_tools(msg: dict) -> list[str]:
    return [c.get("name") for c in msg.get("content", []) if c.get("type") == "tool"]


def cmd_list(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="list")
    p.add_argument("--dir", help="only sessions rooted at this directory")
    p.add_argument("--model", help="only sessions using this model id")
    p.add_argument("--limit", type=int, default=50)
    opts = p.parse_args(args)

    data = api("get", f"/api/session?limit={opts.limit}")["data"]
    for s in data:
        if opts.dir and s.get("location", {}).get("directory") != opts.dir:
            continue
        if opts.model and s.get("model", {}).get("id") != opts.model:
            continue
        print(
            f"{s['id']}  {s.get('model', {}).get('id', '?'):<26} "
            f"{s.get('outcome', '?'):<12} {s.get('title', '')[:50]}"
        )


def cmd_show(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="show")
    p.add_argument("session")
    p.add_argument("--limit", type=int, default=10)
    opts = p.parse_args(args)

    # order=desc gives newest first; do not combine order with cursor.
    msgs = api("get", f"/api/session/{opts.session}/message?order=desc&limit={opts.limit}")["data"]
    for m in reversed(msgs):
        stamp = m.get("time", {}).get("created", "")
        text = message_text(m)
        tools = message_tools(m)
        print(f"=== {m.get('type')} {stamp}")
        if text:
            print(text[:1200])
        if tools:
            print(f"[tools] {', '.join(t for t in tools if t)}")


def cmd_send(args: list[str]) -> None:
    import argparse

    p = argparse.ArgumentParser(prog="send")
    p.add_argument("session")
    p.add_argument("message", nargs="?", default="-", help="file path, or - for stdin")
    p.add_argument("--delivery", choices=["steer", "queue"], default="steer")
    opts = p.parse_args(args)

    text = sys.stdin.read() if opts.message == "-" else Path(opts.message).read_text()
    result = api("post", f"/api/session/{opts.session}/prompt",
                 {"text": text, "delivery": opts.delivery})
    msg = result.get("data", {})
    print(f"sent: {msg.get('id')} -> session {msg.get('sessionID')}")


def cmd_active(_args: list[str]) -> None:
    data = api("get", "/api/session/active")["data"]
    for sid, info in data.items():
        print(f"{sid}  {info.get('type')}")


if __name__ == "__main__":
    commands = {"list": cmd_list, "show": cmd_show, "send": cmd_send, "active": cmd_active}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    commands[sys.argv[1]](sys.argv[2:])