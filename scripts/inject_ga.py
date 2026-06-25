#!/usr/bin/env python3
"""inject_ga.py — reads ga_config.json, injects gtag snippets into every HTML file across all repos."""

import base64, json, re, subprocess, sys, time
from pathlib import Path

GITHUB_USER = "chartmann1590"
SCRIPT_DIR  = Path(__file__).parent
GA_CONFIG   = SCRIPT_DIR / "ga_config.json"
GA_MARKER   = "googletagmanager.com/gtag/js"

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

def gh(endpoint, method="GET", data=None):
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

def list_html_files(repo, branch, folder):
    tree = gh(f"repos/{GITHUB_USER}/{repo}/git/trees/{branch}?recursive=1")
    prefix = (folder.strip("/") + "/") if folder else ""
    paths = [
        item["path"] for item in tree.get("tree", [])
        if item["type"] == "blob" and item["path"].endswith(".html")
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

def inject(html, mid):
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

def push_file(repo, branch, path, sha, content, mid):
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

def main():
    ga_cfg = json.loads(GA_CONFIG.read_text())
    print(f"Loaded {len(ga_cfg)} measurement IDs\n")

    for repo, branch, folder in REPOS:
        mid = ga_cfg.get(repo)
        if not mid:
            print(f"\nSKIP {repo} — no measurement ID")
            continue
        print(f"\n{repo}  [{mid}]")
        files = list_html_files(repo, branch, folder)
        if not files:
            print(f"  No HTML found at branch={branch} folder={folder or '/'}")
            continue
        injected = skipped = errors = 0
        for f in files:
            if GA_MARKER in f["content"]:
                skipped += 1
                continue
            new = inject(f["content"], mid)
            try:
                push_file(repo, branch, f["path"], f["sha"], new, mid)
                print(f"  OK {f['path']}")
                injected += 1
                time.sleep(0.4)
            except Exception as e:
                print(f"  ERR {f['path']}: {e}")
                errors += 1
        print(f"  -> injected={injected}  skipped={skipped}  errors={errors}")

    print("\n=== Done! ===")

if __name__ == "__main__":
    main()
