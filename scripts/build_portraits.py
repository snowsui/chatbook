"""把 out/portraits/*.md 排成一页人物志 out/people.html。

用法：python3 scripts/build_portraits.py --project <dir>

- 一人一个 md，文件名 = 统一显示名（与 config.people 一致）；文件名以 _ 开头的跳过。
- 顺序：config.pages.portraits.order 列出的在前，其余按 work/all.json 里的发言条数从多到少。
- 正文约定：`# 称呼`、紧跟 `> 一句品藻`；`## {author_title}曰` 起一个评语框（到 --- 结束）；`## 数据卡` 起数据框。
  author_title 在 config 顶层配置，缺省「史官」。
- 可配置文案（config.pages.portraits）：title / seal / hero / hero_side / section / section_note / footer。
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from privacy_gate import enforce, review_note
from pagekit import (TEMPLATES, TAB_LABELS, author_title, back_link, cn_num, esc, fill, font_css, inline, load_project, pages,
                     plain_text, render_md, site_name, split_front, tabs_html, text_len, title_spans)

proj, cfg = load_project(__doc__)
enforce(proj, cfg, 'portraits')  # 隐私闸门：默认只提醒不拦；config.privacy.strict 时有重点命中就中止（scripts/privacy_gate.py）
review_note(proj)  # 回收过本人确认（可选）时打一行汇总提醒
pp = pages(cfg, 'portraits')
SRC, OUT = proj / 'out/portraits', proj / 'out'
files = {f.stem: f for f in sorted(SRC.glob('*.md')) if not f.name.startswith('_')}
if not files:
    sys.exit(f'{SRC} 里没有小传 md')
author = author_title(cfg)
me = cfg.get('me') or ''

talk = collections.Counter()
if (proj / 'work/all.json').exists():
    talk = collections.Counter(me if m['s'] == 'me' else m['s'] for m in json.load(open(proj / 'work/all.json')))
order = [k for k in pp.get('order', []) if k in files]
order += sorted((k for k in files if k not in order), key=lambda k: (-talk[k], k))

boxes = {f'{author}曰': ('shi', f'<h2>{esc(author)}曰</h2>'), '数据卡': ('datacard', '<h4>数据卡</h4>')}
if author != '史官':
    boxes['史官曰'] = boxes[f'{author}曰']
people = []
for key in order:
    _, md = split_front(files[key].read_text())
    title, blurb, body, _ = render_md(md, key, boxes=boxes)
    people.append(dict(id=f'p{len(people) + 1}', title=title, blurb=blurb, body=body, chars=text_len(body)))

ppl = ''.join(f'''<li><a href="#{p['id']}" style="--i:{k}"><span class="no">{cn_num(k + 1)}</span><span class="nm">{esc(p['title'])}</span>
<span class="pz">{inline(p['blurb'])}</span><small>约 {max(round(p['chars'], -2), 100):,} 字</small></a></li>''' for k, p in enumerate(people))
secs = ''.join(f'''<article class="story" id="{p['id']}" data-t="{esc(p['title'])}">
<header><span class="g">{esc(pp.get('section', '列传'))} · 第{cn_num(k + 1)}</span><h2>{esc(p['title'])}</h2><p class="blurb">{inline(p['blurb'])}</p></header>
<div class="body">{p['body']}</div>
<nav class="next">{f'<a href="#{people[k + 1]["id"]}">下一位 · {esc(people[k + 1]["title"])} →</a>' if k + 1 < len(people) else '<a href="#top">回到目录 ↑</a>'}</nav>
</article>''' for k, p in enumerate(people))

name = site_name(cfg)
tabs = pages(cfg).get('tabs') or {}
seal = pp.get('seal') or tabs.get('portraits') or TAB_LABELS['portraits']
n = len(people)
page = fill((TEMPLATES / 'portraits.html').read_text(), {
    'TITLE': esc(pp.get('title', name + seal)), 'NAME': title_spans(name), 'NAME_N': len(name), 'SEAL': esc(seal),
    'BACK': back_link(cfg, OUT), 'TABS': tabs_html(cfg, 'portraits', OUT),
    'HERO': pp.get('hero') or (f'{esc(author)}把{esc(people[0]["title"])}在群里的每一句话逐行读完，替<b>TA 写了一篇小传</b>。事都是真的，话都是原话。'
                               if n == 1 else f'{esc(author)}把群里的聊天逐行读完，替<b>{cn_num(n) if n < 100 else n}位群友各写了一篇小传</b>。事都是真的，话都是原话。'),
    'HERO_SIDE': esc(pp.get('hero_side', f'{cn_num(n) if n < 100 else n}个人　一个群')),
    'SECTION': esc(pp.get('section', '列传')),
    'SECTION_NOTE': esc(pp.get('section_note', f'按发言条数排序；每篇末尾有“{author}曰”和数据卡')),
    'PPL': ppl, 'STORIES': secs, 'END': esc(f'{author}曰'),
    'FOOTER': esc(pp.get('footer', f'事都是真的，话都是原话，日期都对得上。写得不像的地方，是{author}眼拙。')),
})
plain = plain_text(page)
brush = name + seal + author + '曰未完待续' + pp.get('section', '列传') + ''.join(p['title'] for p in people) + ''.join(cn_num(k + 1) for k in range(n))
page = page.replace('/*FONTS*/', font_css(proj, cfg, {'Ink': plain, 'Hand': plain, 'Brush': brush}))
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'people.html').write_text(page)
print(f'{n} 人（{"、".join(p["title"] for p in people)}）→ {OUT / "people.html"}（{(OUT / "people.html").stat().st_size // 1024} KB）')
