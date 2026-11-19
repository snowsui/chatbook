"""开工第一步：给一堆聊天导出文件自动识别格式、分群，写最小 chronicle.config.json，再跑 ingest。

用法：
  python3 scripts/init_project.py --project <dir> <文件或目录>... [--no-ingest]
  识别不了的文件写成 `文件:格式` 指定（格式：json-array / chatlab / txt / csv / qq / telegram），如 `exports/a.log:txt`。
  没有时间也没有日期行的 txt 写成 `文件:txt@2024-02-10`（这份文件里的消息都算这一天）。
  python3 scripts/init_project.py --project <dir> --same B=A     把 B 群并进 A 群（同一个群的不同格式导出）
  python3 scripts/init_project.py --project <dir> --drop-group C  从 config 里去掉整个群

- 格式按扩展名 + 内容嗅探：.json 看结构（json-array 数组 / ChatLab {chatlab, meta, messages} / Telegram {name, messages}），
  .csv 看表头（time/时间、sender/发送者、content/内容、可选 id/消息ID），.txt 区分 QQ 消息管理器导出与普通文本
  （普通文本含没有时间的「发送者：内容」形态，见 ingest.py）。文本不是 UTF-8 时自动试 GB18030、UTF-16。
  目录会递归找 .json/.txt/.csv，目录里识别不了的文件跳过并提示。
- 一份文件读不了（空文件、只有表头、没有日期的 txt……）不影响其他文件：先导入能读的，最后列出没导入的文件和修复办法。
- 每个群一个短 key（A、B、C…）和 label（导出里的群名；没有群名就用文件名，并提示去 config 里改成好认的名字——页面上会显示）。
- 同一个群的多次导出（时间重叠）自动认成一个群：同格式，且群 ID/群名相同、或有足够多的消息重合
  （≥ min(10, 较小一份的一半, 至少 3 条)；重合按平台消息 ID，没有就按 时间+发送者+内容）。合并成 "file": [列表]，ingest 去重。
  不同格式的两份导出按 分钟+内容 比对，重合够多只提示“疑似同一个群”，确认后用 --same 合并（ingest 按 分钟+内容 去重）。
- config 已存在：只追加新群 / 给已有的群追加新导出，不改用户已写的其他键；同一文件重复传入会跳过。
下一步：python3 scripts/roster.py --project <dir> build（人物名单）。
"""
import argparse
import csv
import io
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402
from common import read_config  # noqa: E402

FORMATS = tuple(ingest.ADAPTERS)
EXTS = {'.json', '.txt', '.csv'}
RICH = ('txt', 'csv', 'qq', 'telegram', 'chatlab', 'json-array')  # 信息量从少到多
CSV_COLS = {'time': ('time', '时间', 'date', 'datetime', '日期', '发送时间', 'timestamp'),
            'sender': ('sender', '发送者', '发言人', '发送人', '昵称', 'name', 'from', 'user'),
            'content': ('content', '内容', '消息', '消息内容', 'message', 'text'),
            'id': ('id', '消息id', 'msgid', 'msg_id', 'message_id', 'messageid')}
QQ_SPECIFIC = re.compile(r'^\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{2}:\d{2}\s+.*?(?:\(\d+\)|<[^>]+>)$')


def csv_columns(head_line):
    head = next(csv.reader(io.StringIO(head_line)), [])
    low = {h.strip().lower(): h.strip() for h in head}
    cols = {}
    for k, names in CSV_COLS.items():
        hit = next((low[n] for n in names if n in low), None)
        if hit:
            cols[k] = hit
    return cols if all(k in cols for k in ('time', 'sender', 'content')) else None


ARRAY_HINT = {'sender', 'content', 'time', 'timestamp', 'sender_id', 'msg_id', 'type', 'is_self', 'reply_to'} | set(ingest.LEGACY_KEYS)


