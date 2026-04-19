# Public Relay

## Problem

Presentations are local-only. To share with remote students, you'd need to deploy the server publicly. The relay lets any presenter share their presentation via a public URL without deploying anything.

## Architecture

```
Presenter's laptop                    Relay server                           Viewers
┌─────────────────┐                  ┌──────────────────────┐              ┌──────────┐
│ auditorium run   │  WebSocket      │  auditorium relay    │  WebSocket   │ Browser  │
│ talk.py --public │ ──────────────> │  (port 4243)         │ <─────────── │          │
│                  │  mutations      │                      │  acks        │          │
│ deck runs HERE   │ <────────────── │  /r/<id>/ws          │ ─────────>   │          │
└─────────────────┘  acks           │  /r/<id>/ (HTML)     │  mutations   └──────────┘
                                    └──────────────────────┘
```

### Relay server (`auditorium relay`)

A lightweight FastAPI app. Knows nothing about decks, slides, or Python. It just:

1. Accepts **upstream** connections from presenters at `/upstream`
2. Assigns a unique session ID (short hash)
3. Accepts **viewer** connections at `/r/<id>/ws`
4. Forwards messages bidirectionally:
   - Upstream → viewers: all messages (mutations, clear, slide, notes, etc.)
   - Viewers → upstream: `ack` messages only (keypresses from viewers are dropped — audience is read-only)
5. Keeps a message log per session for late-joining viewers (same pattern as the local server)
6. Serves the audience HTML at `/r/<id>/` — a minimal page that connects to the relay's websocket

The relay does NOT know its own hostname. The presenter's CLI constructs the shareable URL from the `--relay` host.

### Presenter flow (`auditorium run --public`)

1. Start the local server as usual
2. Connect to the relay at `wss://<relay>/upstream` as a websocket client
3. Receive `{"type": "registered", "id": "abc123"}` from the relay
4. Print the public URL in the banner: `Public: http://<relay>/r/abc123`
5. Forward all messages from the local presentation to the relay upstream
6. Receive acks from the relay and feed them back to the local presentation

The presenter's local server still runs normally — local browser tabs work as before. The relay is an additional output channel.

### CLI

```
auditorium relay                        # Run a relay server on port 4243
auditorium relay --port 8080            # Custom port

auditorium run talk.py --public         # Connect to default relay (auditorium.apiad.net:4243)
auditorium run talk.py --public --relay myserver.com:4243  # Custom relay
```

### Relay API

| Endpoint | Description |
|----------|-------------|
| `GET /` | Health check / info page |
| `WS /upstream` | Presenter connects here. Relay assigns ID, forwards messages. |
| `GET /r/<id>/` | Serves audience HTML (same as index.html but websocket points to relay) |
| `WS /r/<id>/ws` | Viewers connect here. Relay forwards from/to upstream. |

### Message flow

**Presenter → Relay → Viewers:**
All messages forwarded as-is. The relay doesn't parse or understand them.

**Viewers → Relay → Presenter:**
Only `ack` messages forwarded. `keypress` messages are dropped (audience is read-only in public mode).

**Late-joining viewers:**
Relay keeps a message log per session (reset on `clear`). New viewers get the log replayed, same as local late-join.

### Session lifecycle

- Session created when presenter connects to `/upstream`
- Session destroyed when presenter disconnects
- Viewers connecting to a non-existent session get an error page
- No auth, no tokens — anyone can host. Session IDs are short random strings (8 chars)

### Relay HTML

The relay serves its own `index.html` at `/r/<id>/`. This is a copy of the audience HTML but with the websocket URL pointing to the relay (`ws://<host>/r/<id>/ws`) instead of the local server. The relay reads the bundled `index.html` from the auditorium package and rewrites the websocket URL.

Actually simpler: the relay serves a tiny HTML page that just sets `window.AUDITORIUM_WS_URL` and loads the standard index.html logic. Or: the relay injects a `<base>` tag or query param that the index.html JS reads to determine the websocket URL.

**Simplest approach:** The relay serves the full `index.html` from the auditorium package (imported at runtime), but patches the websocket URL. The JS in index.html already constructs the URL as `${protocol}//${location.host}/ws` — so when served from the relay at `/r/<id>/`, the JS needs to connect to `/r/<id>/ws` instead of `/ws`. We can add a `data-ws` attribute on the body or a query param.

**Even simpler:** The relay serves a small HTML page that embeds an iframe pointing to the upstream's HTML, with the relay websocket... no, that's complex.

**Best approach:** Modify `index.html`'s JS to check for a `ws_path` URL parameter. If present, use that instead of `/ws`. The relay serves the standard `index.html` with `?ws_path=/r/<id>/ws` appended. No changes to index.html needed beyond reading one query param.

### Files

| File | Action | Description |
|------|--------|-------------|
| `auditorium/relay.py` | Create | Relay server: FastAPI app with upstream/viewer websocket handlers |
| `auditorium/cli.py` | Modify | Add `relay` command, add `--public` and `--relay` flags to `run` |
| `auditorium/static/index.html` | Modify | Read `ws_path` query param to override websocket URL |
| `auditorium/relay.service` | Create | systemd unit file |
| `Makefile` | Create | `make relay` command |

### Deployment

```ini
# auditorium/relay.service
[Unit]
Description=Auditorium Relay Server
After=network.target

[Service]
Type=simple
ExecStart=auditorium relay --port 4243
Restart=always
User=auditorium

[Install]
WantedBy=multi-user.target
```

```makefile
# Makefile
relay:
	auditorium relay --port 4243
```
