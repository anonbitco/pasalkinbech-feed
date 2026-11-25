// Run in a logged-in Chrome tab on https://www.facebook.com/pasalkinbech.com.np
// (Claude in Chrome's javascript tool). Saves into ~/Downloads:
//   pkb-<run>.json            {run, posts:[{text, link, files:[...]}]}
//   pkb-<run>-<post>-<n>.jpg  each post's photos (Facebook's own links expire)
// and returns a short summary. Then: python3 -I tools/publish.py --push
// (which moves these files into ~/Downloads/पसल किनबेच Facebook/<date time>/).
// Facebook's markup changes often; if this finds 0 posts, the selectors are the place to look.
await (async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const POSTS_WANTED = 15;
  const run = Date.now().toString(36);
  const save = (blob, name) => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
  };
  // Turns Facebook's timestamp text into an ISO time, or null if it isn't one.
  const postedAt = t => {
    const now = new Date();
    let m = t.match(/^(\d+)\s*(m|min|mins|h|hr|hrs|d|w)$/i);
    if (/^just now$/i.test(t)) return now.toISOString();
    if (m) {
      const mins = { m: 1, min: 1, mins: 1, h: 60, hr: 60, hrs: 60, d: 1440, w: 10080 }[m[2].toLowerCase()];
      return new Date(now - m[1] * mins * 60000).toISOString();
    }
    const clock = (d, s) => {
      const c = s && s.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
      if (c) d.setHours((+c[1] % 12) + (/pm/i.test(c[3]) ? 12 : 0), +c[2], 0, 0); else d.setHours(12, 0, 0, 0);
      return d;
    };
    if ((m = t.match(/^Yesterday(?: at (.+))?$/i))) {
      const d = new Date(now); d.setDate(d.getDate() - 1); return clock(d, m[1]).toISOString();
    }
    if ((m = t.match(/^([A-Z][a-z]+) (\d{1,2})(?:, (\d{4}))?(?: at (.+))?$/))) {
      const d = new Date(`${m[1]} ${m[2]}, ${m[3] || now.getFullYear()}`);
      if (isNaN(d)) return null;
      if (!m[3] && d > now) d.setFullYear(d.getFullYear() - 1);
      return clock(d, m[4]).toISOString();
    }
    return null;
  };
  const container = el => { let c = el; while (c && c.parentElement) { c = c.parentElement; if (c.querySelector('[data-ad-rendering-role="like_button"]')) return c; } return null; };

  const found = [], done = new Set();
  window.scrollTo(0, 0); await sleep(1500);
  for (let round = 0; round < 25 && found.length < POSTS_WANTED; round++) {
    for (const m of document.querySelectorAll('[data-ad-rendering-role="story_message"]')) {
      const c = container(m);
      if (!c || done.has(c)) continue;
      done.add(c);
      m.scrollIntoView({ block: 'center' }); await sleep(1300);
      for (const b of c.querySelectorAll('[role="button"]')) if (b.innerText.trim() === 'See more') { b.click(); await sleep(400); }
      // Facebook fills in the timestamp's real permalink only on hover.
      for (const a of c.querySelectorAll('a')) {
        if (/hashtag/.test(a.getAttribute('href') || '')) continue;
        ['pointerover', 'mouseover', 'mouseenter', 'focus'].forEach(t => a.dispatchEvent(new MouseEvent(t, { bubbles: true })));
      }
      await sleep(700);
      const hrefs = [...c.querySelectorAll('a')].map(a => a.href.split('?')[0]);
      const link = hrefs.find(h => /\/posts\/pfbid|\/posts\/\d/.test(h)) || hrefs.find(h => /\/reel\/\d|\/videos\/\d/.test(h)) || null;
      const images = [...new Set([
        ...[...c.querySelectorAll('img')].filter(i => i.naturalWidth >= 250 && /fbcdn/.test(i.src)).map(i => i.src),
        ...[...c.querySelectorAll('video')].map(v => v.poster).filter(Boolean),
      ])].slice(0, 4);
      const text = m.innerText.trim().replace(/\s*See less$/, '');
      // The timestamp link reads "52m", "23h", "3d", "Yesterday at 3:30 PM" or "November 18 at 3:30 PM".
      const stamp = [...c.querySelectorAll('a')]
        .filter(a => /\/posts\/|\/reel\/|\/videos\/|\/photos?\//.test(a.href))
        .map(a => a.innerText.trim()).find(t => postedAt(t));
      if (text) found.push({ text, link, images, time: stamp ? postedAt(stamp) : null });
      if (found.length >= POSTS_WANTED) break;
    }
    window.scrollBy(0, 2500); await sleep(1800);
  }

  const posts = [];
  let photos = 0;
  for (const [pi, p] of found.entries()) {
    const files = [];
    for (const [ii, u] of p.images.entries()) {
      try {
        const b = await (await fetch(u)).blob();
        if (!b.type.startsWith('image/')) continue;
        const name = `pkb-${run}-${pi}-${ii}.jpg`;
        save(b, name); files.push(name); photos++;
        await sleep(350);
      } catch (e) { /* skip this photo */ }
    }
    posts.push({ text: p.text, link: p.link, time: p.time, files });
  }
  await sleep(500);
  save(new Blob([JSON.stringify({ run, posts })], { type: 'application/json' }), `pkb-${run}.json`);
  return { run, posts: posts.length, photos, withLink: posts.filter(p => p.link).length, withTime: posts.filter(p => p.time).length };
})()
