"""汇总统一阅读（prompts/00）的产物 work/cards/<分段>.json：
  ① 事件 → work/events/<月>.json（该月只有一段）或 work/part_events/<分段>.json（多段，之后走 02 合并）
  ② 人物证据 → work/people/<人>/evidence.md（按时间排序，每条带稳定键 k 与日期，供写作员/建模员读）
  ③ 核对报告 → work/review/evidence-check.md

用法：
  python3 scripts/collect_evidence.py --project <dir> [--no-events] [--force-events]

逐条核对证据（不合格的放进 evidence.md 末尾「待核对」，不进正文）：
  - id 在 all.json 里、且在这个分段文件里（不在 → 编造或抄错）
  - 说话人：名场面/语言指纹/对人方式/在乎与怕/反差/日常 必须是本人说的；他评 必须是别人说的；`who` 要和原文一致
  - quote 在那条消息的正文里（不含「（回复 X: …）」引用部分；忽略空白标点，按 … 切段）
  - kind 合法；also 里的 id 存在
事件文件：目标已存在且比卡片新时不覆盖（合并/手改过的不会被冲掉），--force-events 强制覆盖。
卡片的 read_to < lines（没读完）会在报告里列出。补读卡片 <分段>-b.json（fill_prompt --from-line 派的）和原卡片接起来算，
事件与证据一起汇总。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import REPLY_RE, args, body, display, load_all, people, safe  # noqa: E402
from pipeline import read_progress  # noqa: E402
from verify_citations import canon, quote_in  # noqa: E402

KINDS = ('名场面', '语言指纹', '对人方式', '他评', '在乎与怕', '反差', '日常', '禁区')
SELF = {'名场面', '语言指纹', '对人方式', '在乎与怕', '反差', '日常'}
LINE_ID = re.compile(r'^([A-Za-z]+\d+)\|')


def extra(p):
    p.add_argument('--no-events', action='store_true', help='不导出事件（只汇总人物证据）')
    p.add_argument('--force-events', action='store_true', help='事件文件已存在也覆盖')


def chunk_ids(f):
    if not f.exists():
        return None, 0
    lines = f.read_text(encoding='utf-8').split('\n')
    return {m.group(1) for m in map(LINE_ID.match, lines) if m}, len(lines)


def main():
    a = args(__doc__, extra)
    cfg = a.cfg
    allm = load_all(a)
    byid = {m['id']: m for m in allm}
    wanted = people(cfg)
    cards = sorted((a.work / 'cards').glob('*.json'))
    if not cards:
        sys.exit(f'{a.work / "cards"} 里没有卡片，先跑统一阅读（prompts/00）')
    parts = {}
    for f in (a.work / 'chunks').glob('*.txt'):
        parts.setdefault(f.stem.rsplit('_p', 1)[0], []).append(f.stem)
    ev = {p: [] for p in wanted}      # 人 → [(时间, 行)]
    bad = {p: [] for p in wanted}
    taboo = {p: [] for p in wanted}
    glance = {p: [] for p in wanted}
    report, nev, unread = [], 0, []
    loaded = {}  # 分段 → [(卡片文件, 内容)]，原卡片在前、补读卡片在后
    for cf in cards:
        try:
            d = json.loads(cf.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            report.append(f'- {cf.name}：JSON 不合法（{e}），整份跳过')
            continue
        loaded.setdefault(re.sub(r'-[b-z]$', '', cf.stem), []).append((cf, d))
    for stem, group in loaded.items():
        group.sort(key=lambda x: x[0].stem != stem)  # 原卡片在前
        got, lines = read_progress(a.project, stem)
        if lines and got < lines:
            unread.append(f'{stem}（读到 {got}/{lines} 行）')
        # ① 事件：原卡片和补读卡片的事件一起写
        d0 = group[0][1]
        if not a.no_events and any('events' in d for _, d in group):
            mon = d0.get('month') or stem[:7]
            single = len(parts.get(mon, [stem])) <= 1
            dst = a.work / ('events' if single else 'part_events') / (f'{mon}.json' if single else f'{stem}.json')
            newest = max(cf.stat().st_mtime for cf, _ in group)
            if a.force_events or not dst.exists() or dst.stat().st_mtime < newest:
                evs = [e for _, d in group for e in d.get('events') or []]
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(json.dumps({'month': mon, 'month_summary': d0.get('month_summary', ''), 'events': evs},
                                          ensure_ascii=False, indent=1), encoding='utf-8')
                nev += len(evs)
        for cf, d in group:
            ids, nlines = chunk_ids(a.work / 'chunks' / f'{stem}.txt')
            if nlines and d.get('lines') and abs(d['lines'] - nlines) > 1:
                report.append(f'- {cf.name}：回报文件 {d["lines"]} 行，实际 {nlines} 行——核对是否读的是这个文件')
            # ② 证据
            for p, blk in (d.get('people') or {}).items():
                p = canon(cfg, p)
                if p not in ev:
                    report.append(f'- {cf.name}：{p} 不在 config.people 里，跳过')
                    continue
                if blk.get('glance'):
                    glance[p].append(f'- {cf.stem}：{blk["glance"]}')
                for it in blk.get('items') or []:
                    mid, kind = it.get('id', ''), it.get('kind', '')
                    m = byid.get(mid)
                    why = []
                    if kind not in KINDS:
                        why.append(f'kind「{kind}」不合法')
                    if not m:
                        why.append(f'id {mid} 不在 all.json')
                    elif ids is not None and mid not in ids:
                        why.append(f'id {mid} 不在分段 {cf.stem} 里')
                    for x in it.get('also') or []:
                        if x not in byid:
                            why.append(f'also 的 {x} 不在 all.json')
                    if m:
                        actual = display(cfg, m['s'])
                        who = canon(cfg, it['who']) if it.get('who') else None
                        if who and who != actual:
                            why.append(f'who 写的是 {who}，原文说话人是 {actual}')
                        if kind in SELF and actual != p:
                            why.append(f'记在 {p} 名下的「{kind}」，原文是 {actual} 说的（别人的话只能记成他评）')
                        if kind == '他评' and actual == p:
                            why.append('他评却是本人说的')
                        if kind != '禁区' and it.get('quote') and not quote_in(it['quote'], body(m['c'])):
                            rq = REPLY_RE.search(m['c'])
                            if '（回复' in it['quote'] or '(回复' in it['quote']:
                                why.append('quote 里抄进了「（回复 X: …）」——那是被引用的旧消息，只抄这条消息自己说的字')
                            elif rq and quote_in(it['quote'], rq.group(0)):
                                why.append('quote 是被引用的旧消息里的话（「（回复 X: …）」部分），不是这条消息的发言人说的')
                            else:
                                why.append('quote 不在这条消息里')
                    tm = m['t'][:16] if m else '????-??-?? ??:??'
                    k = m['k'] if m else mid
                    if kind == '禁区':
                        (bad[p] if why else taboo[p]).append((tm, f'- {tm[:10]}｜{it.get("topic", "?")}｜k={k}' + (f'｜✗ {"；".join(why)}' if why else '')))
                        continue
                    spk = display(cfg, m['s']) if m else (it.get('who') or '?')
                    tail = [x for x in (it.get('tone'), f'对 {it["to"]}' if it.get('to') else '') if x]
                    also = [byid[x]['k'] for x in it.get('also') or [] if x in byid]
                    line = (f'- {tm}｜{kind}｜k={k}｜{spk}：「{it.get("quote", "")}」— {it.get("note", "")}'
                            + (f'（{"，".join(tail)}）' if tail else '') + (f'｜另见 {"、".join(also)}' if also else ''))
                    (bad[p] if why else ev[p]).append((tm, line + (f'｜✗ {"；".join(why)}' if why else '')))
    for p in wanted:
        d = a.work / 'people' / safe(p)
        d.mkdir(parents=True, exist_ok=True)
        lines = [f'# {p} · 证据汇总（统一阅读）', '',
                 f'来源：work/cards/*.json 共 {len(cards)} 段。有效 {len(ev[p])} 条，待核对 {len(bad[p])} 条，禁区主题 {len(taboo[p])} 条。',
                 '引用某条原话时，在引语后紧跟它的标注：`「原话」<!--k:这里填 k-->`（别人说的写 `<!--k:…@说话人-->`）。', '',
                 '## 各段一句话', ''] + (glance[p] or ['- （无）'])
        lines += ['', '## 证据（按时间）', ''] + ([x for _, x in sorted(ev[p])] or ['- （无）'])
        lines += ['', '## 禁区主题（只列主题与日期，不写进公开文本）', ''] + ([x for _, x in sorted(taboo[p])] or ['- （无）'])
        lines += ['', '## 待核对（脚本查出问题，不要直接引用；需要时回原文确认）', ''] + ([x for _, x in sorted(bad[p])] or ['- （无）'])
        (d / 'evidence.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'{p}: 有效 {len(ev[p])}，待核对 {len(bad[p])}，禁区 {len(taboo[p])} → {d / "evidence.md"}')
    rv = a.work / 'review'
    rv.mkdir(parents=True, exist_ok=True)
    out = ['# 统一阅读汇总核对', '', f'卡片 {len(cards)} 份；导出事件 {nev} 条。', '',
           '## 没读完的分段（补派）', ''] + ([f'- {x}' for x in unread] or ['- （无）'])
    out += ['', '## 卡片问题', ''] + (report or ['- （无）'])
    out += ['', '## 各人待核对条目', '']
    for p in wanted:
        out += [f'### {p}（{len(bad[p])} 条）'] + [x for _, x in sorted(bad[p])] + ['']
    (rv / 'evidence-check.md').write_text('\n'.join(out) + '\n', encoding='utf-8')
    print(f'导出事件 {nev} 条；没读完 {len(unread)} 段；报告 → {rv / "evidence-check.md"}')


if __name__ == '__main__':
    main()
