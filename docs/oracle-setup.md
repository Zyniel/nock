# Putting Nock online on Oracle Cloud (step by step)

This guide is for the owner. It follows the plan in `docs/hosting.md`
(option D). Allow about two hours the first time. Commands are given exactly;
copy them as written and replace only what is between `<` and `>`.

When a step does not go as described, stop there and ask a Claude session for
help. Paste the step number and what you see.

## What you will have at the end

```
Players ──HTTPS──▶ nock.<your-domain> ──▶ Oracle server (Paris or Marseille)
                                            ├─ Caddy: HTTPS certificates, no access log
                                            └─ Nock: the game, its database on a separate disk
GitHub ── on each version tag: tests, build, deploy ──▶ the server
Server ── every night: encrypted backup ──▶ Oracle Object Storage (kept 14 days)
```

The files that do this are in the repository:

| File | What it does |
| --- | --- |
| `Dockerfile` | Builds the app image: the web client, then Python and the app. |
| `deploy/compose.yaml` | Runs Caddy and Nock on the server. |
| `deploy/Caddyfile` | Caddy's settings: your domain, HTTPS, no access log. |
| `deploy/.env.example` | Template of the server's settings and secrets. |
| `deploy/backup.env.example` | Template of the backup settings. |
| `deploy/setup-server.sh` | One-time preparation of a new server. |
| `deploy/deploy.sh` | Installs one version, checks it, goes back if it fails. |
| `deploy/backup.sh` | Nightly backup (and before each deploy). |
| `deploy/restore-test.sh` | Monthly check that the latest backup really restores. |
| `deploy/systemd/` | The timers that run the backup and the restore test. |
| `.github/workflows/deploy.yml` | The automatic deployment on each version tag. |
| `compose.sandbox.yaml` | The sandbox on your own computer. |

## Before you start

- A card for Oracle's sign-up. Nothing is charged as long as only Always Free
  resources are used, and step 2 sets an alert at 1 €.
- Access to your domain's DNS settings (at your registrar).
- Admin access to the GitHub repository `zyniel/nock`.
- On your computer: PowerShell (Windows) and the repository folder
  (`K:\Projects\nock`). OpenSSH (`ssh`, `scp`, `ssh-keygen`) comes with Windows.
- A password manager for the secrets this guide creates.
- **One rule about privacy.** Until spec 038 is built, the app writes visitors'
  IP addresses in its log. Make the site public only with a version that
  includes spec 038 (the `v1.0.0` release of `docs/build-plan.md`). Before
  that, use the site only for private tests.

Oracle's console changes its menus from time to time. If a name below differs
slightly, look for the closest one.

## Step 1. Create the Oracle Cloud account

1. Go to <https://www.oracle.com/cloud/free/> and choose "Start for free".
2. Fill in the form. For **Home Region**, choose **France Central (Paris)** or
   **France South (Marseille)**. This cannot be changed later, and the free
   server can only be created there.
3. Confirm the e-mail and the card check, then sign in to the console.

## Step 2. Switch to Pay As You Go and set a budget alert

The switch keeps the free resources free, and stops Oracle from reclaiming a
server that looks idle (a quiet game server does).

1. Menu ☰ > **Billing & Cost Management** > **Upgrade and Manage Payment** >
   **Upgrade to Pay As You Go**. Confirm.
2. Menu ☰ > **Billing & Cost Management** > **Budgets** > **Create Budget**:
   name `nock`, amount **1** (EUR), alert at **100 %** of actual spending, with
   your e-mail address. You will get an e-mail if anything ever costs money.

## Step 3. Create your SSH key (on your computer)

