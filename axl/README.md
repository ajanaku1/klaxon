# AXL nodes

Three AXL agent nodes. Ed25519 keys + configs for the 3-of-N quorum demo.

## Binary

`bin/node` is built from [github.com/gensyn-ai/axl](https://github.com/gensyn-ai/axl) with `make build` (pins to Go 1.25.5 via the Makefile's `GOTOOLCHAIN`).

## Nodes

| Node | API port | Key file | Config |
|---|---|---|---|
| A | 9002 | `node-a-private.pem` | `node-a-config.json` |
| B | 9012 | `node-b-private.pem` | `node-b-config.json` |
| C | 9022 | `node-c-private.pem` | `node-c-config.json` |

All three peer to Gensyn's public bootstrap nodes (`34.46.48.224:9001`, `136.111.135.206:9001`). That's how they find each other over the Yggdrasil mesh.

## Run

```bash
# Terminal 1
cd axl && ./bin/node -config node-a-config.json

# Terminal 2
cd axl && ./bin/node -config node-b-config.json

# Terminal 3
cd axl && ./bin/node -config node-c-config.json
```

## HTTP API (per node, on its APIPort)

- `GET /topology`: our IPv6, pubkey, peers, tree
- `POST /send` with `X-Destination-Peer-Id: <hex-pubkey>` header: unicast raw bytes
- `GET /recv`: poll for inbound messages (204 if empty, 200 with `X-From-Peer-Id` header if present)
- `POST /mcp/{peer_id}/{service}`: JSON-RPC to peer's MCP service
- `POST /a2a/{peer_id}`: JSON-RPC to peer's A2A server

## Broadcast pattern

AXL has no native broadcast primitive, and `/topology["peers"]` lists *direct TCP links*. For our nodes that's the Gensyn bootstrap servers, not the other agents in the swarm. Yggdrasil routes by IPv6 across the mesh, so to broadcast to other agents we keep a roster of authorized AXL pubkeys (`agent-roster.json`) and `/send` to each one.

```python
roster = json.load(open("axl/agent-roster.json"))
for agent in roster["agents"]:
    if agent["axlPubkey"] == self_pubkey:
        continue
    requests.post(
        f"http://127.0.0.1:{my_api_port}/send",
        headers={"X-Destination-Peer-Id": agent["axlPubkey"]},
        data=signed_payload_bytes,
    )
```

See `agents/axl_client.py` for the full helper.

## Recv semantics

`/recv` is a single poll, not a long-poll:
- `200 OK` with `X-From-Peer-Id` header + body when a message is queued
- `204 No Content` when the inbox is empty

Agents poll on a loop (we use 100 ms) and process each `200` response.

## Config gotchas

The JSON file is decoded twice. Once by Yggdrasil's config parser (`PrivateKeyPath`, `Peers`, `Listen`, all PascalCase) and once by AXL's `ApiConfig` (`api_port`, `tcp_port`, `router_port`, `a2a_port`, which are **snake_case, not** `APIPort`). Mixed-case fields are silently ignored.

`tcp_port` is the **gVisor netstack port**, not a host OS port. Every node uses the default 7000 even on the same host, because each one runs its own userspace network stack tied to its own Yggdrasil IPv6. Only `api_port` (the HTTP API) has to differ per node when you run multiple nodes locally.

The `-listen` CLI flag overrides the *Yggdrasil P2P listen URI*, not the HTTP API port. Use `api_port` in JSON for the HTTP port.
