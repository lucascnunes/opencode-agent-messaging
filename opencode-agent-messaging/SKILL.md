---
name: OpenCode Agent Messaging
description: Send messages to, and read the conversation of, other OpenCode agents running on the same machine — for example when the user says "pass this to the other agent", "reply to the agent in opencode2", "ask that other session", "what did that other session do", or wants a handoff, review, question, or follow-up delivered to a peer session instead of doing the work yourself. Also use this whenever you need to inspect, hand off to, or coordinate with a running OpenCode TUI/CLI session by ID, since every OpenCode client on the machine shares one background service that owns all sessions.
---

# Talking to other OpenCode agents

## The mental model

OpenCode is **client-server**. Every TUI and CLI you launch — `opencode`, `opencode2`, an alias, a second terminal window — is only a *client* of one shared background service. That service owns every session, its message history, and its running turns.

This is the key insight: **you do not need the other agent's terminal.** The moment it is running, its session is a normal HTTP resource. Writing a prompt to that session is exactly what the user typing into its window would do, which makes it the correct channel for a handoff, a review, or a question.

Reach for this whenever the user asks you to hand something to a peer agent. It beats guessing at their window, and it leaves a durable record in their transcript instead of scrolling past in a terminal.

`opencode api` performs the same service discovery and authentication as the TUI, so use it rather than hand-rolling `curl` — you never touch the auth token.

## Workflow

**1. Find the service** (only to confirm it is healthy; `opencode api` auto-discovers it):

```sh
opencode service status          # prints e.g. http://127.0.0.1:49374
```

**2. Find the session.** Never guess an ID. List them and narrow:

```sh
python3 scripts/oc-agents.py list --dir "$PWD"
```

Sessions come back **newest-updated first**, which is usually already the answer. Narrow further with `--model deepseek-v4.1-flash` when the user named the model. If several look alike, `GET /api/session/active` shows which are actually running right now.

**3. Confirm you picked the right one.** Titles lie — an agent's session title is generated from its first message, not its current task. Read the tail:

```sh
python3 scripts/oc-agents.py show ses_... --limit 5
```

This prints role, timestamp, text, and the tool names it used. If the tail does not match what the user described, keep looking before you send anything.

**4. Write the message to a file first**, then send it. Long messages with code blocks are painful to pass through `--data`:

```sh
python3 scripts/oc-agents.py send ses_... /tmp/handoff.md
```

**5. Verify delivery.** A successful send prints the new message ID. That is enough: if the peer then produces new assistant messages, it read and acted on it.

## Writing the handoff

The peer agent has your repository and your conclusion but none of your reasoning path. What makes a handoff land is the same thing that made a code review useful: root cause, evidence, and why the obvious fix is wrong.

Include:

- **Root cause**, with `file:line` references.
- **Evidence**, ideally something you actually ran rather than inferred. A table of observed request/response behaviour beats a paragraph of argument.
- **Why the current patch does not work**, if there is one. This is the highest-value part — a band-aid that looks right is worse than no fix, and the peer cannot see your evidence.
- **A concrete fix**, and any trade-off you are aware of.
- **Scope**: what you changed and what you deliberately left alone. The peer is about to edit the same working tree; ambiguity here causes conflicting writes.

## Gotchas that cost real time

- **The API prefix is `/api/`.** Omit it and the server silently returns the SPA HTML with a 200 — it looks like it worked, then your JSON parse dies. `scripts/oc-agents.py` turns this into an explicit error.
- **Pipe large responses to a file, then parse.** Tool results carry base64 images and `GET /api/session/{id}/message` returns whole pages; piping straight into `python3` gives `JSONDecodeError: Unterminated string` because the pipe closed mid-object.
- **Messages use `content`, not `parts`,** and text lives in `content[]` entries with `type == "text"`. Message `type` values include `user`, `assistant`, `synthetic`, and `idle`.
- **Do not combine `order` with `cursor`** on the message endpoint — the spec rejects it. Use `?order=desc&limit=N` for the newest N.
- **The `--param` flag did not reliably apply query values** in my testing; putting the query string in the path did. The helper does the latter.
- **`/api/session` is already sorted by most-recently-updated**, so you usually do not need ordering flags at all.

## Delivery mode

`POST /api/session/{id}/prompt` accepts `delivery`:

- `"steer"` (default) — lands in the current turn if one is running, so the peer can course-correct mid-task.
- `"queue"` — waits for the current turn to finish.

Use `steer` for corrections and mid-task course-correction; use `queue` when the peer must finish what it is doing before reading you.

## Before you send: check you will not clobber

Sending a prompt causes real code to be written in a shared working tree. If the peer has uncommitted work and you are about to apply your own changes, say so in the handoff or wait. `git status --short` costs nothing.

## Companion endpoints

Useful once you are comfortable with the basics:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/session/active` | which sessions are running right now |
| `POST /api/session/{id}/interrupt` | stop a peer mid-turn |
| `POST /api/session/{id}/prompt` | send a message (`text`, `delivery`, `agents`, `files`) |
| `POST /api/experimental/session/{id}/wait` | block until the peer goes idle |
| `GET /api/experimental/session/{id}/export` | full session transcript |
| `GET /api/event` | server-sent event stream |
| `GET /openapi.json` | full spec; also `opencode api --help` |

`/openapi.json` is the authority when you need an endpoint this skill does not cover. Do not guess endpoint shapes.

## When this is the wrong tool

- **The user wants a second opinion, not a handoff.** Spawn a `general` subagent inside your own session instead. It is cheaper, synchronous, and its findings stay in your transcript where the user can read them.
- **Nothing is running and nothing needs to act.** Write the findings into the conversation or a file; there is no peer to hand off to.
- **You want parallel *work* rather than a message.** Several sessions can edit one working tree at once and corrupt each other's files. Give each agent its own git worktree, and use this only for the parts that need to talk.