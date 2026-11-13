// Run in a logged-in Chrome tab on https://www.facebook.com/pasalkinbech.com.np
// (Claude in Chrome's javascript tool). Saves into ~/Downloads:
//   pkb-<run>.json            {run, posts:[{text, link, files:[...]}]}
//   pkb-<run>-<post>-<n>.jpg  each post's photos (Facebook's own links expire)
// and returns a short summary. Then: python3 -I tools/publish.py --push
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
      if (text) found.push({ text, link, images });
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
    posts.push({ text: p.text, link: p.link, files });
  }
  await sleep(500);
  save(new Blob([JSON.stringify({ run, posts })], { type: 'application/json' }), `pkb-${run}.json`);
  return { run, posts: posts.length, photos, withLink: posts.filter(p => p.link).length };
})()
