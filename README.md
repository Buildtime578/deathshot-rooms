# Deathshot room list server

A tiny server that lets the in-game room browser show rooms across the internet. It only keeps a
list of rooms in memory; the game itself still connects player-to-player.

## Deploy on Render (free)

1. Put this `server/` folder in a GitHub repo (it can be its own repo, or keep it inside the game repo).
2. On render.com: **New > Blueprint** (uses `render.yaml`) or **New > Web Service** with
   *Runtime: Python*, *Build command:* `echo ok`, *Start command:* `python server.py`,
   *Instance type: Free*. If the folder lives inside a bigger repo, set *Root Directory* to `server`.
3. When it's live, open `https://<your-service>.onrender.com/ping`. It should say `ok`.
4. In the game, set `MASTER_URL` at the top of `net.gd` to that address (no trailing slash):
   `const MASTER_URL := "https://deathshot-rooms.onrender.com"`

Render's free tier sleeps the service after ~15 minutes without traffic and takes up to about a
minute to wake. The game pings `/ping` as soon as it launches, so the server is usually awake by
the time someone opens the browser.

## Notes

- Hosts must opt in ("List my room on the internet browser" on the multiplayer screen). Their
  public IP is shown to players who browse, because that's how others connect to them.
- Joining still needs the host to forward **UDP port 7777** on their router. The server can't check that.
- Rooms vanish 30 seconds after the host stops sending heartbeats. Limits: 100 rooms, 3 per IP.
- The server trusts the `CF-Connecting-IP` / `X-Forwarded-For` header Render adds to get the host's
  address. A client can lie about its own listing but only hurts its own room.

## Run locally

```
python server.py        # listens on port 8080 (or $PORT)
```

Then launch the game with `-- --master=http://127.0.0.1:8080` to try it.
