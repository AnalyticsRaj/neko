# Neko — shared browser on your server

One real browser that lives on your server. Log into Telegram / WhatsApp / Instagram
**once**, and it's there from **every device** (phone, laptop) — because every device
views the same browser. Password protected.

Open it at:  **http://5.189.136.54:9012**

---

## One-time setup on the server

```bash
# 1. install Docker (if you don't have it)
curl -fsSL https://get.docker.com | sh

# 2. go to this folder (where docker-compose.yml is)
cd neko

# 3. open the required ports in the firewall
ufw allow 9012/tcp
ufw allow 52000:52100/udp
#   (CentOS/Alma: firewall-cmd --add-port=9012/tcp --add-port=52000-52100/udp --permanent && firewall-cmd --reload)

# 4. start it
docker compose up -d
```

That's it. Open **http://5.189.136.54:9012** on any device.
- Normal login password: `open@123`  (this is the USER password in .env)
- Admin password is in `.env` (full control).

## Use it
- Log into Telegram/WhatsApp/Instagram inside this browser once.
- Open the same URL on your phone, type the password → everything is already logged in.
- Multiple people can watch; one controls at a time (click to take control).

## Manage
```bash
docker compose logs -f      # see logs
docker compose restart      # restart
docker compose down         # stop
docker compose pull && docker compose up -d   # update
```

## Change settings
Edit `.env`:
- `NEKO_USER_PASSWORD` — the password you type to get in.
- `NEKO_ADMIN_PASSWORD` — admin password.
- `NEKO_PUBLIC_IP` — your server's public IP (already set to 5.189.136.54).

After editing: `docker compose up -d` again.

Want a bigger screen / more accounts at once? Raise `NEKO_DESKTOP_SCREEN`
(e.g. `1920x1080@30`) in docker-compose.yml and give the server enough RAM.

**Note:** `.env` has your passwords — it is git-ignored, keep it only on the server.
**RAM:** give the server at least ~2 GB free; a browser with many tabs uses a lot.
