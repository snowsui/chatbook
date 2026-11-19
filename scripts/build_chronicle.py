"""把 work/stable/*.json 排成大事记单文件版 out/chronicle.html。

用法：python3 scripts/build_chronicle.py --project <dir>

读：chronicle.config.json、work/all.json、work/stable/*.json、可选 work/top10.json
原文片段：默认一条都不展示，只展示事件；config.pages.show_chat_groups 列出的群（key 或 label 都行）
才会在事件卡片上出现「翻当时的聊天」。
年度十大：work/top10.json 形如 {"2020": [{"id": "E:2020-05-3", "reason": "入选理由"}]}，
id 是「E:月份-该月 stable 文件里的序号」（同修订清单的 key）；没有这个文件就按热度自动挑。
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from privacy_gate import enforce
from pagekit import (TEMPLATES, author_title, cn_year, esc, fill, font_css, load_project, pages,
                     plain_text, site_name, tabs_html, title_spans)

proj, cfg = load_project(__doc__)
enforce(proj, cfg, 'chronicle')  # 隐私闸门：默认只提醒不拦；config.privacy.strict 时有重点命中就中止（scripts/privacy_gate.py）
W, OUT = proj / 'work', proj / 'out'
pc = pages(cfg, 'chronicle')
me = cfg.get('me') or '我'
disp = lambda s: me if s == 'me' else s

allm = json.load(open(W / 'all.json'))
idx = {m['k']: i for i, m in enumerate(allm)}
idx.update({m['id']: i for i, m in enumerate(allm) if 'id' in m and m['id'] not in idx})
month_count = collections.Counter(m['t'][:7] for m in allm)
label_of = {g.get('key'): g.get('label') for g in cfg.get('groups', [])}
show = {label_of.get(x, x) for x in pages(cfg).get('show_chat_groups', [])}
hidden_note = pc.get('hidden_note', '※ 聊在别的群里，原文不公开')


def excerpt(refs):
    """取被引用消息前后各 3 条同群上下文，最多 40 条；跨越不连续处插一个省略行。"""
    refs = [r for r in refs if allm[idx[r]]['g'] in show]
    if not refs:
        return []
    g = allm[idx[refs[0]]]['g']
    refs = [r for r in refs if allm[idx[r]]['g'] == g]
    keys = {allm[idx[r]]['k'] for r in refs}
    keep = set()
    for p in sorted(idx[r] for r in refs):
        keep.add(p)
        for step in (-1, 1):
            n, i = 0, p
            while 0 < i + step < len(allm) and n < 3:
                i += step
                if allm[i]['g'] == g:
                    keep.add(i); n += 1
    out, prev = [], None
    for i in sorted(keep)[:40]:
        m = allm[i]
        if prev is not None and any(allm[k]['g'] == g for k in range(prev + 1, i)):
            out.append({'gap': 1})
        out.append({'t': m['t'][5:16], 's': disp(m['s']), 'c': m['c'], 'k': m['k'] in keys})
        prev = i
    return out


months, all_events, bad = [], {}, 0
for f in sorted((W / 'stable').glob('*.json')):
    mo = json.load(open(f))
    evs = []
    for i, e in enumerate(mo.get('events', [])):
        refs = [r for r in e.get('refs', []) if r in idx]
        bad += len(e.get('refs', [])) - len(refs)
        ex = excerpt(refs)
        ev = {'id': f"{mo['month']}-{i}", 'date': e['date'], 'title': e['title'], 'summary': e.get('summary', ''),
              'people': [disp(p) for p in e.get('people', [])], 'category': e.get('category', '群内热议'),
              'heat': int(e.get('heat', 1)), 'ex': ex,
              'lock': hidden_note if show and refs and not ex else ''}
        all_events[ev['id']] = (ev, len(refs))
        evs.append(ev)
    evs.sort(key=lambda e: e['date'])
    months.append({'month': mo['month'], 'summary': mo.get('month_summary', ''),
                   'count': month_count.get(mo['month'], 0), 'events': evs})
if not months:
    sys.exit(f'{W / "stable"} 里没有月份文件')

# ---------- 年度十大 + 三张榜（只有登录版网站显示；单文件版不展示） ----------
# 第一年不足 3 个月时并进下一年
years = sorted({m['t'][:4] for m in allm})
first_months = sorted({m['t'][:7] for m in allm if m['t'][:4] == years[0]})
merge = len(years) > 1 and len(first_months) < 3
year_of = lambda t: years[1] if merge and t[:4] == years[0] else t[:4]
talk, night, seen = (collections.defaultdict(collections.Counter) for _ in range(3))
for m in allm:
    talk[year_of(m['t'])][disp(m['s'])] += 1
    if m['t'][11:13] < '05':
        night[year_of(m['t'])][disp(m['s'])] += 1
for ev, _ in all_events.values():
    for p in set(ev['people']):
        seen[year_of(ev['date'])][p] += 1
picks_path = W / 'top10.json'
if picks_path.exists():
    picks = {y: [{'id': p['id'].removeprefix('E:'), 'reason': p.get('reason', '')} for p in rows]
             for y, rows in json.load(open(picks_path)).items()}
else:  # 自动：热度高的优先，同热度按引用条数
    by_year = collections.defaultdict(list)
    for eid, (ev, nref) in all_events.items():
        by_year[year_of(ev['date'])].append((-ev['heat'], -nref, ev['date'], eid))
    picks = {y: [{'id': r[3], 'reason': all_events[r[3]][0]['summary']} for r in sorted(rows)[:10]] for y, rows in by_year.items()}
top = {}
for year in sorted(picks):
    rows = []
    for p in picks[year]:
        if p['id'] not in all_events:
            print('top10.json 里找不到事件', p['id']); continue
        ev = all_events[p['id']][0]
        rows.append({k: ev[k] for k in ('id', 'date', 'title', 'category', 'heat', 'people')} | {'month': ev['id'][:7], 'reason': p['reason']})
    note = f'含 {years[0]} 年的 {len(first_months)} 个月' if merge and year == years[1] else ''
    top[year] = {'note': note, 'events': rows, 'boards': [
        ['话痨榜', '发言条数', talk[year].most_common(5)],
        ['上镜榜', '出现在几件事里', seen[year].most_common(5)],
        ['夜猫子榜', '凌晨 0–5 点的发言条数', night[year].most_common(5)],
    ]}

# ---------- 封面 ----------
name = site_name(cfg)
evs = [e for m in months for e in m['events']]
people = {p for e in evs for p in e['people']}
lede = (f"<b>{len(allm):,}</b> 条消息里，攒下的 <b>{len(evs):,}</b> 件大事小事。"
        + esc(pc.get('lede_tail', '生日、聚会、吵过的架，还有半夜的梦。')))
stats = ''.join(f'<div><b>{n}</b><span>{label}</span></div>' for n, label in [
    (sum(e['heat'] == 3 for e in evs), '件大事'), (len(month_count), '个月'), (len(people), '位群友')])
y0, y1 = allm[0]['t'][:4], allm[-1]['t'][:4]
span = cn_year(y0) + (' 至 ' + cn_year(y1) if y1 != y0 else '')

payload = {'months': months, 'activity': sorted(month_count.items()), 'top': top}
tpl = (TEMPLATES / 'chronicle.html').read_text()
page = fill(tpl, {
    'TITLE': esc(cfg.get('title') or name + '大事记'), 'NAME': title_spans(name), 'NAME_N': len(name),
    'SEAL': esc(pc.get('seal', '大事记')), 'END_SEAL': esc(pc.get('end_seal', name[:2])),
    'LEDE': lede, 'STATS': stats, 'SPAN': span, 'TABS': tabs_html(cfg, 'chronicle', proj / 'out'),
    'FOOTER': esc(pc.get('footer', f'据群聊记录整理，挂一漏万。哪件事记错了、漏掉了，找{author_title(cfg)}说一声。')),
    'DATA': json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/'),
})
# 正文字体只覆盖页面与事件文字；聊天原文用系统字体，不进子集
text = plain_text(tpl) + lede + ''.join(e['title'] + e['summary'] + e['category'] + ''.join(e['people']) for e in evs)
text += ''.join(m['summary'] for m in months) + '甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥鼠牛虎兔龙蛇马羊猴鸡狗猪〇一二三四五六七八九十月年至件事位群友条消息只看大事全部所有人年份全年'
text += '.,·:：，。！？、「」《》（）—…~ '
fonts = font_css(proj, cfg, {'Ink': text, 'Hand': text, 'Brush': name + pc.get('end_seal', name[:2]) + '未完待续'})
page = page.replace('/*FONTS*/', fonts)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'chronicle.html').write_text(page)
print(f'月份 {len(months)}，事件 {len(evs)}，带原文 {sum(bool(e["ex"]) for e in evs)}，无效引用 {bad} → {OUT / "chronicle.html"}'
      f'（{(OUT / "chronicle.html").stat().st_size // 1024} KB）')