The key lets you, and only you, log in to the server. In PowerShell:

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\nock_admin -C "nock admin"
```

Choose a passphrase when asked (keep it in the password manager). This creates
two files: `nock_admin` (private, never share it) and `nock_admin.pub`
(public). Show the public one, to paste in step 4:

```powershell
Get-Content $HOME\.ssh\nock_admin.pub
```

## Step 4. Create the server

Menu ☰ > **Compute** > **Instances** > **Create instance**.

1. **Name**: `nock`.
2. **Image and shape** > **Edit**:
   - **Change image**: **Canonical Ubuntu**, version **24.04** (not "Minimal").
   - **Change shape**: **Ampere** > **VM.Standard.A1.Flex**, **1 OCPU** and
     **6 GB** memory. The label "Always Free-eligible" must show.
3. **Networking**: create a new virtual cloud network and a new **public**
   subnet (the defaults), and keep **Assign a public IPv4 address** checked.
4. **Add SSH keys** > **Paste public keys**: paste the line from step 3.
5. **Boot volume**: leave the default size (about 47 to 50 GB).
6. **Create**.

If Oracle answers **"Out of capacity"**: choose another availability domain in
the "Placement" section, or try again later (sometimes for a few days). Nothing
is charged meanwhile.

When the server is **Running**, note its **Public IP address** on its page. Below
it is written `<IP>`.

## Step 5. Open ports 80 and 443 in Oracle's network

On the server's page: **Primary VNIC** > the **Subnet** link > **Security Lists** >
the **Default Security List** > **Add Ingress Rules**. Add two rules:

| Source CIDR | IP protocol | Destination port range |
| --- | --- | --- |
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

(Port 22, for SSH, is already open. The server's own firewall is opened by the
setup script in step 8.)

## Step 6. Create and attach the data disk

The database lives on its own disk, so it survives if the server is rebuilt.

1. Menu ☰ > **Storage** > **Block Volumes** > **Create Block Volume**: name
   `nock-data`, **the same availability domain as the server**, size **50 GB**,
   default performance. **Create**.
2. Back on the server's page: **Attached block volumes** > **Attach block
   volume**: choose `nock-data`, attachment type **Paravirtualized**, access
   **Read/Write**. **Attach**.

## Step 7. Point your subdomain to the server

At your domain's registrar (DNS settings), add a record:

| Type | Name | Value | TTL |
| --- | --- | --- | --- |
| A | `nock` (or the subdomain you want) | `<IP>` | 3600 (or the default) |

Below, `<DOMAIN>` is the full name, for example `nock.example.org`. It can take
from a few minutes to a few hours to work. Check in PowerShell:

```powershell
Resolve-DnsName <DOMAIN>
```

It must show `<IP>`. Do not go to step 12 before it does: Caddy needs the name
to get the HTTPS certificate.

## Step 8. Prepare the server

In PowerShell, in the repository folder, copy the deploy files to the server,
then log in:

```powershell
cd K:\Projects\nock
scp -i $HOME\.ssh\nock_admin -r deploy ubuntu@<IP>:/tmp/nock-deploy
ssh -i $HOME\.ssh\nock_admin ubuntu@<IP>
```

(The first time, answer `yes` to the question about the host's fingerprint.)

You are now on the server. Find the data disk's name:

```bash
lsblk
```

It is the 50 GB disk with no partitions and no mount point, usually `sdb`. Then
run the setup with that name:

```bash
sudo bash /tmp/nock-deploy/setup-server.sh /dev/sdb
```

It installs the software, opens the firewall, prepares the disk (it asks you to
type `yes` before formatting the new disk), and turns on the backup timers. It
takes a few minutes. At the end, log out (`exit`) and log in again with the same
`ssh` command.

## Step 9. The server's settings and secrets

On the server:

```bash
cd /srv/nock/deploy
cp .env.example .env
chmod 600 .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
nano .env
```

The `python3` line prints a random operator token. In the editor:

- `NOCK_DOMAIN=<DOMAIN>`
- `NOCK_OPERATOR_TOKEN=` followed by the printed token. It opens the game's
  dashboard at `https://<DOMAIN>/ops`. Save it in the password manager.
- Leave the account and mail lines commented out (step 14 is for later).

Save with `Ctrl+O`, `Enter`, and quit with `Ctrl+X`.

## Step 10. Backups to Oracle Object Storage

In the Oracle console:

1. Menu ☰ > **Storage** > **Buckets** > **Create Bucket**: name `nock-backups`,
   **Standard** tier, the rest as given. **Create**.
2. Optional, as a second safety: in the bucket, **Lifecycle Policy Rules** >
   **Create Rule**: delete objects older than **15** days.
