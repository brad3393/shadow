# SHADOW-DEPLOY USB Kit — Windows

Run Shadow off a USB stick: plug it into the laptop, and Shadow boots with
zero (or one) clicks. Heavy lifting stays on the laptop; your phone talks to
it over an encrypted tunnel.

## USB stick layout

```
SHADOW-DEPLOY            <- volume label (set when formatting)
├── START_SHADOW.bat     <- one-click launcher (from windows_deploy/)
├── README_USB.md        <- this file
├── shadow\              <- the full Shadow repo
└── python_embed\        <- optional bundled Python (fully offline)
```

## Three ways to use it

### Mode A — one click (no setup at all)
1. Plug the stick in.
2. Open it in Explorer, double-click **START_SHADOW.bat**.
3. Done. Shadow verifies itself, starts the REST API, and drops you into the CLI.

> Note: Windows blocks USB sticks from running code with *zero* clicks
> (deliberate anti-malware rule). The Sentinel below gets you true zero-click.

### Mode B — zero clicks after one-time setup (recommended)
1. Plug the stick in, open it, run **sentinel\install-sentinel.bat** once (~30 s).
2. From then on, plugging the SHADOW-DEPLOY stick into this laptop makes
   Shadow start by itself. The watcher only reacts to a stick labeled
   `SHADOW-DEPLOY`, nothing else.
3. Undo anytime: **sentinel\uninstall-sentinel.bat**.

### Mode C — always-on (Shadow starts at Windows logon, no USB needed)
Create a shortcut to `START_SHADOW.bat` and place it in:
`Win+R → shell:startup`

## Secure phone access — Tailscale (REQUIRED for hotel/shared WiFi)

On untrusted networks (hotel, café, apartment WiFi), never expose Shadow to
the raw local network. The launcher handles this automatically — it binds
the API **only** to the Tailscale interface, making Shadow invisible to
everyone else on the hotel network.

One-time setup (~5 minutes):
1. Laptop: install Tailscale from https://tailscale.com/download
2. Pixel 7: install the Tailscale app from the Play Store
3. Sign in on both with the SAME account (Google login is easiest)
4. Done. Both devices get a private 100.x.x.x address that works
   on hotel WiFi, cellular, anywhere — encrypted end to end.

From your phone: `http://<laptop-tailscale-ip>:8787`
(find the laptop's address with `tailscale ip -4` on the laptop —
the launcher also prints it on every boot.)

If Tailscale isn't installed yet, the launcher safely falls back to
localhost-only — Shadow runs, but stays unreachable from the network
until you install Tailscale. It will NEVER bind to the hotel LAN.

Why this is safe even on hotel WiFi:
- All traffic is WireGuard-encrypted — the hotel network only sees noise
- Shadow binds to the tunnel interface only — other guests can't even find him
- Works even with hotel "client isolation" (devices blocked from seeing
  each other) and captive portals
- Your phone reaches the laptop from cellular too — no WiFi needed at all

Optional extra lock: start the API with `--token <secret>` to require
`Authorization: Bearer <secret>` on every request (for future PWA clients).

## Requirements
- No Python needed on the laptop if `python_embed\` is on the stick
  (Shadow is pure Python stdlib — the embedded runtime is complete).
- No admin rights needed for any mode.
- The stick can be FAT32 or exFAT.

## Security notes
- The Sentinel runs only the launcher from a stick labeled SHADOW-DEPLOY;
  it never executes anything else, and it stores no data on the stick.
- Guardian still audits every command Shadow executes.
- Keep the stick physically with you — anyone holding it can run Shadow
  on their own machine too (your Shadow, any PC).
