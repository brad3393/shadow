# ShadowOS Android — Shadow as a resident node on your phone

ShadowOS Android is not a ROM and it does not replace anything. Shadow
installs *inside* Android, living alongside your normal phone life:
full brain, memory, 10 agents, CLI, and a localhost-only API.

This is the phone half of the offline-first architecture: Shadow in your
pocket when you're out, Shadow on the laptop at home, one brain once the
sync module arrives.

## Install (~5 minutes, no root)

1. Install **Termux from F-Droid** (not the Play Store — that build is
   outdated): https://f-droid.org/en/packages/com.termux/
2. Open Termux and run:

```bash
pkg install curl -y
curl -fsSL https://raw.githubusercontent.com/brad3393/shadow/main/shadowos/install-shadow-android.sh | bash
```

3. Start him anytime:

```bash
bash ~/shadow-start.sh
```

## Start at phone boot (optional)

Install the **Termux:Boot** add-on from F-Droid, open it once. The
installer auto-detects it and registers Shadow to start at boot.

## Security model (same rules as everywhere)

- API binds to `127.0.0.1` **only** — reachable from this phone, invisible
  to mobile data, hotel WiFi, and Bluetooth neighbors. Always.
- No root required. No special permissions beyond Termux itself.
- Guardian audits every command, same as the laptop build.
- For phone→laptop traffic, Tailscale remains the only road (planned sync
  module will ride the tunnel too).

## AI on the phone

Same as the laptop: stub/template mode. The phone's job is orchestration,
memory, and pocket presence — the thinking happens wherever an Ollama or
cloud key lives.

## Daily use

- `bash ~/shadow-start.sh` — console + API
- Browser on the phone: `http://127.0.0.1:8787` — his status page
- His brain: `~/shadow/shadow_data` — backs up by copying that folder
- Update: re-run the installer (safe over the top, brain is preserved)
