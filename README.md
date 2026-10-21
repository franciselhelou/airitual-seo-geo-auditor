# AI Ritual — SEO & GEO Website Auditor (MVP)

A working **Submit URL → GitHub Actions audit → Interactive report → Download PDF** application for `audit.airitual.com`.

The project uses **one Cloudflare Worker** for both the website and API, a **private R2 bucket** for jobs and reports, and **GitHub Actions / Python** for the audit. No database, account registration, or paid SaaS stack is required.

> This is a public-data *screening audit*, not a promise of Google keyword rankings, actual generative-AI mentions, Search Console access, or full directory coverage. The report marks inaccessible/untested data rather than inventing figures.

## What's inside

```text
.github/workflows/audit.yml    GitHub Actions pipeline
src/worker.js                  Cloudflare API, Turnstile verification, R2 results
public/index.html              Submission + results pages
public/styles.css              AI Ritual-themed responsive design
public/app.js                  Submission, polling, charts, report UI, PDF button
public/sample-report.json       Clearly labeled dashboard demo
wrangler.jsonc                  Cloudflare Workers / R2 configuration
requirements.txt               Python dependencies
audit/net.py                    Validated, bounded HTTP fetches
audit/crawl.py                  Robots-aware crawling and HTML extraction
audit/evaluate.py               Evidence-linked findings and explainable scores
audit/pdf_report.py             Multipage branded PDF export
audit/runner.py                 GitHub job and local CLI entrypoints
tests/                          Automated smoke tests
examples/sample-report.pdf      Sample PDF with illustrative data
```

## 1. Prerequisites

- A GitHub account and an **Actions-enabled repository** containing these files.
- Cloudflare account with the `airitual.com` DNS zone if using `audit.airitual.com` as a custom domain. If DNS is elsewhere, you can initially use the `*.workers.dev` URL while preparing the custom domain.
- Node.js **20+** and npm for Wrangler commands.
- Python **3.12+** for optional local audit tests.
- A Cloudflare R2 bucket and a Cloudflare Turnstile widget.
- Optional: an OpenAI API key for improving the narrative summary; the deterministic report works without it.
- Optional: a Google PageSpeed Insights API key for a homepage mobile performance measurement.

**Do not store GitHub tokens, R2 credentials or Turnstile secrets in the repo.**

## 2. Create your GitHub repository

1. Create a new repo named `airitual-seo-geo-auditor` (private is recommended).
2. Upload all of this project's files, including the `.github/workflows/audit.yml` file, to the repo's **default branch** (normally `main`).
3. In **Settings → Actions → General**, ensure workflows are permitted.
4. Check the **Actions** tab; you should see `Website SEO & GEO audit`.

If starting with local files and Git already installed:

```bash
git init
git add .
git commit -m "Initial SEO GEO auditor MVP"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/airitual-seo-geo-auditor.git
git push -u origin main
```

If the default branch is not `main`, use that branch in `wrangler.jsonc` under `GITHUB_REF`.

## 3. Create the R2 bucket

From the project root:

```bash
npm install
npx wrangler login
npx wrangler r2 bucket create airitual-audit-reports
```

Alternatively, create the bucket in **Cloudflare → R2 Object Storage**. Keep it **private**, without a public R2 development URL or custom public bucket domain.

Next, create an **R2 API token** with **Object Read & Write** access **limited to this bucket**:

Cloudflare Dashboard → **Storage & databases → R2 → Overview → Manage API Tokens → Create API Token**.

Save:

- Your Cloudflare **Account ID**
- **R2 Access Key ID**
- **R2 Secret Access Key**
- Bucket name: `airitual-audit-reports`

The GitHub runner uses R2's S3-compatible endpoint to read submissions and write report files. The Worker reads the *same bucket* through its R2 binding.

## 4. Configure the GitHub Actions secrets

Navigate to your repo → **Settings → Secrets and variables → Actions**.

Under **Repository secrets**, create:

| Name | Value |
|---|---|
| `R2_ACCOUNT_ID` | Cloudflare Account ID (not your domain or zone ID) |
| `R2_ACCESS_KEY_ID` | R2 API token Access Key ID |
| `R2_SECRET_ACCESS_KEY` | R2 API token Secret Access Key |
| `R2_BUCKET` | `airitual-audit-reports` |
| `OPENAI_API_KEY` | Optional: your OpenAI API key |
| `PAGESPEED_API_KEY` | Optional: Google PageSpeed Insights API key |

Optional **Repository variable**: `OPENAI_MODEL` (default `gpt-5-mini` if no variable is set; replace if your key lacks access to that model).

**Note:** Missing OpenAI or PageSpeed keys does not prevent generation of the main audit/PDF. The report states when performance was not measured.