def sniff(path):
    """→ (format, info)；info: label / gid / columns。识别不了返回 (None, 原因)。"""
    ext = path.suffix.lower()
    if path.stat().st_size == 0:
        return None, '文件是空的'
    try:
        text = ingest.read_text(path)
    except ValueError as e:
        return None, str(e)
    if not text.strip():
        return None, '文件是空的'
    if ext == '.json':
        try:
            data = json.loads(text)
        except ValueError as e:
            return None, f'不是合法 JSON（{e.__class__.__name__}）'
        if isinstance(data, list):
            head = next((x for x in data if isinstance(x, dict)), None)
            if head is None:
                return None, 'JSON 数组里没有消息'
            if 'sender' in head and ({'time', 'timestamp'} & set(head)) or len(ARRAY_HINT & set(head)) >= 4:
                return 'json-array', {}
            return None, 'JSON 数组，但每条里找不到 time/timestamp、sender、content'
        if isinstance(data, dict):
            meta = data.get('meta') or {}
            if 'chatlab' in data or ('meta' in data and isinstance(data.get('messages'), list)):
                return 'chatlab', {'label': meta.get('name'), 'gid': meta.get('groupId') or meta.get('name')}
            msgs = data.get('messages')
            if isinstance(msgs, list) and any(isinstance(m, dict) and 'date' in m for m in msgs[:50]):
                return 'telegram', {'label': data.get('name'), 'gid': data.get('id') or data.get('name')}
        return None, 'JSON 结构不认识'
    lines = [x.rstrip() for x in text.splitlines()[:3000] if x.strip()]
    if ext == '.csv':
        cols = csv_columns(lines[0]) if lines else None
        if not cols:
            return None, 'CSV 表头里找不到 时间/发送者/内容 三列'
        default = {'time': 'time', 'sender': 'sender', 'content': 'content', 'id': 'id'}
        extra = {k: v for k, v in cols.items() if default[k] != v}
        return 'csv', {'columns': extra} if extra else {}
    m = re.search(r'^消息对象:\s*(.+)$', text[:4000], re.M)
    qq = sum(1 for x in lines if QQ_SPECIFIC.match(x))
    if m or qq >= 2:
        return 'qq', {'label': m.group(1).strip() if m else None, 'gid': m.group(1).strip() if m else None}
    tx = sum(1 for x in lines if any(r.match(x) for r in ingest.TXT_LINE) or ingest.TXT_HEAD.match(x))
    if tx >= min(2, len(lines)) and tx:
        return 'txt', {}
    # 无时间形态「张三：内容」：大半行都长这样（或是单独的日期行）才认
    nt = sum(1 for x in lines if ingest.TXT_NOTIME.match(x) or ingest.TXT_DATE.match(x))
    if lines and nt >= 2 and nt * 2 >= len(lines):
        return 'txt', {}
    return None, '文本里找不到「时间 发送者: 内容」或「发送者：内容」这类行'


def info_for(path, fmt):
    """用户用 文件:格式 指定时，照样取群名 / 群 ID / csv 列名。"""
    try:
        if fmt in ('chatlab', 'telegram'):
            d = json.loads(ingest.read_text(path))
            src = d.get('meta') or {} if fmt == 'chatlab' else d
            return {'label': src.get('name'), 'gid': src.get('groupId' if fmt == 'chatlab' else 'id') or src.get('name')}
        text = ingest.read_text(path)
    except (ValueError, AttributeError):
        return {}
    if fmt == 'qq':
        m = re.search(r'^消息对象:\s*(.+)$', text[:4000], re.M)
        return {'label': m.group(1).strip(), 'gid': m.group(1).strip()} if m else {}
    if fmt == 'csv' and text:
        cols = csv_columns(text.splitlines()[0]) or {}
        extra = {k: v for k, v in cols.items() if k != v}
        return {'columns': extra} if extra else {}
    return {}