3. Note the **namespace**: menu ☰ > **Governance & Administration** > **Tenancy
   details** > "Object storage namespace" (a short code).
4. Profile icon (top right) > **My profile** > **Customer secret keys** >
   **Generate secret key**, name `nock-backup`. Copy the **secret** at once (it
   is shown only once), then the **Access key** shown in the list.

On the server, create the backup settings:

```bash
cd /srv/nock/deploy
sudo cp backup.env.example backup.env
sudo chmod 600 backup.env
```

Choose a long random password for the encryption (the password manager can
generate one), and keep it there: **without it the backups cannot be read**.
Turn it into rclone's form:

```bash
rclone obscure '<the encryption password>'
```

Then `sudo nano backup.env` and fill in:

- in `RCLONE_CONFIG_OCI_ENDPOINT`, replace `<namespace>`; if your home region is
  Marseille, also replace `eu-paris-1` by `eu-marseille-1` there and in
  `RCLONE_CONFIG_OCI_REGION`;
- `RCLONE_CONFIG_OCI_ACCESS_KEY_ID` and `RCLONE_CONFIG_OCI_SECRET_ACCESS_KEY`:
  the two values of point 4;
- `RCLONE_CONFIG_NOCKBACKUP_PASSWORD`: the output of `rclone obscure`.

Optional: create a free check at <https://healthchecks.io> (period 1 day, grace 2
hours) and put its URL in `BACKUP_PING_URL`. You then get an e-mail if a nightly
backup is ever missed.

The first real backup runs after the first deployment (step 12).

## Step 11. Let GitHub deploy to the server

**A deploy key.** GitHub needs its own key to log in to the server. On your
computer, in PowerShell (press `Enter` twice when asked for a passphrase: this
key must work unattended):

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\nock_deploy -C "github deploy"
Get-Content $HOME\.ssh\nock_deploy.pub | ssh -i $HOME\.ssh\nock_admin ubuntu@<IP> "cat >> ~/.ssh/authorized_keys"
ssh-keyscan <IP>
```

Keep the output of `ssh-keyscan` (a few lines starting with `<IP>`) for the next
part.

**The secrets.** On GitHub, in the repository: **Settings** > **Environments** >
**New environment**, name `production`. Optional: tick **Required reviewers** and
add yourself, to get an "Approve" button before each deployment. Then **Add
environment secret**, four times:

| Name | Value |
| --- | --- |
| `DEPLOY_HOST` | `<IP>` |
| `DEPLOY_USER` | `ubuntu` |
| `DEPLOY_SSH_KEY` | the whole content of `$HOME\.ssh\nock_deploy` (the file **without** `.pub`; show it with `Get-Content $HOME\.ssh\nock_deploy`) |
| `DEPLOY_KNOWN_HOSTS` | the lines printed by `ssh-keyscan <IP>` |

Then delete the private deploy key from your computer once it is in GitHub, or
move it to the password manager.

## Step 12. First deployment

The deployment files must be on `main` (merge the `docs/hosting-plan` branch
first). A deployment starts when a version tag is pushed. Ask a Claude session
to "tag and release v0.x.y", or in PowerShell:

```powershell
git checkout main
git pull
git tag v0.2.0
git push origin v0.2.0
```

On GitHub, **Actions** > **Deploy** shows three jobs: the quality gate (about 15
minutes), the image (about 10 minutes), then the deployment (1 minute). When
all three are green, open `https://<DOMAIN>`: the game's home page shows, with
a padlock.

Then, on the server, check the backups once by hand:

```bash
sudo /srv/nock/deploy/backup.sh
sudo /srv/nock/deploy/restore-test.sh
```

The first ends with "off-site copy uploaded", the second with "restore test
passed".

## Step 13. Be warned when the site is down

Create a free account at <https://uptimerobot.com> (or Better Stack). Add an
**HTTPS** monitor on `https://<DOMAIN>/`, every 5 minutes, alerting your
e-mail. It sees only its own requests, no player data.

## Step 14. Later: sign-in e-mails (V1, spec 033)

Only once a version with accounts is released.