## 5. Create a GitHub API token for the Worker

Create a **fine-grained GitHub personal access token** or GitHub App installation token authorized for the audit repository, with **Actions: Read and write** permission. The token is used by the Cloudflare Worker to dispatch `.github/workflows/audit.yml`.

For GitHub fine-grained PATs:

GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens** → select the correct repository → **Repository permissions → Actions → Read and write**.

Copy the generated token. You will store it as a **Cloudflare Worker secret**, never in a browser-accessible variable.

## 6. Create Cloudflare Turnstile verification

Cloudflare Dashboard → **Turnstile → Add widget**:

1. Configure the permitted hostname `audit.airitual.com` (or your chosen test hostname).
2. Save the **public site key** and **secret key**.
3. Update `wrangler.jsonc` with the public **site key** under `TURNSTILE_SITE_KEY`.
4. Store the secret separately as shown below.

Turnstile validation is enforced **server-side**. A valid challenge must be completed before GitHub is dispatched. On test hostnames, configure a widget for that hostname or use Cloudflare's published test keys in local testing only.

## 7. Configure and deploy the Cloudflare Worker

Update `wrangler.jsonc`:

```jsonc
"vars": {
  "GITHUB_OWNER": "YOUR_GITHUB_USERNAME_OR_ORGANIZATION",
  "GITHUB_REPO": "airitual-seo-geo-auditor",
  "GITHUB_REF": "main",
  "TURNSTILE_SITE_KEY": "YOUR_PUBLIC_TURNSTILE_SITE_KEY"
}
```

Leave the R2 binding pointed at your real bucket:

```jsonc
"r2_buckets": [{ "binding": "AUDITS", "bucket_name": "airitual-audit-reports" }]
```

Run in the project root:

```bash
npm install
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put TURNSTILE_SECRET_KEY
npm run deploy
```

Wrangler will ask you to paste the secret values **securely** (the terminal input will not be committed to Git). Make sure `wrangler secret put` is run for the same Worker name as in the config.

It will deploy an initial URL resembling:

`https://airitual-seo-geo-audit.YOUR_SUBDOMAIN.workers.dev`

**Important:** If your Turnstile widget is restricted to `audit.airitual.com`, the challenge won't work correctly on the temporary `workers.dev` URL. Add the desired test hostname to the widget, or test only after connecting the custom domain.

### Attach your custom domain

1. In Cloudflare Dashboard → **Workers & Pages** → select `airitual-seo-geo-audit`.
2. Choose **Settings → Domains & Routes → Add → Custom Domain**.
3. Enter `audit.airitual.com`.
4. Cloudflare creates the DNS record and manages HTTPS if the domain's DNS zone is managed by that Cloudflare account.
5. Wait for certificate/DNS activation and open `https://audit.airitual.com/`.

You can alternatively add the following to the Wrangler config if Cloudflare already manages the `airitual.com` zone:

```jsonc
"routes": [{"pattern": "audit.airitual.com", "custom_domain": true}]
```

Do **not** set a custom domain that already has an incompatible existing DNS record. Remove/adjust conflicting DNS records first.

## 8. Test end to end

1. Open `https://audit.airitual.com/`.
2. Enter a small public website, e.g. a business you own or have permission to audit.
3. Optionally add a couple of external business profile URLs, one per line.
4. Complete Turnstile and click **Run comprehensive audit**.
5. The browser navigates to `/report/<random-uuid>` and polls the API.
6. GitHub → **Actions** → `Website SEO & GEO audit`: watch the job being executed.
7. Once finished, the dashboard displays scores, findings, source URLs, roadmap, and page inventory.
8. Click **Download PDF**.

If the audit finishes without accessible pages (robots restrictions, firewall, or no valid HTML), the report shows **unmeasured scores** and an explicit accessibility warning, not a fabricated passing or failing score.

### Try the report interface without running GitHub

Click **Open sample report** on the home page. It loads clearly labeled **illustrative data** from `public/sample-report.json`. The sample preview does not enable a live PDF download; the separate `examples/sample-report.pdf` is included in this repository.

## 9. Run smoke tests locally

```bash
python -m pip install -r requirements.txt
python -m pytest tests/test_engine.py -q
node tests/test_worker.mjs
node --check public/app.js
```

### Optional Python-only audit

```bash
python -m audit.runner --url https://example.com --output output
```

You should get `output/result.json` and `output/report.pdf`. This does not require Cloudflare or GitHub, but **does** require public network access. To include extra links:

```bash
python -m audit.runner --url https://example.com --extra-url https://www.linkedin.com/company/example/ --output output
```

### Local Cloudflare preview

```bash
npm run dev
```

