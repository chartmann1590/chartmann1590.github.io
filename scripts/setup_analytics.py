#!/usr/bin/env python3
"""
setup_analytics.py

For every GitHub Pages site owned by chartmann1590:
  1. Creates a GA4 property + web data stream if one does not already exist.
  2. Injects the Google tag (gtag.js) snippet into every HTML file in that
     repo's Pages source folder — no local git clone needed.

No setup required. Just run:
  python scripts/setup_analytics.py

A browser window will open once asking you to allow Google Analytics access.
Everything else is automated.
"""

import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from google.analytics.admin import AnalyticsAdminServiceClient
from google.analytics.admin_v1alpha.types import DataStream, Property

# ─── OAuth client — load from scripts/client_secrets.json (gitignored) ───────
#  Create that file from Google Cloud Console: APIs & Services → Credentials
#  → Create OAuth client ID → Desktop app → Download JSON → save as client_secrets.json
_CLIENT_SECRETS_FILE = Path(__file__).parent / "client_secrets.json"
if not _CLIENT_SECRETS_FILE.exists():
    sys.exit(
        f"Missing {_CLIENT_SECRETS_FILE}\n"
        "Download a Desktop OAuth client from Google Cloud Console and save it there."
    )
with open(_CLIENT_SECRETS_FILE) as _f:
    _CLIENT_CONFIG = json.load(_f)
GA_SCOPES = ["https://www.googleapis.com/auth/analytics.edit"]

# ─── Paths ────────────────────────────────────────────────────────────────────
GITHUB_USER    = "chartmann1590"
SCRIPT_DIR     = Path(__file__).parent
TOKEN_FILE     = SCRIPT_DIR / ".ga_token.json"
GA_CONFIG_FILE = SCRIPT_DIR / "ga_config.json"
TIME_ZONE      = "America/Chicago"

# ─── Repo map: (repo, source branch, html subfolder) ─────────────────────────
REPOS = [
    ("chartmann1590.github.io",  "main",     ""),
    ("showcase",                 "master",   ""),
    ("skypulse-android",         "main",     "docs"),
    ("ollama-android-client",    "master",   "website"),
    ("ScamRadar",                "main",     "docs"),
    ("party-quips",              "main",     ""),
    ("android-photobooth",       "main",     "docs"),
    ("DriveVault",               "main",     "docs"),
    ("knightfall",               "main",     "docs"),
    ("trailsage-ai-android",     "main",     "docs"),
    ("captionburn",              "main",     "docs"),
    ("qrcode-scanner-android",   "master",   "docs"),
    ("dreamloom",                "main",     "docs"),
    ("GrocyFridgeScanner",       "master",   "docs"),
    ("AI-Social",                "master",   "website"),
    ("airgf",                    "master",   "docs"),
    ("tiktok-live-gift-tracker", "master",   "docs"),
    ("jury-simulator",           "master",   "site"),
    ("StickyNotes",              "main",     "docs"),
    ("Flashlight",               "main",     "docs"),
    ("LiveTranscribe-Android",   "main",     "docs"),
    ("ToolTok-App",              "main",     "site"),
    ("SpaceShooter",             "master",   "website"),
    ("Pocket-Assistant",         "master",   "docs"),
    ("Rokid-Maps",               "gh-pages", ""),
    ("mls-home-portal",          "main",     "pages"),
    ("VowVault",                 "gh-pages", ""),
]