1. Create a free account at <https://www.brevo.com>.
2. In Brevo: **Senders, domains** > add your domain. Brevo shows DNS records
   (DKIM, a code, and the advice for SPF and DMARC). Add them at your
   registrar, then click "Verify" in Brevo.
3. In Brevo: **SMTP & API** > **SMTP** > generate an SMTP key. Note the login
   shown there.
4. On the server, `nano /srv/nock/deploy/.env`, uncomment and fill the account
   lines: `NOCK_PUBLIC_URL=https://<DOMAIN>`, `NOCK_SMTP_HOST=smtp-relay.brevo.com`,
   `NOCK_SMTP_USER=` the login, `NOCK_SMTP_PASSWORD=` the key,
   `NOCK_SMTP_FROM=connexion@<your domain>`.
5. Apply it: deploy the release again (Actions > Deploy > **Run workflow** with
   its tag), or on the server:

   ```bash
   cd /srv/nock/deploy
   docker compose --env-file .env --env-file tag.env up -d
   ```

6. Ask a sign-in link for a Gmail and an Outlook address; it must arrive in the
   inbox, not in spam.

## Everyday use

| You want to | Do |
| --- | --- |
| Release a new version | Push a tag `v...` (or ask Claude to). Deployment follows. If the new version does not start, the server goes back to the previous one by itself and GitHub e-mails you the failure. |
| Deploy an older version again | Actions > Deploy > **Run workflow**, with its tag. Only safe if the newer version did not change the database (its release notes say so). |
| See whether the app runs | `ssh -i $HOME\.ssh\nock_admin ubuntu@<IP>`, then `cd /srv/nock/deploy && docker compose --env-file .env --env-file tag.env ps` |
| Read the app's logs | on the server: `journalctl -t nock --since today` (Caddy: `-t caddy`) |
| See the game's figures | `https://<DOMAIN>/ops`, with the operator token |
| Check the backups | on the server: `systemctl list-timers 'nock-*'` and `journalctl -u nock-backup --since yesterday` |
| Try a version before releasing it | the sandbox, below |

## The sandbox on your computer

Install **Docker Desktop** for Windows once. Then, in the repository folder:

```powershell
docker compose -f compose.sandbox.yaml up --build
```

The game runs at <http://localhost:8000>, the fake mailbox at
<http://localhost:8025>, and `/ops` opens with the token
`sandbox-operator-token-not-a-secret-0000`. Put grid files in a `grids` folder at
the root of the repository to see them in the catalogue. `Ctrl+C` stops it;
`docker compose -f compose.sandbox.yaml down -v` also deletes its data.

## When something goes wrong

| Symptom | Likely cause and fix |
| --- | --- |
| "Out of capacity" when creating the server | Oracle has no free Arm server left in that place for now. Try another availability domain, or again later. |
| `ssh` says "Connection timed out" | Wrong IP, or the server is stopped (console > Instances > Start). |
| The site does not open at all | The DNS record (step 7) does not point to `<IP>` yet, or a port rule is missing (step 5). Check both. |
| The browser warns about the certificate | Caddy could not get it: the DNS was not ready when it started. Once `Resolve-DnsName` shows `<IP>`, run on the server `cd /srv/nock/deploy && docker compose --env-file .env --env-file tag.env restart caddy`, wait a minute, and look at `journalctl -t caddy --since "10 min ago"`. |
| The Deploy workflow is red | Open the failed job in Actions: the gate (a test failed: nothing was deployed), the image, or the deployment (the server went back to the previous version). Paste the end of the log into a Claude session. |
| A budget alert e-mail arrived | Something is no longer free. Look at Billing > Cost Analysis, and ask for help before deleting anything. |
| The server disappeared | Should not happen on Pay As You Go. Rebuild it (steps 4 to 12; step 6 is not needed: attach the existing `nock-data` disk), or restore the latest backup on a new one (ask a Claude session to guide you). |

## Moving away from Oracle

The same files run on any Ubuntu 24.04 server (for example a small paid VPS at
an EU provider). Follow steps 7 to 13 on the new server, then put the latest
backup in place before the first deployment. A Claude session can guide you.
