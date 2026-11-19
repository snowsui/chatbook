"""给 config.people 每人出一张手机转发用的竖版卡片（1080×1920 PNG + 同款 HTML），再出一张群体总卡。

用法：python3 scripts/build_share_cards.py --project <dir> [--person 张三 ...] [--year 2023] [--no-png]

读：work/all.json（口头禅：≤8 字、≥3 个不同月份、共 ≥5 次的短句，不含纯笑声/问句；笑声单列「最爱的笑法」）、
    work/stats/<人>.md（先跑 person_stats.py）、work/metrics.md（可选）、
    out/portraits/<人>.md（品藻 = 第二行 `> …`；代表性原话 = 文中第一句能核对上本人原文的「…」）、
    work/stable/ 与可选 work/top10.json（总卡的年度十大前 5）。
写：out/cards/<人>.html/.png、out/cards/_group.html/.png（模板 assets/templates/share_card.html）。
PNG 需要 Python 版 Playwright（pip install playwright && python3 -m playwright install chromium）；没装就只出 HTML。
可选配置 config.pages.share：{"quote": {"张三": "手选的一句原话"}, "seal": "印章字（缺省「年鉴」）"}。
手选的原话同样要能核对上本人某条消息，核对不上就退回人物志里的引语。
隐私闸门：构建前扫人物志与大事记的输入（privacy_gate.enforce 'portraits' + 'chronicle'），连同卡片上脚本自拼的文字
（口头禅、笑法、原话、品藻、事件标题）一起扫，命中只提醒（严格模式下有重点命中就不写文件）。人物志里的引语出处标注 <!--k:…--> 会去掉。
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import all_names, args, display, load_all, members, people, safe, sender_key  # noqa: E402
from privacy_gate import enforce  # noqa: E402
from pagekit import TEMPLATES, esc, fill, font_css, pages, plain_text, site_name, split_front  # noqa: E402
from sharekit import (STRIP, catchphrases, favorite_laugh, group_age, hour_label, load_events, metrics_row,  # noqa: E402
                      parse_stats, screenshot, top_events, verified_quote)

W, H = 1080, 1920


def main():
    def extra(p):
        p.add_argument('--person', nargs='*', help='只出这些人的卡')
        p.add_argument('--year', help='总卡「年度十大」取哪一年，默认最后一年')
        p.add_argument('--no-png', action='store_true', help='只出 HTML，不截图')
    a = args(__doc__, extra)
    proj, cfg = a.project, a.cfg
    allm = load_all(a)
    sc = pages(cfg, 'share')
    name = site_name(cfg)
    y0, y1 = allm[0]['t'][:4], allm[-1]['t'][:4]
    span = y0 if y0 == y1 else f'{y0}–{y1}'
    seal = sc.get('seal', '年鉴')
    out = proj / 'out/cards'
    out.mkdir(parents=True, exist_ok=True)
    tpl = (TEMPLATES / 'share_card.html').read_text(encoding='utf-8')
    talk = collections.Counter(display(cfg, m['s']) for m in allm)
    rank = {p: i + 1 for i, (p, _) in enumerate(talk.most_common())}
    foot = (f'<div class="foot"><div class="g">{esc(name)}<small>{esc(span)} · 群聊年鉴</small></div>'
            f'<div class="seal">{esc(seal)}</div></div>')
    made, pending, said = [], [], []  # said：卡片上脚本自拼的文字，送隐私闸门

    def write(stem, title, card, brush, kind='person'):
        pending.append((stem, title, card, brush, kind))

    for p in people(cfg, a.person):
        sf = a.work / 'stats' / f'{safe(p)}.md'
        if not sf.exists():
            print(f'{p}: 没有 {sf}，先跑 person_stats.py --person {p}；跳过')
            continue
        st = parse_stats(sf)
        pf = proj / 'out/portraits' / f'{p}.md'
        md = STRIP.sub('', split_front(pf.read_text(encoding='utf-8'))[1]) if pf.exists() else ''
        lines = md.split('\n')
        pz = lines[1][2:].strip() if len(lines) > 1 and lines[1].startswith('> ') else ''
        if not pf.exists():
            print(f'  {p}：没有人物志 {pf}，卡片不放品藻')
        hour = max(st['hours'], key=st['hours'].get) if st['hours'] else None
        mine = [m for m in allm if m['s'] == sender_key(cfg, p)]
        phr = catchphrases(mine, names=all_names(cfg, allm))
        laugh = favorite_laugh(mine)
        near = st['near'][0][0] if st['near'] else ''
        q = verified_quote(cfg, allm, p, md, (sc.get('quote') or {}).get(p))
        cells = [f'<div><span class="k">发言</span><b>{st["total"]:,}</b><small>条 · 全群第 {rank.get(p, "-")}</small></div>']
        if hour is not None:
            cells.append(f'<div><span class="k">最活跃</span><b>{hour}</b><small>点 · {esc(hour_label(hour))}</small></div>')
        if phr:
            cells.append('<div class="full"><span class="k">口头禅</span><div class="chips">'
                         + ''.join(f'<span>{esc(w)}</span>' for w in phr) + '</div></div>')
        if laugh:
            cells.append(f'<div class="full"><span class="k">最爱的笑法</span><b>{esc(laugh)}</b></div>')
        if near:
            cells.append(f'<div class="full"><span class="k">最常一起聊的人</span><b>{esc(near)}</b></div>')
        card = (f'<div class="kicker">{esc(name)} · 人物志</div>'
                f'<h1 class="name{" long" if len(p) > 3 else ""}">{esc(p)}</h1>'
                + (f'<p class="pz">{esc(pz)}</p>' if pz else '')
                + '<div class="grid">' + ''.join(cells) + '</div>'
                + (f'<blockquote class="quote{" l" if len(q[0]) > 40 else ""}"><p>{esc(q[0])}</p><cite>—— {esc(p)}，{q[1]}</cite></blockquote>' if q else '')
                + foot)
        write(safe(p), f'{p} · {name}', card, p + seal + '0123456789')
        said += [(f'卡片 {p} · 口头禅', w) for w in phr] + [(f'卡片 {p} · 笑法', laugh), (f'卡片 {p} · 品藻', pz),
                                                           (f'卡片 {p} · 原话', q[0] if q else '')]
        print(f'{p}: 发言 {st["total"]}，口头禅 {"、".join(phr) or "-"}，原话 {"有" if q else "无（人物志里没有能核对上的引语）"}')

    # ---------- 群体总卡 ----------
    counts = {k: int(v) for k, v in metrics_row(proj, '消息总数').items() if v.isdigit()}
    if not counts:  # 没跑 metrics.py 就直接从 all.json 数
        counts = {p: talk[p] for p in members(cfg, allm)}
    ms = sorted(counts.items(), key=lambda x: -x[1])
    peak = max(counts.values() or [1])
    year = a.year or y1
    tops = top_events(proj, load_events(proj, cfg), year) if (proj / 'work/stable').exists() else []
    card = (f'<div class="kicker">{esc(span)} · 群聊年鉴</div>'
            f'<h1 class="name{" long" if len(name) > 3 else ""}">{esc(name)}</h1>'
            f'<div class="big"><div><b>{len(allm):,}</b><span>条消息</span></div>'
            f'<div><b>{esc(group_age(allm[0]["t"], allm[-1]["t"]))}</b><span>群龄</span></div></div>'
            '<h2 class="h">谁说得最多</h2><ul class="bars">'
            + ''.join(f'<li><span>{esc(p)}</span><i style="width:{max(2, round(100 * n / peak))}%"></i><em>{n:,}</em></li>' for p, n in ms[:8])
            + '</ul>'
            + (f'<h2 class="h">{esc(year)} 年度十大 · 前五</h2><ol class="top5">'
               + ''.join(f'<li><div>{esc(e["title"])}<small>{e["date"]}</small></div></li>' for e, _ in tops[:5]) + '</ol>' if tops else '')
            + foot)
    write('_group', f'{name} · 群聊年鉴', card, name + seal + '0123456789', 'group')
    said += [(f'总卡 · 年度十大 {e["date"]}', e['title']) for e, _ in tops[:5]]

    enforce(proj, cfg, ['portraits', 'chronicle'], texts=said)  # 隐私闸门：默认只提醒；严格模式下有重点命中就不写文件
    for stem, title, card, brush, kind in pending:
        page = fill(tpl, {'TITLE': esc(title), 'CARD': card, 'KIND': kind})
        text = plain_text(page)
        page = page.replace('/*FONTS*/', font_css(proj, cfg, {'Ink': text, 'Hand': text, 'Brush': brush}))
        f = out / f'{stem}.html'
        f.write_text(page, encoding='utf-8')
        made.append(f)
    print(f'总卡：{len(allm)} 条，{len(ms)} 人，{year} 年度十大 {len(tops[:5])} 件')

    if not a.no_png and screenshot([(f, f.with_suffix('.png')) for f in made], W, H):
        print(f'PNG {len(made)} 张')
    print(f'→ {out}')


if __name__ == '__main__':
    main()
