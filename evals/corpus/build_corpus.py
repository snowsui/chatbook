"""把写作子任务产出的 src/<YYYY-MM>.md 拼成可被 skill 导入的聊天导出，并回填真值里的实测发言形态。

用法：
  python3 evals/corpus/build_corpus.py evals/corpus/roommates [--from 2023-09 --to 2023-11] [--measure]

- 语料目录下 truth/config.json 的 groups[0].format 决定导出格式：chatlab（ChatLab 开放格式）或 txt。
- 输出到 <语料>/exports/<groups[0].file 的文件名>（--from/--to 时文件名加 _<from>_<to> 后缀，用于子集实测）。
- 说话人写显示名；chatlab 里按 persona 的 nickname_timeline 换成当时的群昵称、sender 填 persona 的 uid，
  is_self 的人写进 meta.ownerId；`[图片] 配文` 在 chatlab 里拆成一条图片 + 一条文字，txt 里原样保留。
- `说话人 ↩被回复人[「片段」]: 内容` → 引用回复（chatlab 的 replyToMessageId；txt 写成 `内容（回复 X: 前40字）`）。
- 打印：条数、>8 字消息完全重复占比、各类消息占比、每人条数。
- --measure：在临时目录跑 scripts/ingest.py + scripts/turnmix.py，把每人的实测发言形态写回 truth/persona_*.json 的 speech_measured。
"""
import argparse
import collections
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
LINE = re.compile(r'^(\d{1,2}):(\d{2})\s+([^:：↩]+?)\s*(?:↩\s*([^:：「]+?)\s*(?:「([^」]*)」)?)?\s*[:：]\s?(.*)$')
DAY = re.compile(r'^##\s*(\d{4}-\d{2}-\d{2})')
PH = re.compile(r'^\[(图片|表情|语音|视频|链接|文章|红包|拍一拍|文件|位置|小程序|转账)\]\s*(.*)$')
CL_TYPE = {'图片': 1, '语音': 2, '视频': 3, '文件': 4, '表情': 5, '链接': 7, '文章': 7, '位置': 8, '红包': 20, '转账': 21,
           '拍一拍': 22, '小程序': 24}  # ChatLab 消息类型；文字 0，引用回复 25


def parse_src(root, start=None, end=None):
    msgs, bad = [], []
    for f in sorted((root / 'src').glob('*.md')):
        mon = f.stem[:7]
        if (start and mon < start) or (end and mon > end):
            continue
        day = None
        for n, raw in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith('# '):
                continue
            m = DAY.match(line)
            if m:
                day = m.group(1)
                continue
            m = LINE.match(line)
            if not m or not day:
                if msgs and day and not line.startswith('#'):
                    msgs[-1]['c'] += ' ⏎ ' + line  # 续行
                else:
                    bad.append(f'{f.name}:{n}: {line[:60]}')
                continue
            hh, mm, who, rto, rfrag, c = m.groups()
            msgs.append({'day': day, 'hm': (int(hh), int(mm)), 's': who.strip(), 'rto': (rto or '').strip() or None,
                         'rfrag': rfrag, 'c': c.strip()})
    return msgs, bad


def assign_times(msgs):
    """同一分钟内的多条按顺序分配秒；时间倒退时夹到上一条之后。"""
    last = None
    for m in msgs:
        t = datetime.strptime(f'{m["day"]} {m["hm"][0]:02d}:{m["hm"][1]:02d}:00', '%Y-%m-%d %H:%M:%S')
        ts = time.mktime(t.timetuple())
        if last is not None and ts <= last:
            ts = last + 7
        m['ts'] = int(ts)
        last = m['ts']
        m['t'] = datetime.fromtimestamp(m['ts']).strftime('%Y-%m-%d %H:%M:%S')


def nick_at(persona, day):
    cur = persona['nickname_timeline'][0]['nick']
    for x in persona['nickname_timeline']:
        if x['from'] <= day:
            cur = x['nick']
    return cur


