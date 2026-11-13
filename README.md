# pasalkinbech-feed

Posts from facebook.com/pasalkinbech.com.np, refreshed twice a day, for the Pasal Kinbech app.

- `posts.json`: newest posts in Facebook Graph API shape
- `images/`: copies of post photos (Facebook's own links expire)
- `tools/extract.js`: runs in a logged-in Chrome tab on the page and returns the posts
- `tools/publish.py --push`: merges the run from ~/Downloads, copies photos, commits and pushes; the run's raw files are kept in `~/Downloads/पसल किनबेच Facebook/<date time>/`