Wrangler emulates R2 bindings locally by default. GitHub's cloud runner cannot see that local bucket, so **end-to-end dispatch and PDF retrieval require deployment to the real Cloudflare R2 bucket**. The built-in sample dashboard can be previewed without connecting any services.

## 10. Troubleshooting

| Problem | Check |
|---|---|
| Submit button disabled | Turnstile sitekey, hostname allowlist, and browser script/network policies |
| `Server configuration incomplete` | Cloudflare secrets, `GITHUB_OWNER`, `GITHUB_REPO` |
| `Verification failed` | Correct Turnstile secret, correct site key and hostname, expired token |
| `Could not start GitHub workflow` | Fine-grained PAT Actions write permission; workflow exists on default branch; repository/ref match |
| Audit stuck on `queued` | GitHub Actions queued/disabled, `audit.yml` file, job concurrency, Actions billing limits |
| GitHub job fails immediately | GitHub R2 secrets; Python dependencies; Cloudflare account ID and R2 API token scope |
| Audit finished but no PDF | Check GitHub job logs and R2 path `audits/<id>/report.pdf` |
| Scores show N/A | No public HTML was collected; inspect `robots.txt`, crawl permissions, or HTTP errors |
| PageSpeed not measured | Set `PAGESPEED_API_KEY` or accept that field as unavailable |
| Social / Google listing inaccessible | Site may block bots or require approved APIs; no result should be inferred |
| PDF download returns 404 | Job may still be running or PDF upload failed |

Job input and result files in R2:

```text
audits/<UUID>/input.json
             progress.json
             result.json
             report.pdf
```

The UUID acts as a **private unguessable report link**; anyone with the link can access the results. Avoid submitting confidential sites or sensitive details. For private client work, add authentication in a later version.

## 11. Public-site safeguards and limitations

- A Turnstile check is **mandatory** for audit submission.
- Use **Cloudflare WAF Rate Limiting** on `POST /api/audits` before public promotion; an example starting policy is **3 submissions per IP per hour**, with adjustments for your audience.
- Limit the GitHub repository's permissions and set Actions cost limits/budgets. Each public submission consumes Actions minutes and may consume model/API credits.
- The crawler caps itself at **32 pages**, **240 discovered URLs**, **8 external URLs**, **1.25 MB per HTML document**, short timeouts, and 4 redirects.
- It respects explicit robots disallow rules. If `robots.txt` cannot be verified due to denied access or server failure, it does not crawl that site.
- The URL validator rejects IP literal targets, local hostnames, nonstandard ports, DNS addresses that resolve to non-public IPs, and redirects to such addresses. **This is basic SSRF protection; DNS rebinding between preflight and connection is a residual risk.** For high-risk public deployment, additionally run the crawler behind an egress firewall or outbound proxy that rejects private and metadata IP destinations at connection time.
- No full-browser rendering is performed in this MVP: `BeautifulSoup` analyzes fetched HTML. JavaScript-rendered sites may receive incomplete results.
- External sources are **availability checks**, not full Google/Yelp/social APIs or verified NAP comparison.
- GEO score is a **readability heuristic**; it is **not** a measured AI-answer citation share or actual placement in Google/ChatGPT results.
- The PDF contains all findings and recommendations from the JSON result; no fictional keyword volume, actual rankings, backlink counts, or traffic statistics are added.
- A versioned scoring method counts passed/failed automated tests. It is not an official Google rating and should be displayed with audit coverage.
- Current storage has no automatic expiration. Define a Cloudflare R2 **lifecycle policy** (e.g., delete objects after 30 days) and disclose retention in a brief public privacy notice before accepting customer submissions.
- Sensitive content should not be sent to third-party model APIs without permission. The optional AI summary receives limited finding metadata, not full crawled pages.

## 12. Improvements to consider later (not part of this MVP)

Additional crawler depth, actual Search Console access, authorized Google Business/Yelp APIs, real AI-answer citation testing, login, recurring audits, comparison history, and paid features. The MVP deliberately does **not** make unsupported claims for these capabilities.

## References

- Cloudflare [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)
- Cloudflare [R2 Worker binding](https://developers.cloudflare.com/r2/api/workers/workers-api-reference/)
- Cloudflare [R2 S3 SDK](https://developers.cloudflare.com/r2/examples/aws/boto3/)
- Cloudflare [Turnstile verification](https://developers.cloudflare.com/turnstile/get-started/)
- Cloudflare [Workers custom domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/)
- GitHub [REST workflow dispatch](https://docs.github.com/en/rest/actions/workflows/#create-a-workflow-dispatch-event)

© 2026 AI Ritual. Adapt branding and content to your actual website as needed.
