"""年度报告式翻页页面 out/wrapped-<年>.html：全屏分页、左右滑 / 点按 / 方向键翻页、手机优先。

用法：python3 scripts/build_wrapped.py --project <dir> [--year 2023]（缺省 = 聊天记录的最后一年）

页面：封面 → 这一年发了多少条 → 最热的一天 → 年度十大 → 每位成员一页（本年发言量、口头禅、本年名场面 1 件）→ 结尾。
数据只取 work/all.json 的统计、work/stable/ 的事件（和可选 work/top10.json）；不放聊天原文，
除非 config.pages.show_chat_groups 允许那个群——允许时名场面下面附该成员在那件事里的最多 2 句原话。
口头禅 = 本年里 ≤8 字、在 ≥3 个不同月份出现、共 ≥5 次的短句（统计口径，不是摘录）；纯笑声/问句不算，笑声单列「最爱的笑法」。
隐私闸门：写文件前扫大事记的输入（privacy_gate.enforce 'chronicle'），连同页面上脚本自拼的文字（口头禅、笑法、原话）一起扫；默认只提醒。
可选配置 config.pages.wrapped：{"end": "结尾页的一句话", "footer": "落款"}；结尾印章用 config.pages.share.seal（缺省「年鉴」）。
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import all_names, args, body, display, load_all, members, sender_key  # noqa: E402
from privacy_gate import enforce  # noqa: E402
from pagekit import TEMPLATES, author_title, esc, fill, font_css, pages, plain_text, site_name  # noqa: E402
from sharekit import catchphrases, favorite_laugh, hour_label, load_events, top_events  # noqa: E402

CAT_RANK = {'名场面': 0, '群内热议': 1, '人生节点': 2, '聚会出行': 3}


def main():
    a = args(__doc__, lambda p: p.add_argument('--year', help='哪一年，默认最后一年'))
    proj, cfg = a.project, a.cfg
    allm = load_all(a)
    year = a.year or allm[-1]['t'][:4]
    ym = [m for m in allm if m['t'][:4] == year]
    if not ym:
        sys.exit(f'{year} 年没有消息（聊天记录范围 {allm[0]["t"][:10]} ~ {allm[-1]["t"][:10]}）')
    pw = pages(cfg, 'wrapped')
    name = site_name(cfg)
    evs = load_events(proj, cfg) if (proj / 'work/stable').exists() else {}
    yev = [e for e in evs.values() if e['date'][:4] == year]
    if not evs:
        print('提示：没有 work/stable/，页面里没有事件（最热的一天、年度十大、名场面都会空着）')
    label_of = {g.get('key'): g.get('label') for g in cfg.get('groups', [])}
    show = {label_of.get(x, x) for x in pages(cfg).get('show_chat_groups', [])}
    by_key = {m['k']: m for m in allm}
    slides, said = [], []  # said：脚本自拼的文字，送隐私闸门

    def slide(cls, inner):
        slides.append(f'<section class="slide {cls}"><div class="in">{inner}</div></section>')

    # 封面
    slide('dark', f'<p class="k">{esc(name)} · 年度报告</p><h1 class="huge">{esc(year)}</h1>'
                  f'<p class="lede">这一年，我们在群里说过的话，都在这儿了。</p><p class="hint">点右边 · 左滑 → 下一页</p>')

    # 这一年
    days = collections.Counter(m['t'][:10] for m in ym)
    months = collections.Counter(m['t'][5:7] for m in ym)
    hot_m, hot_mn = months.most_common(1)[0]
    talkers = {m['s'] for m in ym}
    slide('paper', f'<p class="k">这一年</p><p class="lede">{esc(name)}一共发了</p><p class="big">{len(ym):,}</p><p class="unit">条消息</p>'
                   f'<p class="lede">有人说话的日子 <b>{len(days)}</b> 天，平均每天 <b>{len(ym) / len(days):.0f}</b> 条；'
                   f'最热闹的是 <b>{int(hot_m)} 月</b>（{hot_mn:,} 条）；<b>{len(talkers)}</b> 个人开过口。</p>')

    # 最热的一天
    hot_d, hot_n = days.most_common(1)[0]
    that = sorted((e for e in yev if e['date'] == hot_d), key=lambda e: -e['heat'])
    peak_h = collections.Counter(int(m['t'][11:13]) for m in ym if m['t'][:10] == hot_d).most_common(1)[0][0]
    slide('red', f'<p class="k">最热的一天</p><p class="big">{int(hot_d[5:7])}月{int(hot_d[8:10])}日</p>'
                 f'<p class="lede">这一天群里发了 {hot_n} 条，{esc(hour_label(peak_h))}最热闹。'
                 + ('那天在聊：</p><ul class="list">' + ''.join(f'<li>{esc(e["title"])}</li>' for e in that[:4]) + '</ul>'
                    if that else '那天的事没记进大事记。</p>'))

    # 年度十大
    tops = top_events(proj, evs, year)
    if tops:
        slide('paper', f'<p class="k">{esc(year)} 年度十大</p><ol class="top">'
                       + ''.join(f'<li><div>{esc(e["title"])}<small>{int(e["date"][5:7])}月{int(e["date"][8:10])}日 · {esc(e.get("category", ""))}</small></div></li>'
                                 for e, _ in tops) + '</ol>')

    # 每人一页
    talk = collections.Counter(display(cfg, m['s']) for m in ym)
    rank = {p: i + 1 for i, (p, _) in enumerate(talk.most_common())}
    roster = sorted((p for p in members(cfg, allm) if talk[p]), key=lambda p: -talk[p])
    used = set()
    for p in roster:
        s = sender_key(cfg, p)
        mine = [m for m in ym if m['s'] == s]
        phr = catchphrases(mine, names=all_names(cfg, allm))
        laugh = favorite_laugh(mine)
        said += [(f'{p} · 口头禅', w) for w in phr] + [(f'{p} · 笑法', laugh)]
        hours = collections.Counter(int(m['t'][11:13]) for m in mine)
        # 名场面：尽量每人不同——没被别人用过的优先，其次 TA 是主角（people 第一位）、人少的、名场面类、热度高的
        hot = sorted((e for e in yev if p in e['people']),
                     key=lambda e: (e['id'] in used, e['people'][0] != p, len(e['people']),
                                    CAT_RANK.get(e.get('category'), 9), -e['heat'], -len(e.get('refs', [])), e['date']))
        ev = ''
        if hot:
            e = hot[0]
            used.add(e['id'])
            chat = list(dict.fromkeys(body(by_key[r]['c']) for r in e.get('refs', [])
                                      if r in by_key and by_key[r]['g'] in show and by_key[r]['s'] == s))[:2]
            said += [(f'{p} · 原话', c) for c in chat]
            ev = (f'<p class="sec">本年名场面</p><div class="ev"><time>{int(e["date"][5:7])}月{int(e["date"][8:10])}日</time>'
                  f'<h3>{esc(e["title"])}</h3><p>{esc(e.get("summary", ""))}</p>'
                  + ''.join(f'<div class="chat"><b>{esc(p)}</b>{esc(c)}</div>' for c in chat if c) + '</div>')
        slide('paper', f'<p class="k">{esc(year)} · 第 {rank[p]} 话痨</p><h2 class="name">{esc(p)}</h2>'
                       f'<div class="row"><div><b>{talk[p]:,}</b><span>条发言</span></div>'
                       f'<div><b>{hours.most_common(1)[0][0]} 点</b><span>最常出没</span></div></div>'
                       + ('<p class="sec">口头禅</p><div class="chips">' + ''.join(f'<span>{esc(w)}</span>' for w in phr) + '</div>' if phr else '')
                       + (f'<p class="sec">最爱的笑法</p><div class="chips"><span>{esc(laugh)}</span></div>' if laugh else '')
                       + ev)

    # 结尾
    nxt = int(year) + 1
    slide('dark', f'<p class="k">{esc(year)} · 完</p><h2 class="huge" style="font-size:clamp(64px,20vw,120px)">明年见</h2>'
                  f'<p class="lede">{esc(pw.get("end", f"{nxt} 年，群还在，人还在，接着聊。"))}</p>'
                  f'<span class="seal">{esc(pages(cfg, "share").get("seal", "年鉴"))}</span>'
                  f'<p class="foot">{esc(pw.get("footer", f"据群聊记录整理，数字都是数出来的。记错了找{author_title(cfg)}。"))}</p>')

    enforce(proj, cfg, 'chronicle', texts=said)  # 隐私闸门：默认只提醒；严格模式下有重点命中就不写文件
    page = fill((TEMPLATES / 'wrapped.html').read_text(encoding='utf-8'),
                {'TITLE': esc(f'{name} · {year} 年度报告'), 'SLIDES': '\n'.join(slides)})
    text = plain_text(page)
    page = page.replace('/*FONTS*/', font_css(proj, cfg, {'Ink': text, 'Hand': text, 'Brush': text}))
    out = proj / 'out' / f'wrapped-{year}.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding='utf-8')
    print(f'{year}：{len(ym)} 条，{len(slides)} 页（成员 {len(roster)} 人，十大 {len(tops)} 件，'
          f'原文 {"允许：" + "、".join(sorted(show)) if show else "不放"}）→ {out}（{out.stat().st_size // 1024} KB）')


if __name__ == '__main__':
    main()
