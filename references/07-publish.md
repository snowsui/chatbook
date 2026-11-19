# ⑦ 发布（登录版网站）

目标：群友用一个共享账号密码登录，看大事记（按月懒加载、搜索、年度十大）、小剧场、人物志、数据四个栏目（有哪个页面就出哪个栏目）。

## 方案

Cloudflare Worker + 静态资源（`[assets]` + `run_worker_first = true`，所有请求先过 Worker 鉴权）：
- 自写登录页，HMAC 签名 cookie（HttpOnly; Secure; SameSite=Lax），用户名/密码常数时间比较；未登录访问数据和资源返回 401。
- `python3 scripts/package_site.py --project <dir>`：把单文件大事记拆成 按月 JSON、事件搜索索引、年度十大、群友榜；小剧场/人物志整页拷入并把内嵌字体抽成带哈希的独立文件（`Cache-Control: immutable`）；数据页（`out/stats.html`，见 15-stats-dashboard.md）的内嵌数据、脚本、字体抽成带哈希的文件，路由 `/stats`；先生成的页面导航里缺的栏目打包时补上；清理旧哈希文件。第一次运行时自动建 `site/`，之后 wrangler.toml 的 `[build]` 自动调用它。
- 模板与说明：assets/site/（src/index.js、src/app.js、wrangler.toml.example、README.md）。

## 步骤

1. 跑 `python3 <skill>/scripts/package_site.py --project <dir>`：第一次会自动生成 `<project>/site/`（复制 src/index.js、src/app.js，按 config 生成 wrangler.toml 和 .gitignore；已存在的文件不覆盖），并把 out/ 下的页面打包进 `site/public/`。之后 `wrangler dev` / `wrangler deploy` 会通过 `[build]` 自动重新打包。需要改 Worker 名、绑自定义域名时编辑 `site/wrangler.toml`（见 assets/site/README.md 第 4 节）。
2. 在 `site/` 里 `npx wrangler secret put USER / PASS / SECRET`（账号密码由用户定，不要写进任何文件或日志）。
3. 本地测试：`site/.dev.vars` 写测试用 USER/PASS/SECRET，`npx wrangler dev`，用浏览器（或 Playwright）测登录、栏目切换（最多四栏：大事记/小剧场/人物志/数据，有哪个页面出哪个）、手机宽度无横向滚动；**测完删掉 .dev.vars**。
4. 部署前：package_site 开头会自动跑隐私闸门（也会把已生成的 html 再查一遍），把列出的疑似隐私问题给用户过目，改不改由用户决定；回收过本人确认结果（可选）的，会打一行汇总提醒。不想放某人的小传，把那篇挪出 out/portraits/ 后重跑 build_portraits.py。见 references/09-privacy.md。
5. 部署：在 `site/` 里 `npx wrangler deploy`。**部署是对外发布，先征得用户同意。**
6. 上线后请用户实际打开确认（自动化访问可能被安全验证拦住）。

## 常见问题

- **访问慢、手机打不开**：先看域名的 Cloudflare 安全级别，处理办法见 assets/site/README.md 第 4 节。再看页面体积：内嵌字体的整页要抽成独立文件（package_site 会自动抽）。
- **改了内容不生效**：确认改的是数据源（stable/ 或 out/*.md）并重新 build；单文件版和网站版是两条构建线。
- **只想发给群里看**：txt 合集（小剧场）、单文件 HTML、分享卡片 PNG 都能直接发，不一定要上线。单文件默认不加密，发给谁由用户决定；要放到免费静态托管（GitHub Pages / Vercel / Netlify）做公开链接时，可用 `build_locked.py` 给链接加访问口令（口令另走渠道；安全边界和托管选型见 references/11-share-hosting.md）。
