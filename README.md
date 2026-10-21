# GBP Audit by Amrendar

Extension-free, local Python browser audits with a public browser interface, keyword competitor comparison and editable PowerPoint reports.

**Website:** https://askamrendar.github.io/gbp-audit-by-amrendar/

## Start

Install Python 3.11+ and Google Chrome. Download or clone this repository, open its folder in a terminal, then:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python runner.py
```

Windows: `py -m venv .venv`, then `.venv\Scripts\activate`.

Open the website or `http://127.0.0.1:8765`, enter the pairing code printed by the runner, and approve read-only collection. Chrome may ask to allow local network access for the public website. If the browser prevents this, use the local interface; do not disable browser security.

The public site is static. **Every user needs their own running Python process. GitHub Pages cannot execute Python or control Chrome.** No browser extension, Google password or paid API is required. The runner opens a separate persistent Chrome audit profile, not an existing personal tab/profile. Keep its window open until the job completes. The website pairing code stays in page memory and changes when the runner restarts.

## What runs

For each store/keyword: resolve the target profile, capture the profile view, collect a Maps keyword result list around the supplied/inferred map centre, exclude explicitly labelled ads, inspect the first three observed results (deduplicating the target), and collect the linked public websites plus up to two same-host supplementary location/contact pages. Profile, hours, About, posts and bounded item-level gallery collection are attempted where the interface exposes them. Access blocks stop affected collection; no CAPTCHA bypass or login automation.

Outputs per store:

- 11-slide editable PowerPoint: overview, authentic GBP/result screenshots, local comparison, findings, three form-comparison slides, media gaps, two linked-page comparison slides and prioritised action plan.
- 70 stable master checks per collected entity in CSV, with status, evidence-based finding and next input.
- JSON, screenshots and visible-page text, including website headings, canonical, JSON-LD syntax, iframe/link inventory and sampled media IDs/labels.
- One downloadable archive containing all local evidence and reports for the job.

Client name and brand colour are optional inputs before starting. Reports have no client-specific footer or bundled client screenshots.

## Honest coverage

This is a **public evidence audit with disclosed unresolved checks**, not a fully automated assessment of every Google account field. Pass / Partial / Fail / Unknown / Not applicable are assessment states; presence alone does not pass factual or operational checks. Unknown is never converted to failure. No aggregate health score or ranking guarantee is produced.

Maps area-view order is exploratory. The map centre is not verified physical customer origin, and this does not measure Google Search Local Pack, a geographic rank grid or authenticated performance. Check actual screenshot order, sponsored exclusions and identities before using top-three conclusions. A target outside loaded results is not assigned a made-up rank. If the target is itself in the top three, the report contains it once and compares the remaining observed businesses.

Media images and video labels are captured as a sample. Automatic semantic image classification, complete owner upload history, actual video playback quality and exact upload frequency are **not established**. Samples may end early when Google exposes no usable Next control. Inspect saved screenshots; obtain owner exports for private history. Category completeness, descriptions, review/reply rates, Q&A availability and branch truth can require further evidence. The form comparison identifies these gaps explicitly.

Website iframe candidates do not prove rendered review/social embeds, and ordinary social links are not embeds. JSON-LD parsing does not prove schema vocabulary correctness, visible-fact consistency or Google eligibility. Local layout/content usefulness and competitor causation require editorial review. Public competitor evidence cannot establish their private account truth. Reports require review before client delivery.

## Bulk file

CSV (UTF-8) or XLSX, first worksheet, one row per store/keyword. Required:

| Column | Purpose |
|---|---|
| `store_code` | Stable unique code, letters/numbers/hyphens/underscores |
| `maps_url` | Exact HTTPS Google Maps business profile link |
| `keyword` | One exact query, e.g. `sneaker store near me` |

Recommended: `business_name` (strict displayed-name cross-check), `search_latitude`, `search_longitude`. Both coordinates must be supplied together. `expected_address` and `phone` can be retained as inputs for manual corroboration; automated routing/address-truth verification is not implemented. Duplicate business names do not establish identity; use an exact profile link/CID. Expected-name mismatches stop the competitor loop for review. Maximum 100 rows, one job at a time. The web upload cap is 3.5 MB before encoding.

Download [template](docs/template.csv). Never upload passwords, access tokens or unrelated customer data.

## CLI

```sh
python audit.py --maps-url 'https://www.google.com/maps?cid=YOUR_CID' --keyword 'sneaker store near me' --store-code STORE1
python audit.py --input stores.csv
```

`--media-limit 0..50`, `--search-latitude`, `--search-longitude`, `--headless` and `--executable` are available. First-use CLI consent is saved only in the local audit profile. `--yes` is explicit read-only consent for unattended CLI use. The web UI requires consent per job. To stop an audit, interrupt the local runner; completed evidence remains on disk. No resume function is implemented.

## Privacy and security

The runner binds only to `127.0.0.1`, validates host/origin and requires a random bearer pairing code for all API calls. Only this GitHub Pages origin and the local interface can connect. Generated files, browser profiles and uploads are never committed or sent to GitHub. Google and visited websites receive the ordinary browser requests; GitHub Pages logs site visits according to its policies. Local evidence can contain public reviewer names/photos. Review it before sharing. Keep the pairing code private. Do not expose the local service through a public tunnel.

Audited websites cannot intentionally navigate the collector to private-network addresses through the request filter, but this is not a hardened sandbox for hostile web content. Use a dedicated machine/account for untrusted sites. Fetching public pages remains subject to access restrictions, site terms and applicable rules. No stealth, proxy evasion or block bypass is included.

## Development and sources

```sh
python -m unittest discover -s tests
```

Original project code; no external scraper source copied. Reviewed [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper) (MIT, Go-based) and [alokumarjaiswal/gmaps_scraper](https://github.com/alokumarjaiswal/gmaps_scraper) as references. Their implementation was not necessary for this local Python architecture. Dependencies retain their own licences.

Primary platform references: [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages), [Chrome local network access](https://developer.chrome.com/blog/local-network-access), [Playwright persistent contexts](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context).