def find_ref(msgs, i, who, frag):
    for j in range(i - 1, max(-1, i - 400), -1):
        if msgs[j]['s'] == who and (not frag or frag in msgs[j]['c']):
            return msgs[j]
    return None


def text_of(c):
    m = PH.match(c)
    return m.group(2) if m else c


def stats(msgs):
    n = len(msgs)
    texts = [text_of(m['c']) for m in msgs]
    long_ = [t for t in texts if len(t) > 8]
    cnt = collections.Counter(long_)
    dup = sum(v - 1 for v in cnt.values() if v > 1)
    kinds = collections.Counter((PH.match(m['c']).group(1) + ('+配文' if PH.match(m['c']).group(2) else '')) if PH.match(m['c']) else '文字' for m in msgs)
    print(f'共 {n} 条；>8 字文字 {len(long_)} 条，其中完全重复 {dup} 条（{100 * dup / max(1, len(long_)):.2f}%）')
    print('重复最多：' + '；'.join(f'{t[:20]}×{v}' for t, v in cnt.most_common(5) if v > 1))
    print('类型：' + '、'.join(f'{k} {100 * v / n:.1f}%' for k, v in kinds.most_common()))
    print('引用回复：%.1f%%' % (100 * sum(1 for m in msgs if m['rto']) / n))
    print('每人：' + '、'.join(f'{k} {v}' for k, v in collections.Counter(m['s'] for m in msgs).most_common()))
    return {'messages': n, 'long_text': len(long_), 'long_dup': dup, 'long_dup_rate': round(dup / max(1, len(long_)), 4)}


def to_chatlab(msgs, personas, label):
    out, lid, mid = [], 0, {}
    for i, m in enumerate(msgs):
        p = personas[m['s']]
        ph = PH.match(m['c'])
        if ph and ph.group(1) == '图片' and ph.group(2):
            parts = [('图片', ''), ('文字', ph.group(2))]
        elif ph:
            parts = [(ph.group(1), ph.group(2))]
        else:
            parts = [('文字', m['c'])]
        for k, (kind, c) in enumerate(parts):
            lid += 1
            rec = {'sender': p['uid'], 'accountName': nick_at(p, m['day']), 'timestamp': m['ts'] + k,
                   'platformMessageId': f'm{lid}'}
            if kind == '文字':
                ref = find_ref(msgs, i, m['rto'], m['rfrag']) if m['rto'] and k == len(parts) - 1 else None
                rec.update(type=25 if ref is not None else 0, content=c)
                if ref is not None:
                    rec['replyToMessageId'] = mid[id(ref)]
            else:
                rec.update(type=CL_TYPE.get(kind, 99), content=c)
            out.append(rec)
            mid[id(m)] = rec['platformMessageId']  # 被引用时指向最后一条（图片 + 配文时是配文）
    owner = next((p['uid'] for p in personas.values() if p.get('is_self')), None)
    members = [{'platformId': p['uid'], 'accountName': p['nickname_timeline'][-1]['nick']} for p in personas.values()]
    data = {'chatlab': {'version': '0.0.1', 'generator': 'evals/corpus/build_corpus.py'},
            'meta': {'name': label, 'type': 'group', 'groupId': 'g_' + label, **({'ownerId': owner} if owner else {})},
            'members': members, 'messages': out}
    return json.dumps(data, ensure_ascii=False, indent=0)


def to_txt(msgs, personas):
    lines = []
    for i, m in enumerate(msgs):
        c = m['c']
        if m['rto']:
            ref = find_ref(msgs, i, m['rto'], m['rfrag'])
            if ref is not None:
                c = f'{c}（回复 {ref["s"]}: {(text_of(ref["c"]) or ref["c"])[:40]}）'
        lines.append(f'{m["t"]} {m["s"]}: {c}')
    return '\n'.join(lines) + '\n'


