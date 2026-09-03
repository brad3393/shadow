# SHADOW-DEPLOY USB Kit — Windows

Run Shadow off a USB stick: plug it into the laptop, and Shadow boots with
zero (or one) clicks. Heavy lifting stays on the laptop; your phone talks to
it over the REST API.

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
3. Done. Shadow verifies itself, starts the REST API on port 8787,
   and drops you into the CLI.

> Note: Windows blocks USB sticks from running code with *zero* clicks
> (this is a deliberate anti-malware rule that applies to everyone).
> The Sentinel below gets you to true zero-click anyway.

### Mode B — zero clicks after one-time setup (recommended)
1. Plug the stick in, open it, run **sentinel\install-sentinel.bat** once (~30 s).
2. That's it — from now on, plugging the SHADOW-DEPLOY stick into this
   laptop makes Shadow start by itself. The watcher only reacts to a stick
   labeled `SHADOW-DEPLOY`, nothing else.
3. To undo: run **sentinel\uninstall-sentinel.bat**.

### Mode C — always-on (Shadow starts at Windows logon, no USB needed)
Create a shortcut to `START_SHADOW.bat` and place it in:
`Win+R → shell:startup`

## Phone access (Pixel 7)
Shadow's API binds to the LAN while running: `http://<laptop-ip>:8787`
Find the laptop IP with `ipconfig` (look for IPv4 Address).
First run, Windows Firewall asks once — tick **Private networks** and Allow.
For access away from home, put Tailscale on both devices (planned sync layer).

## Requirements
- No Python needed on the laptop if `python_embed\` is on the stick
  (Shadow is pure Python stdlib — the embedded runtime is complete).
- No admin rights needed for any mode.
- The stick can be FAT32 or exFAT.

## Security notes
- The Sentinel runs only the launcher from a stick labeled SHADOW-DEPLOY;
  it never executes anything else, and it stores no data on the stick.
- Guardian still audits every command Shadow executes.
- Keep the stick physically with you — anyone holding it can run Mode A
  on their own machine too (which is a feature: your Shadow, any PC).
