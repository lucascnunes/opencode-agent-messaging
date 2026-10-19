# opencode-agent-messaging

Let one OpenCode agent send messages to — and read the work of — another, across sessions.

## Why this exists

OpenCode is client-server. Every TUI and CLI you launch is only a *client* of one shared
background service, and that service owns every session on the machine. So while an agent is
running in another terminal, its session is a normal HTTP resource.

That makes "ask the other agent" a solvable problem. You do not need their terminal, you do not
need to guess which window they are in, and the exchange lands in their transcript where they can
scroll back to it — instead of vanishing past in a scrollback buffer.

This repo packages that as an OpenCode skill plus a small helper script.

## Install

```sh
git clone https://github.com/lucascnunes/opencode-agent-messaging.git
./install.sh
```

Or point OpenCode at the repo directly without copying anything:

```jsonc
// ~/.config/opencode/opencode.json
{
  "$schema": "https://opencode.ai/config.json",
  "skills": ["~/Projetos/opencode-agent-messaging/opencode-agent-messaging"]
}
```

## Use

Once installed, OpenCode discovers the skill and loads it on its own when you ask for
something like *"pass this to the other agent"*. The skill teaches the model the workflow and
the traps.

To drive the helper yourself:

```sh
# who is running right now
python3 opencode-agent-messaging/scripts/oc-agents.py active

# find a session (newest-updated first)
python3 opencode-agent-messaging/scripts/oc-agents.py list --dir "$PWD"
python3 opencode-agent-messaging/scripts/oc-agents.py list --model deepseek-v4.1-flash

# read what it has been doing
python3 opencode-agent-messaging/scripts/oc-agents.py show ses_... --limit 5

# hand something over
python3 opencode-agent-messaging/scripts/oc-agents.py send ses_... ./handoff.md
```

Requires `opencode` and Python 3.9+ on `PATH`.

## How it works

```sh
opencode api get /api/session
opencode api post /api/session/<id>/prompt --data '{"text":"..."}'
```

`opencode api` performs the same service discovery and authentication as the TUI, so there is no
token to handle. The helper is a thin, well-commented wrapper that adds the parts that are easy to
get wrong — response shape, pagination, and the failure modes listed below.

## Traps worth knowing

These each cost real debugging time, so the skill documents them in full:

- **The API prefix is `/api/`.** Omit it and the server answers unknown paths with the SPA HTML
  and a 200. It looks like it worked until your JSON parse dies.
- **Write large responses to a file, then parse.** Tool results embed base64 images and the
  message endpoint returns whole pages; piping straight into a parser truncates the object and
  raises `JSONDecodeError: Unterminated string`.
- **Messages use `content`, not `parts`.** Text lives in `content[]` entries with
  `type == "text"`. Message `type` values include `user`, `assistant`, `synthetic`, and `idle`.
- **`order` cannot be combined with `cursor`** on the message endpoint.
- **`GET /api/session` is already newest-updated first**, so you rarely need ordering flags.

## Safety

Sending a prompt causes real code to be written in a shared working tree. Check
`git status` before you message a peer, and give each agent its own git worktree when they are
doing parallel work rather than exchanging messages.

## API reference

`GET /openapi.json` on a running server is the full spec. The endpoints that matter here:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/session` | list sessions, newest-updated first |
| `GET /api/session/active` | which sessions are running right now |
| `GET /api/session/{id}` | one session |
| `GET /api/session/{id}/message` | conversation; `?order=desc&limit=N` |
| `POST /api/session/{id}/prompt` | send a message (`text`, `delivery`) |
| `POST /api/session/{id}/interrupt` | stop a peer mid-turn |
| `POST /api/experimental/session/{id}/wait` | block until the peer goes idle |
| `GET /api/experimental/session/{id}/export` | full transcript |
| `GET /api/event` | server-sent event stream |

`delivery` is `"steer"` (default; lands in the current turn so a peer can course-correct) or
`"queue"` (waits for the current turn to finish).

## License

MIT