def msg_keys(path, fmt, g):
    """一份导出的去重键集合（与 ingest 合并时同一口径），以及跨格式比对用的 分钟+内容 键（太短的、占位符不算）。"""
    keep = lambda name, uid=None, self=False: name  # noqa: E731
    recs = list(ingest.ADAPTERS[fmt](path, g, keep))
    loose = {ingest.loose_key(r) for r in recs if len(ingest.loose_key(r)[2]) >= 4 and not r['c'].startswith('[')}
    return {ingest.dedup_key(r) for r in recs}, loose


def rel(path, project):
    try:
        return str(path.relative_to(project))
    except ValueError:
        return str(path)


def collect(project, specs):
    """命令行参数 → [(路径, 指定格式或 None, 日期或 None, 是否点名)]。"""
    out = []
    skip = {project / 'work', project / 'out', project / 'site'}
    for spec in specs:
        fmt = day = None
        p = Path(spec).expanduser()
        if not p.exists() and ':' in spec:
            base, fmt = spec.rsplit(':', 1)
            if '@' in fmt:
                fmt, day = fmt.split('@', 1)
                if not ingest.TXT_DATE.match(day):
                    sys.exit(f'{spec}：日期写成 2024-02-10 这样')
            if fmt not in FORMATS:
                sys.exit(f'{spec}：格式 {fmt!r} 不支持，可选：{"、".join(FORMATS)}')
            p = Path(base).expanduser()
        if not p.exists():
            sys.exit(f'找不到：{spec}')
        p = p.resolve()
        if p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith('.') and Path(root, d) not in skip)
                for f in sorted(files):
                    if not f.startswith('.') and Path(f).suffix.lower() in EXTS and f != 'chronicle.config.json':
                        out.append((Path(root, f), fmt, day, False))
        else:
            out.append((p, fmt, day, True))
    return out


def fix_hint(path, fmt, err, project):
    """读失败时给一条能照做的修复办法。"""
    r = shlex.quote(rel(path, project))
    if '没有时间也没有日期行' in err:
        return (f'在文件开头加一行这份记录的日期（如 2024-02-10；多天的记录在每天第一条前各加一行），'
                f'或写成 {shlex.quote(rel(path, project) + ":txt@2024-02-10")}（换成真实日期）重跑')
    if '文件是空的' in err or '只有表头' in err or '没有消息' in err:
        return '导出不完整：重新导出这份记录；用不上就不用管它'
    if '认不出文本编码' in err:
        return err.split('。', 1)[1] if '。' in err else err
    return f'格式认错了就写成 {r}:<格式> 指定（{"/".join(FORMATS)}）'


def merge_group(groups, src_key, dst_key, project):
    """--same B=A：把 B 群的导出并进 A 群（不同格式的写成 {"file", "format"} 元素）。"""
    by = {g['key']: g for g in groups}
    if src_key not in by or dst_key not in by:
        sys.exit(f'--same {src_key}={dst_key}：config 里没有群 {src_key if src_key not in by else dst_key}'
                 f'（现有：{"、".join(by)}）')
    a, b = by[dst_key], by[src_key]
    entries = ingest.group_entries(a)
    for x in ingest.group_entries(b):
        f = x['file'] if isinstance(x, dict) else x
        fmt = ingest.entry_format(b, x)
        extra = {k: v for k, v in ({**b, **x} if isinstance(x, dict) else b).items() if k in ('columns', 'date')}
        if fmt == a['format'] and not extra:
            entries.append(f)
        else:
            entries.append({'file': f, 'format': fmt, **extra})
    a['file'] = entries
    groups.remove(b)
    print(f'已把 [{b["key"]}] {b["label"]} 并进 [{a["key"]}] {a["label"]}（ingest 按 分钟+内容 去重）')


