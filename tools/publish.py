#!/usr/bin/env python3
"""Merge freshly scraped Facebook posts into posts.json and copy their photos.

Usage: python3 -I tools/publish.py [--push]

Chrome can only save into ~/Downloads itself, so the FIRST thing this does is move every
pkb-* file there into ~/Downloads/पसल किनबेच Facebook/<date time>/, one folder per run
(named from when that run was saved), and folders older than KEEP_DAYS (7) are deleted. Nothing is left loose in Downloads, even if a later
step such as git fails. It then builds the feed from the newest run folder.

Run it with DEVELOPER_DIR=/Library/Developer/CommandLineTools so an Xcode update waiting for
its licence to be accepted can't block python3 or git.

posts.json uses the Graph API `/{page}/posts` shape the app already reads:
  {"data": [{"id", "message", "full_picture", "pictures", "permalink_url", "created_time"}]}
Facebook's own image links expire after a few days, so every photo is downloaded into
images/ and served from this repo instead.
"""
import glob, hashlib, json, os, shutil, subprocess, sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = os.path.join(ROOT, "posts.json")
IMAGES = os.path.join(ROOT, "images")
RAW = "https://raw.githubusercontent.com/{repo}/main/"
PAGE_URL = "https://www.facebook.com/pasalkinbech.com.np"
KEEP = 80  # newest posts kept in the feed


GIT_ENV = dict(os.environ, DEVELOPER_DIR="/Library/Developer/CommandLineTools") \
    if os.path.isdir("/Library/Developer/CommandLineTools") else None


def git(*args, check=True, **kw):
    return subprocess.run(["git", "-C", ROOT, *args], env=GIT_ENV, check=check, **kw)


def repo_slug():
    url = git("remote", "get-url", "origin", capture_output=True, text=True).stdout.strip()
    return url.removesuffix(".git").split("github.com/")[-1].lstrip(":")


def post_id(text):
    # Posts often have no visible permalink, so the id is a hash of the opening text.
    norm = " ".join(text.split())[:300]
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


DOWNLOADS = os.path.expanduser("~/Downloads")
ARCHIVE = os.path.join(DOWNLOADS, "पसल किनबेच Facebook")
KEEP_DAYS = 7  # run folders older than this are deleted; the published feed lives in the repo


def archive_downloads():
    """Moves every pkb-* file out of ~/Downloads into one dated folder per run."""
    moved = 0
    for js in glob.glob(os.path.join(DOWNLOADS, "pkb-*.json")):
        run = os.path.basename(js)[4:-5]
        stamp = datetime.fromtimestamp(os.path.getmtime(js)).strftime("%Y-%m-%d %H.%M")
        run_dir = os.path.join(ARCHIVE, stamp)
        os.makedirs(run_dir, exist_ok=True)
        for f in [js] + glob.glob(os.path.join(DOWNLOADS, f"pkb-{run}-*")):
            shutil.move(f, os.path.join(run_dir, os.path.basename(f)))
            moved += 1
    strays = glob.glob(os.path.join(DOWNLOADS, "pkb-*"))  # photos whose run file never arrived
    if strays:
        run_dir = os.path.join(ARCHIVE, "unsorted")
        os.makedirs(run_dir, exist_ok=True)
        for f in strays:
            shutil.move(f, os.path.join(run_dir, os.path.basename(f)))
            moved += 1
    return moved


def prune_archive(newest):
    """Deletes run folders (and unsorted strays) older than KEEP_DAYS, never the newest run."""
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    removed = []
    for d in glob.glob(os.path.join(ARCHIVE, "*")):
        name = os.path.basename(d)
        if not os.path.isdir(d) or d == newest:
            continue
        if name == "unsorted":
            for f in glob.glob(os.path.join(d, "pkb-*")):
                if datetime.fromtimestamp(os.path.getmtime(f)) < cutoff:
                    os.remove(f)
            continue
        try:
            stamp = datetime.strptime(name, "%Y-%m-%d %H.%M")  # only folders this script created
        except ValueError:
            continue
        if stamp < cutoff and all(os.path.basename(f).startswith("pkb-") for f in os.listdir(d)):
            shutil.rmtree(d)
            removed.append(name)
    return removed


def newest_run():
    runs = glob.glob(os.path.join(ARCHIVE, "*", "pkb-*.json"))
    return max(runs, key=os.path.getmtime) if runs else None


def take_image(run_dir, filename):
    """Copies a downloaded photo into images/, named by content so repeats dedupe."""
    src = os.path.join(run_dir, os.path.basename(filename))
    with open(src, "rb") as f:
        data = f.read()
    if not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n" or data[8:12] == b"WEBP"):
        raise ValueError(f"{filename} is not an image")
    name = hashlib.sha1(data).hexdigest()[:20] + ".jpg"
    shutil.copyfile(src, os.path.join(IMAGES, name))
    return "images/" + name


def main():
    print(f"moved {archive_downloads()} files out of Downloads into {ARCHIVE}")
    run_json = newest_run()
    if not run_json:
        sys.exit("No scraped run found: run tools/extract.js first")
    run_dir = os.path.dirname(run_json)
    print("building feed from", run_dir)
    removed = prune_archive(run_dir)
    if removed:
        print(f"deleted run folders older than {KEEP_DAYS} days:", ", ".join(removed))
    if "--push" in sys.argv:
        git("pull", "-q", "--rebase", "--autostash")
    scraped = json.load(open(run_json))["posts"]
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
                pics.append(raw + take_image(run_dir, f))
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

    print(f"{len(fresh)} scraped, {added} new, {len(data)} in feed")
    if "--push" in sys.argv:
        git("add", "-A")
        if git("diff", "--cached", "--quiet", check=False).returncode:
            git("commit", "-qm", f"Feed update {now}: {added} new\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
            git("push", "-q", "origin", "main")
            print("pushed")
        else:
            print("no changes")


if __name__ == "__main__":
    main()
