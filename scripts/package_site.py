"""把 out/ 下的单文件页面打包成登录版网站（Cloudflare Worker + 静态资源）。

用法：python3 scripts/package_site.py --project <dir>
（site/wrangler.toml 的 [build] 会在 wrangler dev / deploy 前自动调用它，参数是 --project ..）

- 第一次运行会建 <项目>/site/：复制 src/index.js、src/app.js、wrangler.toml（已存在的不覆盖）。
- 大事记拆成懒加载：data/index.<hash>.json（目录、年度十大、三张榜）、data/months/ 按月事件、
  data/chat/ 每件事的聊天片段（只有单文件版里带了原文的才有）、data/events 搜索索引。
- 字体从页面里抽成 assets/*.<hash>.woff2（可长期缓存）；小剧场、人物志整页同样处理。
- 数据页（build_stats.py 出的 out/stats.html）：内嵌数据抽成 data/stats.<hash>.json、脚本抽成 assets/stats.<hash>.js、
  字体同样抽出，路由 /stats。
- 顶部栏目：大事记 / 小剧场 / 人物志 / 数据，只显示 out/ 里存在的页面；早先生成的页面导航里缺的栏目会补上。
- 删掉上次打包留下、这次没再引用的哈希文件。
- 打包前过隐私闸门（默认只列出疑似隐私问题供你过目，不拦；严格模式见 references/09-privacy.md）；
  回收过本人确认结果（可选）的，打一行汇总提醒。
"""
import base64
import collections
import hashlib
import json
import re
import shlex
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from privacy_gate import enforce, review_note
from pagekit import SKILL, esc, TAB_FILES, TAB_LABELS, TAB_LABELS_EN, load_project, pages, site_name

proj, cfg = load_project(__doc__)
# 隐私闸门：默认只提醒不拦；config.privacy.strict 时有重点命中就中止（scripts/privacy_gate.py）
enforce(proj, cfg, 'site')
review_note(proj)
OUT, SITE = proj / 'out', proj / 'site'
PUBLIC = SITE / 'public'

