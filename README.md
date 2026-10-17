# India Recruitment Tracker

A standalone, configurable tracker that checks official recruitment/careers pages for Indian PSU banks, financial regulators, and State Public Service Commissions. It looks for recruitment-related links, compares them with the previous run, and emails a digest of newly discovered matching links.

## Important limitations
- This is a starter tool, not an official recruitment feed or a guarantee that every notice will be detected.
- It detects relevant links and page changes; it does not reliably extract/validate every vacancy's eligibility, age limit, scale, or application deadline.
- Official websites may block automated requests, change their layouts, or publish notices only as PDFs. Review the linked official notice before applying.
- The scheduled GitHub Action runs daily but the script only performs a check when at least 15 days have passed since the last successful check.

## Setup (GitHub Actions + email)
1. Create a private GitHub repository and upload the files in this ZIP.
2. In the repository, open **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `SMTP_HOST` (for Gmail: `smtp.gmail.com`)
   - `SMTP_PORT` (`587`)
   - `SMTP_USER` (the sender email address)
   - `SMTP_PASSWORD` (an app password; do not use your normal Gmail password)
   - `ALERT_TO` (the email address where you want alerts)
3. In **Actions**, enable workflows. The tracker checks daily but sends a report only when a 15-day check is due and new matching links are found. It also logs the number of matching links.
4. Run the workflow manually once from **Actions → Recruitment Tracker → Run workflow** to test it.
5. GitHub Actions stores its history file in the repository via the workflow commit. Keep the repository private if you prefer not to expose your tracking history.

## Change what it tracks
Edit `sources.json` to add/remove official pages and `keywords.json` to tune the terms. The default list covers PSU banks, financial regulators and State PSCs, but no list can cover every page or every state perfectly.

## Run locally
Python 3.11+:
```bash
pip install -r requirements.txt
python tracker.py
```
Set the five environment variables listed above if you want email delivery. Without them, the tool prints the report to the console.

## Privacy / security
- Do not commit email passwords or API keys to the repository.
- Use a provider app password or a dedicated SMTP credential.
- The tool only reads public pages and does not submit applications or log into recruitment portals.
