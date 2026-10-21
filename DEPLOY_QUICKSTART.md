# Deploy to audit.airitual.com — Quick Checklist

**Architecture:** Cloudflare Worker (web + API) → Cloudflare R2 (job/result storage) → private GitHub Actions repo (Python crawler and PDF generator).

## A. GitHub

1. Create private repo `airitual-seo-geo-auditor` and upload this entire source directory, including `.github/workflows/audit.yml`, to `main`.
2. Create a fine-grained GitHub PAT for that repository with **Actions: Read and write** permission.

## B. Cloudflare R2

1. From this folder, run:

   ```bash
   npm install
   npx wrangler login
   npx wrangler r2 bucket create airitual-audit-reports
   ```

2. Create an **R2 Object Read & Write** API token limited to that bucket.
3. Add these **GitHub Actions repository secrets**:

   ```text
   R2_ACCOUNT_ID
   R2_ACCESS_KEY_ID
   R2_SECRET_ACCESS_KEY
   R2_BUCKET=airitual-audit-reports
   OPENAI_API_KEY        (optional)
   PAGESPEED_API_KEY    (optional)
   ```

## C. Cloudflare Turnstile

1. Create a Turnstile widget allowing hostname `audit.airitual.com`.
2. Save the public **site key** and private **secret key**.

## D. Configure the Worker

Edit `wrangler.jsonc`:

- `GITHUB_OWNER`: your GitHub username or organization
- `GITHUB_REPO`: repo name
- `GITHUB_REF`: default branch name
- `TURNSTILE_SITE_KEY`: Turnstile **public** site key
- Verify `r2_buckets[0].bucket_name` is `airitual-audit-reports`

Then run:

```bash
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put TURNSTILE_SECRET_KEY
npm run deploy
```

Paste the private GitHub PAT and Turnstile secret when prompted.

## E. Connect the subdomain

Cloudflare → **Workers & Pages** → worker `airitual-seo-geo-audit` → **Settings → Domains & Routes → Add → Custom Domain** → `audit.airitual.com`.

Your website is now at **https://audit.airitual.com/** once DNS and SSL are active. No separate Cloudflare Pages deployment is required; Workers Static Assets serves HTML/CSS/JS.

## F. Test

1. Open the site, submit a public HTTPS URL, complete Turnstile, click **Run audit**.
2. Check GitHub → **Actions** to see the workflow processing.
3. Return to the report URL for dashboard, issues, and PDF download.
4. If you just want to preview the UI, click **Open sample report** without running a job.
5. Before broad public use, create a Cloudflare **WAF rate-limit rule** for `POST /api/audits` and set an R2 lifecycle retention policy.

**For errors, locally run:**

```bash
python -m pip install -r requirements.txt
python -m pytest tests/test_engine.py -q
node tests/test_worker.mjs
```

See [README.md](README.md) for security cautions, complete deployment explanations, limitations, and troubleshooting. This app has not been deployed into your accounts; you must configure your own credentials and DNS.