def next_key(used):
    for i in range(26 * 27):
        k = chr(65 + i % 26) + (str(i // 26 + 1) if i >= 26 else '')
        if k not in used:
            return k


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project', required=True, help='项目目录（没有就新建）')
    ap.add_argument('paths', nargs='*', help='导出文件或目录；识别不了的写成 文件:格式，没日期的 txt 写成 文件:txt@2024-02-10')
    ap.add_argument('--same', action='append', default=[], metavar='B=A', help='把 B 群并进 A 群（同一个群的不同格式导出）')
    ap.add_argument('--drop-group', action='append', default=[], metavar='KEY', help='从 config 里去掉整个群')
    ap.add_argument('--no-ingest', action='store_true', help='只写 config，不跑 ingest')
    a = ap.parse_args()
    if not (a.paths or a.same or a.drop_group):
        ap.error('给出导出文件/目录，或 --same / --drop-group')
    project = Path(a.project).expanduser().resolve()
    project.mkdir(parents=True, exist_ok=True)
    cfg_path = project / 'chronicle.config.json'
    cfg = read_config(cfg_path) if cfg_path.exists() else {}
    groups = cfg.setdefault('groups', [])
    for k in a.drop_group:
        hit = [g for g in groups if g['key'] == k]
        if not hit:
            sys.exit(f'--drop-group {k}：config 里没有这个群（现有：{"、".join(g["key"] for g in groups)}）')
        groups.remove(hit[0])
        print(f'已去掉 [{k}] {hit[0]["label"]}（导出文件没删；以后再传这些文件会重新加回来）')
    for spec in a.same:
        if '=' not in spec:
            sys.exit(f'--same 写成 B=A（把 B 并进 A）：{spec}')
        merge_group(groups, *[x.strip() for x in spec.split('=', 1)], project)

    def abspath(f):
        q = Path(f).expanduser()
        return (q if q.is_absolute() else project / q).resolve()

    known = {abspath(f) for g in groups for f in ingest.group_files(g)}
    # 已有群：格式、群 ID、全部消息键
    pool = []
    for g in groups:
        keys, loose, gid, gf = set(), set(), None, g['format']
        for x in ingest.group_entries(g):
            f = abspath(x['file'] if isinstance(x, dict) else x)
            fx = ingest.entry_format(g, x)
            if f.exists():
                try:
                    k1, k2 = msg_keys(f, fx, {**g, **x} if isinstance(x, dict) else g)
                except (ValueError, KeyError, TypeError):
                    continue
                keys |= k1
                loose |= k2
                fmt, info = sniff(f)
                if fmt == gf and isinstance(info, dict) and info.get('gid') and not gid:
                    gid = f'{fmt}:{info["gid"]}'
        pool.append({'g': g, 'fmt': gf, 'gid': gid, 'keys': keys, 'loose': loose, 'new': False})

    failed, added, renamed = [], [], []
    for path, fmt, day, named in collect(project, a.paths):
        if path in known:
            print(f'跳过（已在 config 里）：{rel(path, project)}')
            continue
        info = {}
        if fmt is None:
            fmt, info = sniff(path)
            if fmt is None:
                if named or info == '文件是空的':
                    failed.append((path, None, info))
                else:
                    print(f'跳过（识别不了）：{rel(path, project)}：{info}。是聊天记录的话写成 '
                          f'{shlex.quote(rel(path, project))}:<格式> 指定（{"/".join(FORMATS)}）')
                continue
        else:
            info = info_for(path, fmt)
        probe = {'columns': info['columns']} if info.get('columns') else {}
        if day:
            probe['date'] = day
        try:
            keys, loose = msg_keys(path, fmt, probe)
        except Exception as e:  # noqa: BLE001  一份读不了不影响其他文件
            why = '这份 txt 没有时间也没有日期行' if '没有时间也没有日期行' in str(e) else f'按 {fmt} 解析失败：{e}'
            failed.append((path, fmt, why))
            continue
        if not keys:
            why = '只有表头、没有消息' if fmt == 'csv' else f'按 {fmt} 解析出 0 条消息'
            failed.append((path, fmt, why))
            continue
        gid = f'{fmt}:{info["gid"]}' if info.get('gid') else None
        same = None
        for e in pool:
            if e['fmt'] != fmt:
                continue
            shared = len(keys & e['keys'])
            need = min(10, max(3, min(len(keys), len(e['keys'])) // 2))
            if (gid and gid == e['gid']) or shared >= need:
                same = e
                print(f'同一个群：{rel(path, project)} → [{e["g"]["key"]}] {e["g"]["label"]}'
                      f'（{"群 ID 相同" if gid and gid == e["gid"] else f"重合 {shared} 条消息"}）')
                break
        sf = rel(path, project)
        if same:
            entry = {'file': sf, 'date': day} if day else sf
            same['g']['file'] = ingest.group_entries(same['g']) + [entry]
            same['keys'] |= keys
            same['loose'] |= loose
            known.add(path)
            continue
        key = next_key({e['g']['key'] for e in pool})
        label = (info.get('label') or '').strip()
        if not label:
            label = path.stem
            renamed.append(key)
        if label in {e['g']['label'] for e in pool}:
            label = f'{label}（{key}）'
        g = {'key': key, 'label': label, 'file': sf, 'format': fmt}
        if info.get('columns'):
            g['columns'] = info['columns']
        if day:
            g['date'] = day
        if gid:
            g['_gid'] = gid
        pool.append({'g': g, 'fmt': fmt, 'gid': gid, 'keys': keys, 'loose': loose, 'new': True})
        groups.append(g)
        known.add(path)
        added.append(g)
        print(f'新群 [{key}] {label}：{sf}（{fmt}，{len(keys)} 条）')
    for g in groups:
        g.pop('_gid', None)

    # 不同格式之间：按 分钟+内容 比对，重合够多就提示可能是同一个群（不自动合并）
    maybe = []
    for e in pool:
        if not e['new']:
            continue
        for o in pool:
            if o is e or o['fmt'] == e['fmt'] or (o['new'] and o['g']['key'] > e['g']['key']):
                continue
            shared = len(e['loose'] & o['loose'])
            if shared >= min(10, max(3, min(len(e['loose']), len(o['loose'])) // 2)):
                # 信息少的并进信息多的（有消息 ID、账号的格式做底）
                src, dst = sorted((e['g'], o['g']), key=lambda g: RICH.index(g['format']))
                maybe.append((src, dst, shared))

    def show_failed():
        print(f'\n有 {len(failed)} 个文件没导入' + ('（其他文件已导入）：' if groups else '：'))
        for path, fmt, why in failed:
            print(f'- {rel(path, project)}：{why}\n  办法：{fix_hint(path, fmt, why, project)}')

    if not groups:
        if failed:
            show_failed()
        sys.exit('没有可用的导出文件')
    if 'title' not in cfg:
        cfg = {'title': f'{groups[0]["label"]}大事记', **cfg}
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'→ {cfg_path}（{len(groups)} 个群，本次新增 {len(added)} 个）')
    rc = 0
    if not a.no_ingest:
        sys.stdout.flush()
        rc = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / 'ingest.py'), '--project', str(project)]).returncode
    q = shlex.quote
    me = q(str(Path(__file__).resolve()))
    if renamed:
        print(f'\n注意：{"、".join(renamed)} 群的名字取自文件名，页面上会显示——到 config 的 groups[].label 改成好认的名字'
              '（网站标题在 title / pages.name）。')
    for g1, g2, n in maybe:
        print(f'\n疑似同一个群：[{g1["key"]}] {g1["label"]}（{g1["format"]}）和 [{g2["key"]}] {g2["label"]}（{g2["format"]}）'
              f'有 {n} 条消息的时间和内容一样。是同一个群就合并：\n  python3 {me} --project {q(str(project))} --same {g1["key"]}={g2["key"]}')
    if failed:
        show_failed()
    if rc:
        sys.exit(rc)
    if not a.no_ingest:
        print(f'\n下一步：python3 {q(str(Path(__file__).resolve().parent / "roster.py"))} --project {q(str(project))} build')


if __name__ == '__main__':
    main()