# ---------- 第一次：建 site/ ----------
for rel in ['src/index.js', 'src/app.js']:
    if not (SITE / rel).exists():
        (SITE / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(SKILL / 'assets/site' / rel, SITE / rel)
        print('新建', SITE / rel)
if not (SITE / 'wrangler.toml').exists():
    slug = re.sub(r'[^a-z0-9-]+', '-', (cfg.get('worker_name') or 'group-chronicle').lower()).strip('-') or 'group-chronicle'
    toml_str = lambda s: s.replace('\\', '\\\\').replace('"', '\\"')
    text = (SKILL / 'assets/site/wrangler.toml.example').read_text()
    text = text.replace('__WORKER_NAME__', slug).replace('__SITE_NAME__', toml_str(site_name(cfg)))
    text = text.replace('__SITE_TITLE__', toml_str(cfg.get('title') or site_name(cfg)))
    text = text.replace('__PACKAGE_SCRIPT__', toml_str(shlex.quote(str(SKILL / 'scripts/package_site.py'))))
    (SITE / 'wrangler.toml').write_text(text)
    print('新建', SITE / 'wrangler.toml')
if not (SITE / '.gitignore').exists():
    (SITE / '.gitignore').write_text('public/\n.wrangler/\n.dev.vars\nnode_modules/\n')

source_path = OUT / 'chronicle.html'
if not source_path.exists():
    sys.exit(f'没有 {source_path}，先跑 build_chronicle.py')
PUBLIC.mkdir(parents=True, exist_ok=True)
source = source_path.read_text()
data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', source, re.S).group(1))
ROUTES = {'chronicle.html': '/', 'stories.html': '/stories', 'people.html': '/people', 'stats.html': '/stats'}
TAB_KEY = {f: k for k, f in TAB_FILES.items()}
TAB_TEXT = {**(TAB_LABELS_EN if cfg.get('lang') == 'en' else TAB_LABELS), **(pages(cfg).get('tabs') or {})}
present = {f for f in ROUTES if (OUT / f).exists()}
emitted = set()


def emit(folder, name, extension, content):
    blob = content.encode() if isinstance(content, str) else content
    digest = hashlib.sha256(blob).hexdigest()[:16]
    path = PUBLIC / folder / f'{name}.{digest}.{extension}'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != blob:
        path.write_bytes(blob)
    emitted.add(path)
    return '/' + path.relative_to(PUBLIC).as_posix()


def emit_json(folder, name, value):
    return emit(folder, name, 'json', json.dumps(value, ensure_ascii=False, separators=(',', ':')))


def write_if_changed(path, text):
    if not path.exists() or path.read_text() != text:
        path.write_text(text)


def site_links(page, current):
    """单文件版之间的相对链接 → 站内路径；没生成的栏目从顶部切换里去掉，后生成的栏目补进导航。"""
    if '<!--site-tabs-->' in page and len(present) > 1:  # 生成时只有这一页、没出导航
        page = page.replace('<!--site-tabs-->', '<nav class="site-tabs" aria-label="栏目"></nav>', 1)
    nav = re.search(r'<nav class="site-tabs"[^>]*>.*?</nav>', page, re.S)
    if nav:
        cur = ' aria-current="page"'
        add = ''.join(f'<a href="{f}" data-tab="{TAB_KEY[f]}"{cur if f == current else ""}>{esc(TAB_TEXT[TAB_KEY[f]])}</a>' for f in ROUTES
                      if f in present and f'data-tab="{TAB_KEY[f]}"' not in nav.group())
        page = page.replace(nav.group(), nav.group()[:-len('</nav>')] + add + '</nav>', 1)
    for file, route in ROUTES.items():
        if file in present:
            page = page.replace(f'href="{file}"', f'href="{route}"')
        else:
            page = re.sub(rf'<a href="{re.escape(file)}" data-tab="\w+">[^<]*</a>', '', page)
    return page


FACE = re.compile(r"@font-face\{font-family:'(\w+)';src:url\(data:font/woff2;base64,([A-Za-z0-9+/=]+)\)([^}]*)\}")

# ---------- 大事记：字体 ----------
fonts = {}
for name, encoded, suffix in FACE.findall(source):
    fonts[name] = f"@font-face{{font-family:'{name}';src:url('{emit('assets', name.lower(), 'woff2', base64.b64decode(encoded))}'){suffix}}}"
reading_fonts = fonts.get('Ink', '') + fonts.get('Hand', '')
font_css_url = emit('assets', 'reading-fonts', 'css', reading_fonts) if reading_fonts else ''

# ---------- 大事记：数据 ----------
manifest = {'activity': data['activity'], 'months': [], 'people': {}, 'eventCount': 0, 'majorCount': 0, 'top': data.get('top', {})}
search_rows = []
for month in data['months']:
    events, counts = [], collections.Counter()
    for original in month['events']:
        event = {k: v for k, v in original.items() if k != 'ex'}
        event['chat'] = emit_json('data/chat', event['id'], original['ex']) if original.get('ex') else None
        events.append(event)
        search_rows.append([event['id'], event['date'], event['category'], event['heat'], event['title'], event['summary'], event['people']])
        manifest['eventCount'] += 1
        manifest['majorCount'] += event['heat'] == 3
        for person in sorted(set(event['people'])):
            manifest['people'][person] = manifest['people'].get(person, 0) + 1
        # 每种筛选组合（类别 × 只看大事 × 人）下这个月有几件，前端据此跳过空月份、不用先下载
        for category in ['', event['category']]:
            for major in ([0, 1] if event['heat'] == 3 else [0]):
                for person in ['', *sorted(set(event['people']))]:
                    counts[json.dumps([category, major, person], ensure_ascii=False, separators=(',', ':'))] += 1
    events.sort(key=lambda e: (e['heat'] != 3, e['date']))
    manifest['months'].append({'month': month['month'], 'summary': month['summary'], 'count': month['count'],
                               'eventCount': len(events), 'counts': dict(counts),
                               'url': emit_json('data/months', month['month'], events)})
manifest['events'] = emit_json('data', 'events', search_rows)  # 第一次搜索时才载入
manifest_url = emit_json('data', 'index', manifest)
app_url = emit('assets', 'app', 'js', (SITE / 'src/app.js').read_bytes())

# ---------- 大事记：页面 ----------
page = FACE.sub('', source)
page = re.sub(r'<script type="application/json" id="data">.*?</script>\n?', '', page, flags=re.S)
page = re.sub(r'<script>.*?</script>', f'<script src="{app_url}" defer></script>', page, flags=re.S)
page = page.replace('<html lang="zh-CN">', f'<html lang="zh-CN" data-index="{manifest_url}" data-fonts="{font_css_url}">')
page = page.replace('<style>', '<style>' + fonts.get('Brush', ''), 1)
page = page.replace('</style>', '''
.month{content-visibility:auto;contain-intrinsic-size:auto 1200px}
.ev,.ev.k-meme{opacity:1;transform:none;transition:none}
.ev.k-meme{transform:rotate(var(--r))}
.title span{opacity:1;filter:none;transform:none;animation:none}
.hero .seal{opacity:.93;transform:rotate(-8deg);animation:none}
.page-status{max-width:1240px;margin:20px auto;padding:20px var(--gut);text-align:center;color:var(--ink-3)}
.page-status button{display:inline-block;border:1px solid var(--rule);border-radius:4px;padding:10px 24px;background:var(--paper-hi)}
.page-status button:disabled{cursor:wait;opacity:.6}
.page-status p{margin-bottom:10px}
.page-status a{color:var(--zhu)}
.sheet[aria-hidden="true"]{visibility:hidden}
.sheet.on{visibility:visible}
.bar-wrap{position:relative}
.now{opacity:1;transform:none;cursor:pointer;align-items:center;padding:6px 14px 6px 0}
.now i{width:0;height:0;border:4.5px solid transparent;border-top:5px solid var(--ink-3);margin-top:5px;transition:transform .2s}
.now[aria-expanded="true"] i{transform:rotate(180deg) translateY(5px)}
.tpanel{position:absolute;top:calc(100% + 1px);left:var(--gut);z-index:60;width:min(600px,calc(100vw - 2*var(--gut)));max-height:min(70svh,560px);overflow-y:auto;
  background:var(--paper-hi);border:1px solid var(--rule);border-radius:4px;box-shadow:0 18px 40px -16px rgba(80,60,30,.45);padding:10px 14px}
.tpanel[hidden]{display:none}
.tp-top{display:flex;justify-content:space-between;align-items:center;font:400 13px var(--hand);color:var(--ink-3);padding:2px 2px 10px;border-bottom:1px solid var(--rule)}
.tp-top button,.from-note button{font:700 13px var(--serif);color:var(--zhu);letter-spacing:.1em}
.tp-y{display:grid;grid-template-columns:52px minmax(0,1fr);align-items:center;gap:8px;padding:6px 0;border-bottom:1px dashed var(--rule)}
.tp-y:last-child{border:0}
.tp-yr{font:900 17px var(--serif);text-align:left}
.tp-ms{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:4px}
.tp-ms button{font:600 13px/1 var(--serif);padding:8px 0;border-radius:3px}
.tp-ms button:hover{background:var(--zhu-soft)}
.tp-ms button.dim{color:var(--ink-3);opacity:.5}
.tp-ms button.cur{background:var(--zhu);color:var(--paper-hi);opacity:1}
.sbtn{flex:none;display:flex;align-items:center;gap:6px;font:700 14px/1 var(--serif);letter-spacing:.1em;padding:8px 0 8px 14px;border-left:1px solid var(--rule)}
.sbtn svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:2}
.srch{height:86svh}
.sq{display:flex;padding-right:44px}
.sq input{flex:1;min-width:0;font:400 16px var(--sans);padding:9px 12px;border:1.5px solid var(--rule);border-radius:6px;background:var(--paper-hi);color:var(--ink);outline:none}
.sq input:focus{border-color:var(--zhu)}
.sq-tip{font:400 14px/1.8 var(--hand);color:var(--ink-3);padding:4px 4px 10px}
.sq-tip button{color:var(--zhu);border-bottom:1px solid currentColor;margin-left:6px}
.sr{display:block;width:100%;text-align:left;padding:10px 6px;border-bottom:1px dashed var(--rule)}
.sr:hover{background:var(--zhu-soft)}
.sr-meta{font:400 12px var(--sans);color:var(--ink-3)}
.sr-c{font:400 14.5px/1.6 var(--sans);color:var(--ink);word-break:break-word}
.sb mark{background:rgba(181,50,29,.2);color:inherit;border-radius:2px}
.sb-more{display:block;margin:16px auto;border:1px solid var(--rule);border-radius:4px;padding:9px 22px;background:var(--paper-hi)}
.sr-t{font:900 16px/1.4 var(--serif);margin:2px 0}
.sr-p{font:600 12px/1.6 var(--serif);color:var(--ink-3);margin-top:2px}
.ev{outline:3px solid transparent;outline-offset:5px}
.ev,.ev.k-meme{transition:outline-color .8s}
.ev.flash{outline-color:var(--zhu)}
.top{max-width:1240px;margin:0 auto;padding:64px var(--gut) 40px}
.top h2{font:900 13px/1 var(--serif);letter-spacing:.5em;color:var(--zhu);margin-bottom:6px}
.top>p{font:400 15px/1.7 var(--hand);color:var(--ink-2);margin-bottom:14px}
.top-tabs{display:flex;gap:18px;overflow-x:auto;scrollbar-width:none;border-bottom:1px solid var(--rule);margin-bottom:22px}
.top-tabs::-webkit-scrollbar{display:none}
.top-note{font:400 13px var(--hand);color:var(--ink-3);margin:-12px 0 12px}
.top-body{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:20px 44px;align-items:start}
.top-list{list-style:none}
.top-ev{display:grid;grid-template-columns:52px minmax(0,1fr);gap:2px 14px;width:100%;text-align:left;padding:14px 4px;border-bottom:1px dashed var(--rule)}
.top-ev:hover{background:var(--zhu-soft)}
.top-n{grid-row:1/4;font:200 42px/1 var(--serif);color:var(--ink-3);text-align:right}
.top-list li:nth-child(-n+3) .top-n{color:var(--zhu);font-weight:900}
.top-m{font:400 12px var(--sans);color:var(--ink-3);letter-spacing:.05em}
.top-t{font:900 19px/1.4 var(--serif)}
.top-r{font:400 15px/1.7 var(--hand);color:var(--ink-2)}
.boards{display:flex;flex-direction:column;gap:20px}
.board{background:var(--paper-hi);padding:16px 20px;border-radius:2px;box-shadow:0 1px 2px rgba(80,60,30,.08),0 10px 24px -14px rgba(80,60,30,.35)}
.board h4{font:900 16px/1.6 var(--serif);letter-spacing:.2em}
.board small{display:block;font:400 12px var(--hand);color:var(--ink-3);margin-bottom:6px}
.br{display:grid;grid-template-columns:16px 6em minmax(0,1fr) auto;align-items:center;gap:8px;font:600 14px/2 var(--serif)}
.br span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.br b{font:400 12px var(--sans);color:var(--ink-3)}
.br i{display:block;height:6px;border-radius:3px;background:var(--zhu);opacity:.45}
.br:first-of-type i{opacity:.9}
.br em{font:400 12px var(--sans);color:var(--ink-3);font-style:normal}
@media (max-width:860px){.top-body{grid-template-columns:minmax(0,1fr)}}
.from-note{display:flex;justify-content:center;gap:14px;align-items:baseline;padding-top:28px;font:400 14px var(--hand);color:var(--ink-3)}
@media (max-width:640px){.sbtn span{display:none}.sbtn{padding-left:10px}.tp-ms{grid-template-columns:repeat(6,minmax(0,1fr))}.now{padding-right:10px}.now b{font-size:18px}.now span{font-size:13px}}
</style>''', 1)


def must_replace(text, old, new):
    assert text.count(old) == 1, f'模板结构变了，找不到：{old[:60]}'
    return text.replace(old, new)


page = must_replace(page, '<div class="now" id="now"><b></b><span></span></div>',
                    '<button class="now" id="now" type="button" aria-label="按时间跳转" aria-haspopup="true" aria-expanded="false" aria-controls="tpanel"><b></b><span></span><i></i></button><div class="tpanel" id="tpanel" hidden></div>')
page = must_replace(page, '<nav class="bar">', '''<section class="top" id="top">
  <h2>年 度 十 大</h2>
  <p>每年挑出最有分量的十件事，再加三张榜。点一件事，跳到时间线里它在的地方。</p>
  <div class="top-tabs" id="top-tabs"></div>
  <div id="top-body"></div>
</section>

<nav class="bar">''')
page = must_replace(page, '</div></div></nav>', '</div><button class="sbtn" id="sbtn" type="button" aria-label="搜索事件"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5"/></svg><span>搜索</span></button></div></nav>')
sheet_end = '<div class="sb" id="shb"></div>\n</div>'
page = must_replace(page, sheet_end, sheet_end + '''
<div class="sheet srch" id="srch" role="dialog" aria-modal="true" aria-hidden="true" aria-label="搜索事件">
  <div class="sh"><div class="sq"><input id="sq" type="search" placeholder="搜事件：标题、经过、人名" enterkeyhint="search" autocomplete="off"></div><button class="x" id="sqx" aria-label="关闭">×</button></div>
  <div class="sb" id="sqb"></div>
</div>''')
page = must_replace(page, '<main id="list"></main>', '''<main id="list" aria-label="大事记"></main>
<div class="page-status" id="page-status" role="status" aria-live="polite"><p>正在载入大事记…</p></div>
<noscript><p class="page-status">请开启 JavaScript 以浏览大事记。</p></noscript>''')
page = must_replace(page, 'id="sheet" role="dialog" aria-modal="true"', 'id="sheet" role="dialog" aria-modal="true" aria-hidden="true" aria-labelledby="sht"')
write_if_changed(PUBLIC / 'chronicle.html', site_links(page, 'chronicle.html'))

# ---------- 小剧场、人物志：整页，内嵌字体抽成带哈希的文件 ----------
for file, prefix in [('stories.html', 'stories'), ('people.html', 'people')]:
    target = PUBLIC / file
    if file not in present:
        target.unlink(missing_ok=True)
        continue
    standalone = (OUT / file).read_text()
    standalone = FACE.sub(lambda m: f"@font-face{{font-family:'{m.group(1)}';src:url('"
                          + emit('assets', f'{prefix}-{m.group(1).lower()}', 'woff2', base64.b64decode(m.group(2)))
                          + f"'){m.group(3)}}}", standalone)
    write_if_changed(target, site_links(standalone, file))

# ---------- 数据页：内嵌的统计数据、脚本、字体都抽成带哈希的文件 ----------
if 'stats.html' in present:
    stats_page = (OUT / 'stats.html').read_text()
    data_tag = re.search(r'<script type="application/json" id="data">(.*?)</script>\n?', stats_page, re.S)
    script_tag = re.search(r'<script>(.*?)</script>', stats_page, re.S)
    assert data_tag and script_tag and 'data-stats=""' in stats_page, '数据页模板结构变了，重跑 build_stats.py'
    stats_url = emit('data', 'stats', 'json', data_tag.group(1))
    stats_js = emit('assets', 'stats', 'js', script_tag.group(1).replace('<\\/script', '</script'))
    stats_page = stats_page.replace(data_tag.group(0), '').replace(script_tag.group(0), f'<script src="{stats_js}" defer></script>')
    stats_page = stats_page.replace('data-stats=""', f'data-stats="{stats_url}"', 1)
    stats_page = FACE.sub(lambda m: f"@font-face{{font-family:'{m.group(1)}';src:url('"
                          + emit('assets', f'stats-{m.group(1).lower()}', 'woff2', base64.b64decode(m.group(2)))
                          + f"'){m.group(3)}}}", stats_page)
    write_if_changed(PUBLIC / 'stats.html', site_links(stats_page, 'stats.html'))
else:
    (PUBLIC / 'stats.html').unlink(missing_ok=True)

# 删掉上次打包留下、这次没再引用的带哈希文件，免得旧版本跟着部署上去
stale = [f for d in ['assets', 'data'] for f in (PUBLIC / d).rglob('*') if f.is_file() and f not in emitted]
for f in stale:
    f.unlink()
print(json.dumps({'pages': sorted(present), 'chronicle_bytes': (PUBLIC / 'chronicle.html').stat().st_size,
                  'index': manifest_url, 'months': len(manifest['months']), 'events': manifest['eventCount'],
                  'chat_snippets': sum(1 for p in emitted if '/data/chat/' in p.as_posix()),
                  'fonts': sorted(fonts), 'removed_stale': len(stale)}, ensure_ascii=False))
