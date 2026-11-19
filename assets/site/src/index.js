// 群聊大事记登录版：账号密码登录后才能看任何页面、数据和字体。
// USER / PASS / SECRET 用 `wrangler secret put` 配置；SITE_NAME / SITE_TITLE 在 wrangler.toml 的 [vars] 里。
const COOKIE = 'gcc_session';
const MAX_AGE = 60 * 60 * 24 * 30;
const PAGES = new Set(['/', '/stories', '/people', '/stats']);

async function sign(secret, msg) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(msg));
  return btoa(String.fromCharCode(...new Uint8Array(sig))).replace(/[+/=]/g, c => ({ '+': '-', '/': '_', '=': '' }[c]));
}

// 先各自哈希再定长比较，避免按字节提前返回泄露时序（也顺带抹平长度差异）
async function same(a, b) {
  const [x, y] = await Promise.all([a, b].map(v => crypto.subtle.digest('SHA-256', new TextEncoder().encode(String(v ?? '')))));
  const u = new Uint8Array(x), v = new Uint8Array(y);
  let diff = 0;
  for (let i = 0; i < u.length; i++) diff |= u[i] ^ v[i];
  return diff === 0;
}

async function validSession(req, env) {
  const m = (req.headers.get('Cookie') || '').match(new RegExp('(?:^|;\\s*)' + COOKIE + '=([^;]+)'));
  if (!m) return false;
  try {
    const [exp, sig, extra] = decodeURIComponent(m[1]).split('.');
    if (extra || !/^\d{1,12}$/.test(exp || '') || !/^[\w-]{43}$/.test(sig || '') || Date.now() / 1000 >= Number(exp)) return false;
    return await same(sig, await sign(env.SECRET, exp));
  } catch {
    return false;
  }
}

const headers = { 'Content-Type': 'text/html; charset=utf-8', 'X-Robots-Tag': 'noindex, nofollow', 'Cache-Control': 'no-store' };
const escapeHtml = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function loginPage(env, error) {
  const name = escapeHtml(env.SITE_NAME || '大事记');
  const title = escapeHtml(env.SITE_TITLE || env.SITE_NAME || '大事记');
  return new Response(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>${title}</title><style>
:root{--paper:#f2e9d6;--ink:#1c1915;--ink-3:#8a8172;--zhu:#b5321d;--rule:rgba(28,25,21,.14)}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--paper) radial-gradient(ellipse at 50% 40%,#f7f0e1 0,var(--paper) 60%,#e6dbc3 100%);color:var(--ink);
font-family:"Songti SC","Noto Serif SC","Source Han Serif SC",serif;display:grid;place-items:center;padding:16px}
form{width:min(340px,100%);text-align:center}
h1{writing-mode:vertical-rl;margin:0 auto 28px;font:900 52px/1.05 inherit;letter-spacing:.12em;height:auto;max-height:60vh}
.seal{display:inline-block;border:2px solid var(--zhu);color:var(--zhu);font:700 13px/1 inherit;letter-spacing:.3em;padding:6px 4px 6px 8px;margin-bottom:32px;transform:rotate(-4deg)}
label{display:block;text-align:left;font-size:13px;letter-spacing:.2em;color:var(--ink-3);margin:18px 0 6px}
input{width:100%;font:500 17px inherit;color:var(--ink);background:transparent;border:0;border-bottom:1.5px solid var(--ink);padding:8px 2px;outline:0;border-radius:0}
input:focus{border-color:var(--zhu)}
button{margin-top:30px;width:100%;font:700 16px inherit;letter-spacing:.5em;padding:12px 0 12px .5em;background:var(--ink);color:var(--paper);border:0;border-radius:3px;cursor:pointer}
button:active{background:var(--zhu)}
.err{color:var(--zhu);font-size:14px;margin-top:16px;min-height:1em}
</style></head><body><form method="post" action="/login">
<h1>${name}</h1><div class="seal">大事记</div>
<label for="u">账号</label><input id="u" name="u" autocomplete="username" autocapitalize="off" required>
<label for="p">密码</label><input id="p" name="p" type="password" autocomplete="current-password" required>
<button type="submit">进入</button><div class="err">${error ? '账号或密码不对' : ''}</div>
</form></body></html>`, { status: error ? 401 : 200, headers });
}

export default {
  async fetch(req, env) {
    // 没配齐 secret 时一律拒绝：否则空账号空密码也能比对成功
    if (!env.USER || !env.PASS || !env.SECRET) {
      return new Response('站点还没配置 USER / PASS / SECRET', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' } });
    }
    const url = new URL(req.url);
    if (url.pathname === '/login' && req.method === 'POST') {
      let f;
      try { f = await req.formData(); } catch { return loginPage(env, true); }
      const [userOk, passOk] = await Promise.all([same(f.get('u'), env.USER), same(f.get('p'), env.PASS)]);
      // 账号或密码不对：等约 1 秒再回，拖慢在线猜密码（不引入 KV/DO，只是单次请求的延迟）
      if (!(userOk && passOk)) await new Promise(r => setTimeout(r, 1000));
      if (userOk && passOk) {
        const exp = String(Math.floor(Date.now() / 1000) + MAX_AGE);
        const token = exp + '.' + await sign(env.SECRET, exp);
        return new Response(null, { status: 303, headers: {
          Location: '/', 'Set-Cookie': `${COOKIE}=${token}; Path=/; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Lax` } });
      }
      return loginPage(env, true);
    }
    if (url.pathname === '/logout') {
      return new Response(null, { status: 303, headers: { Location: '/', 'Set-Cookie': `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax` } });
    }
    const dataRequest = url.pathname.startsWith('/data/');
    const assetRequest = url.pathname.startsWith('/assets/');
    if (!(await validSession(req, env))) {
      if (dataRequest || assetRequest) return Response.json({ error: '请先登录' }, { status: 401, headers: { 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow' } });
      return loginPage(env, false);
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD', 'Cache-Control': 'no-store' } });
    if (!PAGES.has(url.pathname) && !dataRequest && !assetRequest) return Response.redirect(url.origin + '/', 302);
    const target = new URL(req.url);
    if (url.pathname === '/') target.pathname = '/chronicle';
    const res = await env.ASSETS.fetch(new Request(target, req));
    const responseHeaders = new Headers(res.headers);
    responseHeaders.set('X-Robots-Tag', 'noindex, nofollow');
    // 带哈希的字体/脚本可以长期缓存；页面和数据每次都校验
    responseHeaders.set('Cache-Control', assetRequest && (res.ok || res.status === 304) ? 'private, max-age=31536000, immutable' : 'private, no-cache');
    return new Response(res.body, { status: res.status, statusText: res.statusText, headers: responseHeaders });
  },
};