SITE_URLS = {
    "chartmann1590.github.io":  "https://chartmann1590.github.io/",
    "showcase":                 "https://chartmann1590.github.io/showcase/",
    "skypulse-android":         "https://chartmann1590.github.io/skypulse-android/",
    "ollama-android-client":    "https://chartmann1590.github.io/ollama-android-client/",
    "ScamRadar":                "https://chartmann1590.github.io/ScamRadar/",
    "party-quips":              "https://chartmann1590.github.io/party-quips/",
    "android-photobooth":       "https://chartmann1590.github.io/android-photobooth/",
    "DriveVault":               "https://chartmann1590.github.io/DriveVault/",
    "knightfall":               "https://chartmann1590.github.io/knightfall/",
    "trailsage-ai-android":     "https://chartmann1590.github.io/trailsage-ai-android/",
    "captionburn":              "https://chartmann1590.github.io/captionburn/",
    "qrcode-scanner-android":   "https://chartmann1590.github.io/qrcode-scanner-android/",
    "dreamloom":                "https://chartmann1590.github.io/dreamloom/",
    "GrocyFridgeScanner":       "https://chartmann1590.github.io/GrocyFridgeScanner/",
    "AI-Social":                "https://chartmann1590.github.io/AI-Social/",
    "airgf":                    "https://chartmann1590.github.io/airgf/",
    "tiktok-live-gift-tracker": "https://chartmann1590.github.io/tiktok-live-gift-tracker/",
    "jury-simulator":           "https://chartmann1590.github.io/jury-simulator/",
    "StickyNotes":              "https://chartmann1590.github.io/StickyNotes/",
    "Flashlight":               "https://chartmann1590.github.io/Flashlight/",
    "LiveTranscribe-Android":   "https://chartmann1590.github.io/LiveTranscribe-Android/",
    "ToolTok-App":              "https://chartmann1590.github.io/ToolTok-App/",
    "SpaceShooter":             "https://chartmann1590.github.io/SpaceShooter/",
    "Pocket-Assistant":         "https://chartmann1590.github.io/Pocket-Assistant/",
    "Rokid-Maps":               "https://chartmann1590.github.io/Rokid-Maps/",
    "mls-home-portal":          "https://chartmann1590.github.io/mls-home-portal/",
    "VowVault":                 "https://chartmann1590.github.io/VowVault/",
}

# ─── Auth ─────────────────────────────────────────────────────────────────────

def get_credentials() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GA_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("\nA browser window will open — click Allow to grant Analytics access.")
            print("(You are already logged in as charles.h.hartmann1@gmail.com)\n")
            flow = InstalledAppFlow.from_client_config(_CLIENT_CONFIG, GA_SCOPES)
            creds = flow.run_local_server(
                port=0,
                login_hint="charles.h.hartmann1@gmail.com",
                prompt="consent",
            )
        TOKEN_FILE.write_text(creds.to_json())
        print("Auth token saved.\n")
    return creds

# ─── GA4 Admin ────────────────────────────────────────────────────────────────

def get_account_name(client: AnalyticsAdminServiceClient) -> str:
    accounts = list(client.list_accounts())
    if not accounts:
        sys.exit("No GA4 accounts found. Create one at https://analytics.google.com/")
    if len(accounts) > 1:
        for i, a in enumerate(accounts):
            print(f"  [{i}] {a.display_name} ({a.name})")
    return accounts[0].name