def measure(root, cfg, export):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / 'exports').mkdir()
        shutil.copy(export, td / 'exports' / Path(cfg['groups'][0]['file']).name)
        c = dict(cfg)
        c['groups'] = [dict(cfg['groups'][0], file='exports/' + Path(cfg['groups'][0]['file']).name)]
        (td / 'chronicle.config.json').write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8')
        for s in ('ingest', 'turnmix'):
            subprocess.run([sys.executable, str(SKILL / 'scripts' / f'{s}.py'), '--project', str(td)], check=True,
                           stdout=subprocess.DEVNULL)
        rows = {}
        lines = (td / 'work' / 'turnmix.md').read_text(encoding='utf-8').splitlines()
        head = [x.strip() for x in lines[4].strip('|').split('|')]
        for line in lines[6:]:
            if not line.startswith('|') or '条件分布' in line:
                break
            cells = [x.strip() for x in line.strip('|').split('|')]
            rows[cells[0]] = dict(zip(head[1:], cells[1:]))
    pct = lambda v: round(float(v.rstrip('%')) / 100, 3) if v.endswith('%') else None  # noqa: E731
    for f in sorted((root / 'truth').glob('persona_*.json')):
        p = json.loads(f.read_text(encoding='utf-8'))
        col = {k: v.get(p['name']) for k, v in rows.items()}
        if not col.get('turn 数'):
            continue
        sm = {'turns': int(col['turn 数']), 'single': pct(col['单条 turn 占比']), 'reaction': pct(col['纯反应']),
              'jump': pct(col['跳线'])}
        sm['burst'] = round(1 - sm['single'], 3)
        sm['all'] = {k: col[k] for k in rows if k not in ('turn 数',)}
        p['speech_measured'] = sm
        f.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'{p["name"]}: 设计 {p["speech_design"]} → 实测 single={sm["single"]} reaction={sm["reaction"]} jump={sm["jump"]}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('corpus')
    ap.add_argument('--from', dest='start')
    ap.add_argument('--to', dest='end')
    ap.add_argument('--measure', action='store_true')
    a = ap.parse_args()
    root = Path(a.corpus).resolve()
    cfg = json.loads((root / 'truth' / 'config.json').read_text(encoding='utf-8'))
    personas = {p['name']: p for p in (json.loads(f.read_text(encoding='utf-8')) for f in (root / 'truth').glob('persona_*.json'))}
    msgs, bad = parse_src(root, a.start, a.end)
    unknown = collections.Counter(m['s'] for m in msgs if m['s'] not in personas)
    unknown.update(m['rto'] for m in msgs if m['rto'] and m['rto'] not in personas)
    if bad:
        print(f'警告：{len(bad)} 行无法解析（并入上一条或丢弃）：\n  ' + '\n  '.join(bad[:10]))
    if unknown:
        print('警告：未知说话人 ' + str(dict(unknown)) + '，这些行被丢弃')
        msgs = [m for m in msgs if m['s'] in personas]
        for m in msgs:
            if m['rto'] and m['rto'] not in personas:
                m['rto'] = None
    assign_times(msgs)
    st = stats(msgs)
    fmt = cfg['groups'][0]['format']
    name = Path(cfg['groups'][0]['file'])
    if a.start or a.end:
        name = name.with_name(f'{name.stem}_{a.start or ""}_{a.end or ""}{name.suffix}')
    out = root / 'exports' / name.name
    out.parent.mkdir(exist_ok=True)
    out.write_text(to_chatlab(msgs, personas, cfg['groups'][0]['label']) if fmt == 'chatlab' else to_txt(msgs, personas),
                   encoding='utf-8')
    print(f'→ {out}')
    if not (a.start or a.end):
        (root / 'truth' / 'corpus_stats.json').write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
    if a.measure:
        measure(root, cfg, out)


if __name__ == '__main__':
    main()
