# ShadowOS — turn a laptop into a dedicated Shadow appliance

ShadowOS is not a new operating system written from scratch — it's a
minimal Debian Linux stripped down to exactly one job: running Shadow.
Boot the machine and you land directly in Shadow's console, fullscreen.
No Windows, no desktop, no login screen. The machine *is* the agent.

## Why this exists
An old laptop (2014-era dual-core, 8 GB RAM, no VRAM) is a poor Windows
machine but a *great* appliance. Shadow is pure stdlib Python — the
orchestration weighs almost nothing. The heavy AI lifting happens on your
desktop PC's Ollama, reached over Tailscale. Old laptop stands watch,
desktop does the thinking, phone is your window.

## What you need
- The target laptop (contents will be WIPED — back up anything first)
- Another PC to prepare the USB stick
- A USB stick (2+ GB) for the Debian installer
- ~45 minutes

## Install guide

### 1. Make the Debian installer USB (on your desktop)
1. Download the Debian netinst ISO (amd64):
   https://www.debian.org/download
2. Flash it to the USB stick with Rufus (https://rufus.ie) — pick the ISO,
   "DD mode" if asked.

### 2. Install minimal Debian on the laptop
Boot the laptop from the USB (tap ESC / F9 for the boot menu on HP),
then "Graphical install":
- Language/keyboard: your own
- Hostname: **shadowos**
- Root password / user: anything you like (you'll barely see it)
- Partitioning: **"Guided - use entire disk"** (all of it)
- Software selection / tasksel: **uncheck EVERYTHING** — no desktop
  environment, no print server. Just the base system.
- Install GRUB to the primary drive. Reboot.

You'll land at a text login. Log in with the user you created.

### 3. One command → ShadowOS
Run the installer (it fetches Shadow from GitHub and wires everything):

```bash
sudo apt update && sudo apt install -y curl
curl -fsSL https://raw.githubusercontent.com/brad3393/shadow/main/shadowos/install-shadowos.sh -o install-shadowos.sh
sudo bash install-shadowos.sh 100.x.y.z
```

Replace `100.x.y.z` with your **desktop PC's Tailscale IP** (find it with
`tailscale ip` on the desktop). Skip it if you don't have Tailscale set up
yet — Shadow runs in stub mode until you add `OLLAMA_HOST` to
`/etc/default/shadow` later.

### 4. Boot into Shadow
Reboot. The laptop now boots straight into Shadow's console, fullscreen,
and the API is live at `http://<laptop-ip>:8787` for your phone.

## Wiring the desktop brain
On the desktop PC (Windows 11 + Ollama):
1. Install Tailscale on both machines, log in to both with the same account.
2. Make Ollama listen on the network:
   System Environment settings → `OLLAMA_HOST=0.0.0.0` → restart Ollama.
3. Allow Ollama through the Windows Firewall (port 11434, private networks).
4. The laptop's `/etc/default/shadow` already points `OLLAMA_HOST` at
   the desktop's Tailscale IP.

Now the laptop's Shadow thinks with the desktop's models
(Llama 3 8B, Mistral, nomic-embed-text).

## Daily use
- **Power button** → boots to Shadow console in ~15 seconds
- **Phone/Pixel 7** → `http://<laptop-tailscale-ip>:8787`
- **Exit the console?** Ctrl-C restarts it (it's a systemd service).
  Alt+F2 gets you a normal login prompt if you ever need a real shell.

## Changing / updating
- Update Shadow:      `sudo systemctl stop shadow-console shadow-api &&
                       cd /opt/shadow && sudo -u shadow curl -fsSL
                       https://github.com/brad3393/shadow/archive/refs/heads/main.tar.gz |
                       sudo tar -xz --strip-components=1 && sudo systemctl start shadow-api shadow-console`
- Config:            `/etc/default/shadow`
- Services:          `systemctl status shadow-console shadow-api`
- Uninstall (keep Debian): delete both services, re-enable `getty@tty1`