def find_existing_measurement_ids(client: AnalyticsAdminServiceClient, account_name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for prop in client.list_properties(filter=f"parent:{account_name}"):
        try:
            for stream in client.list_data_streams(parent=prop.name):
                if stream.type_ == DataStream.DataStreamType.WEB_DATA_STREAM:
                    uri = stream.web_stream_data.default_uri.rstrip("/")
                    mid = stream.web_stream_data.measurement_id
                    if uri and mid:
                        out[uri] = mid
        except Exception:
            pass
    return out


def create_property(client: AnalyticsAdminServiceClient, account_name: str, repo: str, site_url: str) -> str:
    display_name = repo.replace("-", " ").replace("_", " ").title()
    prop = client.create_property(
        property=Property(
            parent=account_name,
            display_name=display_name,
            time_zone=TIME_ZONE,
            currency_code="USD",
            industry_category=Property.IndustryCategory.TECHNOLOGY,
        )
    )
    time.sleep(1)
    stream = client.create_data_stream(
        parent=prop.name,
        data_stream=DataStream(
            type_=DataStream.DataStreamType.WEB_DATA_STREAM,
            display_name=f"{display_name} Web",
            web_stream_data=DataStream.WebStreamData(default_uri=site_url),
        ),
    )
    mid = stream.web_stream_data.measurement_id
    print(f"  Created: {display_name} → {mid}")
    time.sleep(1)
    return mid

# ─── GitHub file helpers (via gh CLI) ─────────────────────────────────────────

def gh(endpoint: str, method: str = "GET", data: dict | None = None):
    cmd = ["gh", "api", endpoint]
    if method != "GET":
        cmd += ["-X", method]
    inp = json.dumps(data).encode() if data else None
    if inp:
        cmd += ["--input", "-"]
    r = subprocess.run(cmd, input=inp, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode().strip())
    return json.loads(r.stdout) if r.stdout.strip() else {}


def list_html_files(repo: str, branch: str, folder: str) -> list[dict]:
    tree = gh(f"repos/{GITHUB_USER}/{repo}/git/trees/{branch}?recursive=1")
    prefix = (folder.strip("/") + "/") if folder else ""
    paths = [
        item["path"]
        for item in tree.get("tree", [])
        if item["type"] == "blob"
        and item["path"].endswith(".html")
        and item["path"].startswith(prefix)
    ]
    files = []
    for path in paths:
        try:
            d = gh(f"repos/{GITHUB_USER}/{repo}/contents/{path}?ref={branch}")
            content = base64.b64decode(d["content"].replace("\n", "")).decode("utf-8", errors="replace")
            files.append({"path": path, "sha": d["sha"], "content": content})
        except Exception as e:
            print(f"    WARN: could not read {path}: {e}")
    return files


GA_MARKER = "googletagmanager.com/gtag/js"

def inject(html: str, mid: str) -> str:
    snippet = (
        f'\n  <!-- Google tag (gtag.js) -->\n'
        f'  <script async src="https://www.googletagmanager.com/gtag/js?id={mid}"></script>\n'
        f'  <script>\n'
        f'    window.dataLayer = window.dataLayer || [];\n'
        f"    function gtag(){{dataLayer.push(arguments);}}\n"
        f"    gtag('js', new Date());\n"
        f"    gtag('config', '{mid}');\n"
        f'  </script>'
    )
    return re.sub(r'(<head[^>]*>)', r'\1' + snippet, html, count=1, flags=re.IGNORECASE)


def push_file(repo: str, branch: str, path: str, sha: str, content: str, mid: str) -> None:
    gh(
        f"repos/{GITHUB_USER}/{repo}/contents/{path}",
        method="PUT",
        data={
            "message": f"Add Google Analytics tracking ({mid})",
            "content": base64.b64encode(content.encode()).decode(),
            "sha": sha,
            "branch": branch,
        },
    )

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # 1. Authenticate
    print("=== Step 1: Google Analytics authentication ===")
    creds   = get_credentials()
    client  = AnalyticsAdminServiceClient(credentials=creds)
    account = get_account_name(client)
    print(f"Account: {account}\n")

    # 2. Load saved measurement IDs
    ga_cfg: dict[str, str] = {}
    if GA_CONFIG_FILE.exists():
        ga_cfg = json.loads(GA_CONFIG_FILE.read_text())
        print(f"Loaded {len(ga_cfg)} saved measurement IDs from ga_config.json\n")

    # 3. Match already-existing GA properties to repos
    print("=== Step 2: Scanning existing GA4 properties ===")
    existing = find_existing_measurement_ids(client, account)
    for uri, mid in existing.items():
        for repo, site_url in SITE_URLS.items():
            if site_url.rstrip("/") == uri.rstrip("/") and repo not in ga_cfg:
                ga_cfg[repo] = mid
                print(f"  Matched existing: {repo} → {mid}")
    print()

    # 4. Create missing properties
    print("=== Step 3: Creating missing GA4 properties ===")
    for repo, _, _ in REPOS:
        if repo in ga_cfg:
            print(f"  SKIP {repo} (already has {ga_cfg[repo]})")
            continue
        try:
            ga_cfg[repo] = create_property(client, account, repo, SITE_URLS[repo])
        except Exception as e:
            print(f"  ERROR {repo}: {e}")

    GA_CONFIG_FILE.write_text(json.dumps(ga_cfg, indent=2))
    print(f"\nSaved to {GA_CONFIG_FILE}\n")

    # 5. Inject tracking into every HTML file
    print("=== Step 4: Injecting tracking into HTML files ===")
    for repo, branch, folder in REPOS:
        mid = ga_cfg.get(repo)
        if not mid:
            print(f"\n  SKIP {repo} — no measurement ID")
            continue
        print(f"\n  {repo}  [{mid}]")
        files = list_html_files(repo, branch, folder)
        if not files:
            print(f"    No HTML found at branch={branch} folder={folder or '/'}")
            continue
        injected = skipped = errors = 0
        for f in files:
            if GA_MARKER in f["content"]:
                skipped += 1
                continue
            new = inject(f["content"], mid)
            try:
                push_file(repo, branch, f["path"], f["sha"], new, mid)
                print(f"    ✓ {f['path']}")
                injected += 1
                time.sleep(0.4)
            except Exception as e:
                print(f"    ✗ {f['path']}: {e}")
                errors += 1
        print(f"    → injected={injected}  skipped(already tagged)={skipped}  errors={errors}")

    print("\n=== Done! ===")
    print("All HTML files have been updated directly in each repo.")
    print("GitHub Actions / Pages will rebuild and publish the changes.")


if __name__ == "__main__":
    main()
