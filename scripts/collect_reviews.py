"""回收本人确认结果（可选工具），汇总成 work/review/replies.md。

用法：
  python3 scripts/collect_reviews.py --project <dir> [--in 文件 ...] [--apply-blocked]

- 输入：确认页导出的 json 文件，或粘贴了确认码的 txt（前后夹着聊天文字也行，取第一个 { 到最后一个 }）。
  不写 --in 时读 work/review/in/ 下所有 .json / .txt。同一人有多份时，以 generated 时间最新的为准。
- 输出：work/review/replies/<人>.json（规范化后的回收结果）+ work/review/replies.md（逐人：可以公开、修改意见、标了别公开的条目；
  未回收名单）。确认页已经重新生成过（内容变了）的，会标出“确认的是旧版页面”。
- 汇总只供创作者参考，怎么改、发不发由创作者决定；构建脚本只会把“谁标了别公开/要改”打一行提醒（privacy_gate.review_note）。
- 「别公开」的小传段落与事件摘要可以加进已删除素材清单：默认只列出来；创作者想要时加 --apply-blocked，
  追加进 work/privacy/blocked.txt，之后公开页面再出现它们，隐私闸门会提醒（严格模式下会拦）。
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import build_review_pages as brp  # noqa: E402
from privacy_gate import add_blocked  # noqa: E402

LABEL = {'ok': '对', 'wrong': '要改', 'hide': '别公开', 'partly': '部分对', 'public': '可以公开', '': '没选'}
KIND = {'portrait': '小传', 'persona': '对照清单', 'event': '大事记'}


def parse(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    i, j = text.find('{'), text.rfind('}')
    if i < 0 or j < i:
        raise ValueError('没找到确认码（JSON）')
    d = json.loads(text[i:j + 1])
    if d.get('schema') != 'gcc-review/1' or not d.get('person') or not isinstance(d.get('items'), list):
        raise ValueError('不是确认页导出的确认码')
    return d


def current_hash(proj, cfg, person):
    """按当前数据重算确认页的 page 哈希，用来判断对方确认的是不是最新版。"""
    portrait = brp.portrait_items(proj / 'out/portraits' / f'{person}.md')
    persona, _ = brp.persona_items(proj, person)
    events = brp.event_items(proj, cfg, person)
    html = brp.build_page(cfg, person, portrait, persona, events)
    meta = json.loads(html.split('<script type="application/json" id="meta">', 1)[1].split('</script>', 1)[0].replace('<\\/', '</'))
    return meta['page']


def main():
    a = common.args(__doc__, lambda p: (
        p.add_argument('--in', dest='inputs', nargs='+', metavar='文件', help='确认码 json/txt；默认 work/review/in/*'),
        p.add_argument('--apply-blocked', action='store_true', help='把「别公开」条目追加进已删除素材清单')))
    proj, cfg = a.project, a.cfg
    rv = proj / 'work/review'
    files = [Path(x).expanduser() for x in a.inputs] if a.inputs else sorted(
        p for p in (rv / 'in').glob('*') if p.suffix in ('.json', '.txt')) if (rv / 'in').exists() else []
    if not files:
        sys.exit(f'没有输入：用 --in 指定，或把收回的 json/txt 放进 {rv / "in"}/')
    got = {}
    for f in files:
        try:
            d = parse(f)
        except (ValueError, json.JSONDecodeError) as e:
            print(f'跳过 {f}：{e}')
            continue
        old = got.get(d['person'])
        if not old or d.get('generated', '') > old.get('generated', ''):
            got[d['person']] = d
    (rv / 'replies').mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [f'# 本人确认汇总（{now}）', '',
             '只供参考：怎么改、发不发由你决定。', '',
             '| 人 | 回收 | 已选/总数 | 可以公开/对 | 有意见 | 别公开 |', '|---|---|---|---|---|---|']
    body, candidates = [], []
    everyone = list(dict.fromkeys(list(cfg.get('people') or []) + list(got)))
    for person in everyone:
        d = got.get(person)
        if not d:
            lines.append(f'| {person} | 未回收 | – | – | – | – |')
            continue
        (rv / 'replies' / f'{common.safe(person)}.json').write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
        items = d['items']
        agree = [x for x in items if x.get('v') in ('ok', 'public')]
        hide = [x for x in items if x.get('v') == 'hide']
        opinion = [x for x in items if x.get('v') in ('wrong', 'partly') or (x.get('note') and x.get('v') != 'hide')]
        lines.append(f'| {person} | {d.get("generated", "")[:10]} | {d.get("answered")}/{d.get("total")} | {len(agree)} | '
                     f'{len(opinion)} | {len(hide)} |')
        try:
            stale = current_hash(proj, cfg, person) != d.get('page')
        except Exception:  # 数据缺了一块（比如小传删了）也照样汇总
            stale = True
        body += ['', f'## {person}', '']
        if stale:
            body.append('> ⚠ 确认的是旧版页面（之后小传/清单/事件改过）。下面按条目 key 对应，改动过的段落请人工核对。\n')
        if d.get('general'):
            body += ['**整体意见**：' + d['general'].replace('\n', ' '), '']
        body.append(f'**可以公开/对**：{len(agree)} 条' + (f'（{"、".join(x["key"] for x in agree)}）' if agree else ''))
        body += ['', f'**别公开（{len(hide)}）**：' + ('' if hide else '无')]
        for x in hide:
            body.append(f'- [{KIND.get(x["kind"], x["kind"])} {x["key"]}] {x.get("title", "")}{"：" if x.get("title") else ""}{x.get("text", "")}'
                        + (f'\n  - 备注：{x["note"]}' if x.get('note') else ''))
            if x.get('text') and x['kind'] in ('portrait', 'event'):
                candidates.append((person, x['text']))
        body += ['', f'**修改意见（{len(opinion)}）**：' + ('' if opinion else '无')]
        for x in opinion:
            body.append(f'- [{KIND.get(x["kind"], x["kind"])} {x["key"]}] **{LABEL.get(x.get("v", ""), x.get("v"))}** '
                        f'{x.get("title", "")}{"：" if x.get("title") else ""}{x.get("text", "")}'
                        + (f'\n  - 备注：{x["note"]}' if x.get('note') else ''))
    missing = [p for p in cfg.get('people') or [] if p not in got]
    if missing:
        body += ['', '## 未回收', '', '、'.join(missing)]
    if candidates:
        if a.apply_blocked:
            n = sum(add_blocked(proj, [t for q, t in candidates if q == p], f'来自 {p} 本人确认「别公开」')
                    for p in dict.fromkeys(q for q, _ in candidates))
            body += ['', '## 已删除素材清单', '', f'已把 {n} 条「别公开」追加进 work/privacy/blocked.txt（重复的跳过）。']
            print(f'已追加 {n} 条进 {proj / "work/privacy/blocked.txt"}')
        else:
            body += ['', '## 待加入已删除素材清单', '',
                     f'共 {len(candidates)} 条「别公开」，想加进清单就运行 `collect_reviews.py --project <dir> --apply-blocked`；'
                     '要删的话记得从小传 / 事件里删掉（清单里的内容再出现，闸门会提醒）。']
            print(f'有 {len(candidates)} 条「别公开」：想加进已删除素材清单就加 --apply-blocked 再跑一次')
    (rv / 'replies.md').write_text('\n'.join(lines + body) + '\n', encoding='utf-8')
    print(f'回收 {len(got)} 人，未回收 {len(missing)} 人 → {rv / "replies.md"}')


if __name__ == '__main__':
    main()
