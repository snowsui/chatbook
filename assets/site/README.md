# 登录版网站（Cloudflare Worker）

把 `out/chronicle.html`、`out/stories.html`、`out/people.html`、`out/stats.html` 打包成一个**要账号密码才能看**的网站：

- `/` 大事记（按月懒加载、时间跳转面板、事件搜索、年度十大与三张榜、聊天片段抽屉）
- `/stories` 小剧场、`/people` 人物志（整页，单篇阅读模式）
- `/stats` 数据页（build_stats.py；数据与脚本抽成带哈希的文件）
- 顶部栏目切换只显示实际生成了的页面
- 所有请求（页面、`/data/*`、`/assets/*` 字体脚本）都先过 Worker 鉴权；登录态是 HMAC 签名的 HttpOnly cookie，30 天有效，比对用常数时间
- 账号或密码输错时延迟约 1 秒才返回，拖慢在线猜密码；这只是单次请求的延迟，不做按 IP 计数封禁，密码仍要设得够长
- 带哈希的字体/脚本 `immutable` 长期缓存，页面和数据每次校验

## 0. 页面相关配置（chronicle.config.json，全部可选）

```json
{
  "title": "某某群大事记",
  "author_title": "史官",
  "worker_name": "my-group-chronicle",
  "fonts": {"ink": "...", "hand": "...", "brush": "..."},
  "pages": {
    "name": "某某群",
    "show_chat_groups": [],
    "tabs": {"chronicle": "大事记", "stories": "小剧场", "portraits": "人物志"},
    "chronicle": {"seal": "大事记", "end_seal": "某某", "lede_tail": "生日、聚会……", "hidden_note": "※ 聊在别的群里，原文不公开", "footer": "..."},
    "stories": {"title": "...", "seal": "小剧场", "hero": "可含 <b>", "genre": {"01": "武侠"}, "cast_hint": "...", "cast_note": "...", "footer": "..."},
    "portraits": {"title": "...", "seal": "人物志", "hero": "可含 <b>", "hero_side": "N 个人　一个群", "order": ["显示名"], "section": "列传", "section_note": "...", "footer": "..."}
  }
}
```

- `pages.name`：竖排书法大标题，2–4 字最好看；缺省取 `title` 去掉结尾的「大事记」。
- `pages.show_chat_groups`：哪些群的**聊天原文**可以出现在大事记里（群的 key 或 label）。默认空 = 一条原文都不放，只放事件。原文一旦放进去，能登录的人都看得到——只放全体看客本来就在的群。
- `author_title`：人物志里「X曰」评语框和落款用的称呼。
- `pages.portraits.hero`：人物志封面导语；缺省按篇数自动措辞（一篇时写“替 TA 写了一篇小传”，多篇时写“替 N 位群友各写了一篇小传”）。
- `fonts`：不配也能用（页面退回系统字体，构建时会打印一行提示）；字体来源见 `assets/fonts/README.md`。

## 1. 生成与打包

```bash
python3 <skill>/scripts/build_chronicle.py --project <dir>
python3 <skill>/scripts/build_stories.py   --project <dir>   # 可选
python3 <skill>/scripts/build_portraits.py --project <dir>   # 可选
python3 <skill>/scripts/build_stats.py     --project <dir>   # 可选：数据页
python3 <skill>/scripts/package_site.py    --project <dir>
```

（所有脚本也可以直接把项目目录写成第一个参数。）单文件版的顶部栏目只列出 `out/` 里已经生成的页面；后来才生成的栏目，要把早先的页面重新 build 一次才会出现在它们的导航里（网站版打包时会自动按实际存在的页面处理）。

第一次跑 `package_site.py` 会建 `<项目>/site/`：`src/index.js`、`src/app.js`、`wrangler.toml`、`.gitignore`（已存在的文件不覆盖；想换成 skill 里的新版，删掉对应文件再跑一次）。产物在 `site/public/`，每次打包会清掉不再引用的旧哈希文件。

之后 `wrangler dev` / `wrangler deploy` 会通过 `[build]` 自动重新打包，不必手动跑最后一步。

## 2. 账号密码（secrets）

在 `site/` 目录里：

```bash
npx wrangler secret put USER     # 登录账号
npx wrangler secret put PASS     # 登录密码
npx wrangler secret put SECRET   # 签 cookie 的随机串，例如 openssl rand -base64 32 的输出
```

三个都必须设，缺任何一个 Worker 一律返回 503（防止空账号空密码被放行）。改 `SECRET` 会让所有人的登录失效；改密码不会，要强制下线就连 `SECRET` 一起换。

## 3. 本地测试

```bash
cd site
cat > .dev.vars <<'EOF'
USER=test
PASS=test
SECRET=local-only-random-string
EOF
npx wrangler dev        # 打开 http://localhost:8787 ，用 test/test 登录
rm .dev.vars            # 测完就删，别留着明文密码，也别提交
```

`.dev.vars` 已在 `site/.gitignore` 里。

## 4. 部署与自定义域名

```bash
cd site && npx wrangler deploy
```

默认部署到 `<worker_name>.<你的账号>.workers.dev`（同样要登录）。**群友在中国大陆时，`workers.dev` 基本打不开，必须用自己的子域**（不需要 ICP 备案），部署后用手机流量在微信里实测一次。要用自己的子域：

1. 域名要托管在同一个 Cloudflare 账号下；
2. 编辑 `site/wrangler.toml`：`workers_dev = false`，取消 `routes` 注释，`pattern` 改成你的子域（如 `chronicle.example.com`），`custom_domain = true` 会自动建 DNS 记录和证书；
3. 再 `npx wrangler deploy`。

**如果这个域名的安全级别开着 Under Attack（“我正在遭受攻击”）**：访客会先被 JS 质询页拦住，手机浏览器和链接预览常常卡死、登录表单 POST 也可能失败。到 Cloudflare 后台 → 该域名 → Rules → **Configuration Rules** 新建一条：条件 `Hostname equals chronicle.example.com`，设置 **Security Level = Essentially Off（或 Low）**，只对这个子域放行；站点本身有登录保护。

## 5. 隐私提醒

- package_site 打包时会列出疑似隐私问题供你过目，默认只提醒、开 `privacy.strict` 才拦（references/09-privacy.md 第二节）；回收过本人确认结果（可选）的，会打一行汇总提醒。
- 页面带 `noindex`，但这不是保密手段，保密靠登录。账号密码只发给群里的人。
- `site/public/` 是生成物，已被 `.gitignore` 忽略；不要把它、`out/` 或 `work/` 提交到公开仓库。
