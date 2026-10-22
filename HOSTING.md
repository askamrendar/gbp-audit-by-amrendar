# Deploy the background audit service

The hosted service is prepared, but no hosting account or paid service has been provisioned. GitHub Pages continues to use the local runner until a hosted endpoint is configured.

## What users see after deployment

Open the service's HTTPS address, enter a Maps link and keyword, approve collection and start. No Python installation, browser extension, pairing code or local Chrome is needed. A server-side Chromium worker performs the audit and generates editable PowerPoint files and an evidence ZIP. The interface reconnects to audits in the same browser tab after a refresh. Users can rebuild reports from saved data without another Google collection.

Google blocks, unresolved branch identities, private owner fields and media interpretation can still require input. A background browser does not eliminate these evidence limits. Server-origin Maps order is disclosed as exploratory; it does not verify the customer's physical search origin.

## Deploy one container

Use a provider that supports long-running Docker containers, outbound browser traffic and persistent disk. Start with 2 GB RAM and one service instance, then measure actual jobs. Sleeping/ephemeral free tiers may interrupt collection or lose reports.

```sh
docker build -t gbp-audit .
docker run --rm -p 8000:8000 --shm-size=1g \
  -v gbp-audit-data:/data \
  -e AUDIT_ALLOWED_ORIGINS=https://askamrendar.github.io \
  gbp-audit
```

Open http://localhost:8000 for local container testing. Configure the hosting provider's HTTPS ingress and persistent volume at `/data`. Health check: `GET /api/health`. The image installs matching Playwright Chromium and OS dependencies, runs as a non-root user, and uses the provider's `PORT` if supplied. Run **one Uvicorn worker and one service instance**: the queue and rate counters are in memory. Multiple workers/replicas require a shared queue and database before scaling. Chromium sandbox support depends on the host; use the host's container isolation and avoid privileged containers.

| Setting | Default | Meaning |
|---|---|---|
| `PORT` | `8000` | HTTP port behind the hosting provider's TLS ingress |
| `AUDIT_DATA_DIR` | `/data` in Docker | Persistent private outputs and job metadata |
| `AUDIT_ALLOWED_ORIGINS` | GitHub Pages origin | Comma-separated additional frontend origins; no wildcard |
| `AUDIT_RETENTION_HOURS` | `24` | Expiry for terminal jobs, cleaned on startup and job access |
| `AUDIT_MAX_STORES` | `10` | Maximum stores per hosted job |

The same-origin frontend is served by the container automatically. To keep the GitHub Pages address, edit `docs/config.js` after deploying:

```js
window.GBP_AUDIT_CONFIG = {
  apiBase: 'https://YOUR-SERVICE-HOST/api',
  hosted: true
};
```

Publish this configuration to Pages. Never put a deployment credential or shared server secret in this file. Until this URL is real, leave the default configuration unchanged.

## Jobs, privacy and limits

Each tab receives an anonymous random session token stored in that tab's session storage. Jobs and downloads require the matching bearer token; the server stores only its hash. Other sessions cannot list or download that tab's jobs. Losing the tab/session token loses access; there is no account recovery. Do not treat anonymous sessions as enterprise account authentication.

One browser audit runs at a time; at most four hosted jobs can be active/queued globally, with one active job per session. Hosted media sampling is capped at 20 items per profile. Request body limit is 5 MB; decoded spreadsheet limit is 3.5 MB. Basic per-connection-address rate limiting is included. Proxies may share one address, so test the provider's behavior; configure provider-side access/rate controls before opening high-volume public usage. No provider has been selected and no hosting costs have been authorized.

Job metadata is persisted privately. On restart, interrupted jobs are marked stopped, while saved outputs remain downloadable and reports can be rebuilt. The worker runs independently of the page; closing the page does not cancel collection. Completed/failed jobs expire after the retention window. Continuous scheduled deletion, account login and horizontal scaling are not implemented.

## Export troubleshooting

Open **Recent audits** rather than launching a duplicate audit. Download PowerPoint or all evidence. The client validates that a download is non-empty and begins with a ZIP/PPTX signature; the server validates PPTX ZIP structure before advertising success. MIME type, attachment filename and file length are supplied. If a transfer fails, the page reports it and allows a retry. If report generation fails after audit data was saved, use **Rebuild PowerPoint from saved data**. Collection is not repeated.

A generated deck can contain unresolved audit fields. This is different from a corrupt or missing download. Check branch identity and collection logs before sharing a report.

## Validation before public launch

```sh
pip install -r requirements-service.txt
pip install httpx
python -m unittest discover -s tests
uvicorn service:app --host 127.0.0.1 --port 8000 --workers 1
```

The service's API tests cover session isolation, queue limits, request consent, bad uploads, file downloads, restart recovery, retention and report rebuilding. Container build/host-specific browser behavior must also be verified on the selected provider. No cloud deployment has been performed.

## Render deployment

The `render.yaml` Blueprint now uses the free Docker web-service plan in Singapore with no persistent disk, following the user's free-only choice. It sets `/api/health`, one worker, one-store jobs and ephemeral report storage. No paid resources are configured. Free services can sleep, restart and run out of browser memory; downloads must be saved promptly. The free configuration does not provide durable 24-hour file retention.
After deployment, verify the actual Render HTTPS address (it may differ from the proposed name), test `/api/health`, then set `docs/config.js` to that address followed by `/api` with `hosted: true`. Keep Pages in local mode until the service is healthy. Test automatic connection, a real audit, PPTX/ZIP downloads and recovery through the Pages address before calling the deployment complete.
