"""把 out/stories/*.md 排成一页小剧场 out/stories.html，并导出 txt 合集到 out/stories-txt/。

用法：python3 scripts/build_stories.py --project <dir>

- 篇目按文件名排序（建议 01-标题.md、02-标题.md）；文件名以 _ 开头的、CAST.md 不算篇目。
- 类型（武侠/推理/…）取值顺序：md 头部 `---\\ngenre: 武侠\\n---` → config.pages.stories.genre {"01": "武侠"}
  → 文件名 `01-武侠-标题.md` 的中间一段。都没有就不显示类型标签。
- 可选 out/stories/CAST.md：Markdown 表格，只展示「化名」列和「称呼/外号」列（真名列一律不上页面）。
- 正文约定：`# 标题`、紧跟 `> 一句话导语`；群聊体对话行 `**HH:MM 名字**：内容`；
  `## 彩蛋注释`（标题含「彩蛋」）之后的内容折叠显示。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from privacy_gate import enforce
from pagekit import (TEMPLATES, author_title, cn_num, esc, fill, font_css, inline, load_project, pages,
                     plain_text, render_md, site_name, split_front, tabs_html, text_len, title_spans, back_link, TAB_LABELS)

proj, cfg = load_project(__doc__)
enforce(proj, cfg, 'stories')  # 隐私闸门：默认只提醒不拦；config.privacy.strict 时有重点命中就中止（scripts/privacy_gate.py）
ps = pages(cfg, 'stories')
SRC, OUT = proj / 'out/stories', proj / 'out'
files = [f for f in sorted(SRC.glob('*.md')) if f.name != 'CAST.md' and not f.name.startswith('_')]
if not files:
    sys.exit(f'{SRC} 里没有故事 md')


def parse_cast(path):
    """从 CAST.md 的第一张表里取 (化名, 称呼)；没有「化名」列就整张表不用，免得把真名列放上页面。"""
    if not path.exists():
        return []
    rows = [[c.strip() for c in line.strip().strip('|').split('|')] for line in path.read_text().split('\n') if line.strip().startswith('|')]
    if len(rows) < 2:
        return []
    head = rows[0]
    name_col = next((i for i, h in enumerate(head) if '化名' in h), None)
    nick_col = next((i for i, h in enumerate(head) if '称呼' in h or '外号' in h), None)
    if name_col is None:
        print('CAST.md 表头里没有「化名」列，人物表不展示'); return []
    cast = []
    for r in rows[1:]:
        if all(set(c) <= set('-: ') for c in r) or len(r) <= name_col or not r[name_col]:
            continue
        nick = ''
        if nick_col is not None and nick_col < len(r):
            parts = [p.strip() for p in re.split(r'[、,，/]', re.sub(r'[（(][^）)]*[）)]', '', r[nick_col])) if p.strip()]
            nick = ' · '.join(parts[:2])
        cast.append((r[name_col], nick))
    return cast


def md_to_txt(title, md):
    out = [f'《{title}》', '']
    for line in md.split('\n'):
        s = line.rstrip()
        if s.startswith('# '):
            continue
        if s.startswith('#'):
            s = '【' + s.lstrip('# ') + '】'
        elif s.strip() == '---':
            s = '＊　＊　＊'
        elif s.startswith('>'):
            s = s.lstrip('>').strip()
        elif s.startswith('- '):
            s = '· ' + s[2:]
        s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
        s = re.sub(r'(?<![\w*])\*([^*\n]+?)\*(?!\*)', r'\1', s)
        out.append(s)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip() + '\n'


genre_map = ps.get('genre') or {}
stories = []
for k, f in enumerate(files):
    meta, md = split_front(f.read_text())
    m = re.match(r'^(\d+)', f.stem)
    no = m.group(1) if m else str(k + 1)
    parts = f.stem.split('-')
    genre = meta.get('genre') or meta.get('类型') or genre_map.get(no) or (parts[1] if len(parts) >= 3 else '')
    title, blurb, body, egg = render_md(md, f.stem, egg='彩蛋')
    stories.append(dict(id=f's{no}', no=no, genre=genre, title=title, blurb=blurb, body=body, egg=egg,
                        chars=text_len(body), txt=md_to_txt(title, md), stem=f.stem))


def spans(n):
    """6 列网格里每张卡占几列：尽量整行铺满（余 2 张时前两张占半行，余 1 张时首尾各两张占半行）。"""
    if n == 1:
        return [6]
    s = [2] * n
    if n % 3 in (1, 2):
        s[0] = s[1] = 3
    if n % 3 == 1 and n >= 4:
        s[-1] = s[-2] = 3
    return s


def tag(s, k):
    return f'{esc(s["genre"])} · 第{cn_num(k + 1)}篇' if s['genre'] else f'第{cn_num(k + 1)}篇'


toc = ''.join(f'''<a class="card" href="#{s['id']}" style="--i:{k};--span:{sp}"><span class="no">{cn_num(k + 1)}</span>
{f'<span class="g">{esc(s["genre"])}</span>' if s['genre'] else ''}<h3>{esc(s['title'])}</h3><p>{inline(s['blurb'])}</p><small>约 {max(round(s['chars'], -2), 100):,} 字</small></a>'''
              for k, (s, sp) in enumerate(zip(stories, spans(len(stories)))))
secs = ''.join(f'''<article class="story" id="{s['id']}" data-t="{esc(s['title'])}">
<header><span class="g">{tag(s, k)}</span><h2>{esc(s['title'])}</h2><p class="blurb">{inline(s['blurb'])}</p></header>
<div class="body">{s['body']}</div>
{f'<details class="egg"><summary>彩蛋注释 · 这篇里埋了哪些真梗</summary>{s["egg"]}</details>' if s['egg'] else ''}
<nav class="next">{f'<a href="#{stories[k + 1]["id"]}">下一篇 · {esc(stories[k + 1]["title"])} →</a>' if k + 1 < len(stories) else '<a href="#top">回到目录 ↑</a>'}</nav>
</article>''' for k, s in enumerate(stories))

cast = parse_cast(SRC / 'CAST.md')
cast_html = ''
if cast:
    cast_html = (f'<div class="kicker"><h2>人物表</h2><span>{esc(ps.get("cast_hint", "名字都换了个写法，认出来算你眼尖"))}</span></div>\n'
                 '<ul class="cast">' + ''.join(f'<li><b>{esc(a)}</b><span>{esc(b)}</span></li>' for a, b in cast) + '</ul>\n'
                 + (f'<p class="cast-note">{esc(ps["cast_note"])}</p>\n' if ps.get('cast_note') else ''))

name = site_name(cfg)
seal = ps.get('seal') or (pages(cfg).get('tabs') or {}).get('stories') or TAB_LABELS['stories']
genres = list(dict.fromkeys(s['genre'] for s in stories if s['genre']))
page = fill((TEMPLATES / 'stories.html').read_text(), {
    'TITLE': esc(ps.get('title', name + seal)), 'NAME': title_spans(name), 'NAME_N': len(name), 'SEAL': esc(seal),
    'BACK': back_link(cfg, OUT),
    'TABS': tabs_html(cfg, 'stories', OUT),
    'HERO': ps.get('hero') or f'群聊里长出来的<b>{cn_num(len(stories)) if len(stories) < 100 else len(stories)}个故事</b>。人有原型，事是编的。',
    'GENRES': esc('　'.join(genres)), 'CAST': cast_html, 'TOC': toc, 'STORIES': secs,
    'FOOTER': esc(ps.get('footer', f'据群聊记录改编，人物有原型，情节纯属虚构。哪里写得不像，找{author_title(cfg)}说一声。')),
})
plain = plain_text(page)
page = page.replace('/*FONTS*/', font_css(proj, cfg, {'Ink': plain, 'Hand': plain,
                                                     'Brush': name + seal + '未完待续人物表目录' + ''.join(s['title'] for s in stories) + cn_num(len(stories))}))
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'stories.html').write_text(page)

# txt 合集：每篇一个，外加一份全部合在一起的
txt_dir = OUT / 'stories-txt'
txt_dir.mkdir(exist_ok=True)
for old in txt_dir.glob('*.txt'):
    old.unlink()
for s in stories:
    (txt_dir / f'{s["stem"]}.txt').write_text(s['txt'])
(txt_dir / f'00-{name}{seal}-合集.txt').write_text('\n\n\n'.join(s['txt'] for s in stories))
print(f'{len(stories)} 篇，人物表 {len(cast)} 人 → {OUT / "stories.html"}（{(OUT / "stories.html").stat().st_size // 1024} KB），txt → {txt_dir}')
