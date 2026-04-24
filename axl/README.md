# AXL nodes

Three AXL agent nodes — Ed25519 keys + configs for the 3-of-N quorum demo.

## Binary

`bin/node` — built from [github.com/gensyn-ai/axl](https://github.com/gensyn-ai/axl) with `make build` (pins to Go 1.25.5 via Makefile's `GOTOOLCHAIN`).

## Nodes

| Node | API port | Key file | Config |
|---|---|---|---|
| A | 9002 | `node-a-private.pem` | `node-a-config.json` |
| B | 9012 | `node-b-private.pem` | `node-b-config.json` |
| C | 9022 | `node-c-private.pem` | `node-c-config.json` |

All three peer to Gensyn's public bootstrap nodes (`34.46.48.224:9001`, `136.111.135.206:9001`) so they can discover each other over the Yggdrasil mesh.

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

- `GET /topology` — our IPv6, pubkey, peers, tree
- `POST /send` with `X-Destination-Peer-Id: <hex-pubkey>` header — unicast raw bytes
- `GET /recv` — poll for inbound messages (204 if empty, 200 with `X-From-Peer-Id` header if present)
- `POST /mcp/{peer_id}/{service}` — JSON-RPC to peer's MCP service
- `POST /a2a/{peer_id}` — JSON-RPC to peer's A2A server

## Broadcast pattern

AXL has no native broadcast primitive. To broadcast a signed finding to all peers:

```python
topology = requests.get(f"http://127.0.0.1:{api_port}/topology").json()
for peer in topology["peers"]:
    requests.post(
        f"http://127.0.0.1:{api_port}/send",
        headers={"X-Destination-Peer-Id": peer["public_key"]},
        data=signed_payload_bytes,
    )
```

See `agents/axl_client.py` (lands Day 4) for the full helper.
