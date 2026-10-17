# Deploying Lineage to a Vultr VM with HTTPS (Caddy)

Target: one Ubuntu 24.04 VM (2 vCPU / 4 GB is enough; CLIP runs on CPU), a domain with an
A record pointing at the VM, ports 80 and 443 open.

```bash
# on the VM
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER && newgrp docker
git clone https://github.com/JonathanKash/SwampHacks-Submission.git lineage && cd lineage
cp .env.example .env && nano .env            # GEMINI_API_KEY, ADMIN_TOKEN
export DOMAIN=lineage.example.com            # your domain
docker compose -f deploy/docker-compose.yml up -d --build
```

First start downloads the CLIP weights (about 350 MB) into the `lineage-data` volume. Then seed
the demo pool once:

```bash
docker compose -f deploy/docker-compose.yml exec lineage \
  python backend/scripts/fetch_seeds.py --count 6
docker compose -f deploy/docker-compose.yml exec lineage \
  python backend/scripts/seed_pool.py --families 3 --chains 2 --reset
docker compose -f deploy/docker-compose.yml restart lineage
```

Open `https://$DOMAIN/` (about), `/edit` on the tablet, `/tree` on the big screen, `/audit`
for the industry workspace. Caddy obtains and renews the certificate automatically.

Updating: `git pull && docker compose -f deploy/docker-compose.yml up -d --build`.

Resetting the demo pool during the event: `curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN"
https://$DOMAIN/api/reset`, then run `seed_pool.py` again.
