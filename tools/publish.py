#!/usr/bin/env python3
"""Merge freshly scraped Facebook posts into posts.json and copy their photos.

Usage: python3 -I tools/publish.py [--push]

Reads the newest ~/Downloads/pkb-<run>.json written by tools/extract.js, moves that
run's photos into images/, and cleans every pkb-* file out of ~/Downloads.

posts.json uses the Graph API `/{page}/posts` shape the app already reads:
  {"data": [{"id", "message", "full_picture", "pictures", "permalink_url", "created_time"}]}
Facebook's own image links expire after a few days, so every photo is downloaded into
images/ and served from this repo instead.
"""
import glob, hashlib, json, os, shutil, subprocess, sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = os.path.join(ROOT, "posts.json")
IMAGES = os.path.join(ROOT, "images")
RAW = "https://raw.githubusercontent.com/{repo}/main/"
PAGE_URL = "https://www.facebook.com/pasalkinbech.com.np"
KEEP = 80  # newest posts kept in the feed


def repo_slug():
    url = subprocess.run(["git", "-C", ROOT, "remote", "get-url", "origin"], capture_output=True, text=True).stdout.strip()
    return url.removesuffix(".git").split("github.com/")[-1].lstrip(":")


def post_id(text):
    # Posts often have no visible permalink, so the id is a hash of the opening text.
    norm = " ".join(text.split())[:300]
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


DOWNLOADS = os.path.expanduser("~/Downloads")


def take_image(filename):
    """Moves a downloaded photo into images/, named by content so repeats dedupe."""
    src = os.path.join(DOWNLOADS, os.path.basename(filename))
    with open(src, "rb") as f:
        data = f.read()
    if not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n" or data[8:12] == b"WEBP"):
        raise ValueError(f"{filename} is not an image")
    name = hashlib.sha1(data).hexdigest()[:20] + ".jpg"
    shutil.copyfile(src, os.path.join(IMAGES, name))
    return "images/" + name


def main():
    runs = sorted(glob.glob(os.path.join(DOWNLOADS, "pkb-*.json")), key=os.path.getmtime)
    runs = [r for r in runs if not os.path.basename(r).count("-") > 1]
    if not runs:
        sys.exit("No pkb-<run>.json in ~/Downloads: run tools/extract.js first")
    scraped = json.load(open(runs[-1]))["posts"]
    existing = json.load(open(FEED))["data"] if os.path.exists(FEED) else []
    by_id = {p["id"]: p for p in existing}
    raw = RAW.format(repo=repo_slug())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")

    fresh, added = [], 0
    for s in scraped:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        pid = post_id(text)
        old = by_id.pop(pid, None)
        pics = []
        for f in s.get("files", []):
            try:
                pics.append(raw + take_image(f))
            except Exception as e:
                print("image skipped:", e, file=sys.stderr)
        if not pics and old:
            pics = old.get("pictures") or []
        fresh.append({
            "id": pid,
            "message": text,
            "full_picture": pics[0] if pics else None,
            "pictures": pics,
            "permalink_url": s.get("link") or (old or {}).get("permalink_url") or PAGE_URL,
            "created_time": (old or {}).get("created_time") or now,
        })
        added += old is None

    # Scraped posts come newest first; previously seen posts that weren't re-scraped follow.
    data = (fresh + list(by_id.values()))[:KEEP]
    json.dump({"data": data, "updated": now}, open(FEED, "w"), ensure_ascii=False, indent=1)

    # Drop photos no longer referenced by any post.
    used = {u.rsplit("/", 1)[-1] for p in data for u in p.get("pictures") or []}
    for f in os.listdir(IMAGES):
        if f not in used and not f.startswith("."):
            os.remove(os.path.join(IMAGES, f))

    for f in glob.glob(os.path.join(DOWNLOADS, "pkb-*")):
        os.remove(f)

    print(f"{len(fresh)} scraped, {added} new, {len(data)} in feed")
    if "--push" in sys.argv:
        subprocess.run(["git", "-C", ROOT, "add", "-A"], check=True)
        if subprocess.run(["git", "-C", ROOT, "diff", "--cached", "--quiet"]).returncode:
            subprocess.run(["git", "-C", ROOT, "commit", "-qm", f"Feed update {now}: {added} new"], check=True)
            subprocess.run(["git", "-C", ROOT, "push", "-q", "origin", "main"], check=True)
            print("pushed")
        else:
            print("no changes")


if __name__ == "__main__":
    main()
