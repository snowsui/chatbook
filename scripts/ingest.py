"""读取各群导出 → 标准化 → 写 work/all.json（格式见 CONTRACT.md）。

用法：
  python3 scripts/ingest.py --project <dir>

config.groups[] 每项：{"key": "A", "label": "主群", "file": "exports/a.json", "format": "..."}
  file 相对项目目录，也可写绝对路径；同一个群的多次导出写成列表 "file": ["旧.json", "新.json"]，
  按平台消息 ID（没有就按 时间+发送者+内容）去重合并。列表元素也可以写成 {"file": "旧.txt", "format": "txt", "date": "2024-01-01"}，
  用来把同一个群的不同格式导出并在一起（这时按 分钟+内容 去重）。init_project.py 会自动识别格式、写这一项。format 取值：
  json-array  通用 JSON 数组，每条一个对象：time（"2019-01-01 12:00:00"）或 timestamp（秒）、sender、content，
            可选 sender_id、msg_id、type（text / image / voice / video / sticker / link / file / system …，见 ARRAY_KIND）、
            is_self、title（链接/文件的标题）、reply_to（被回复消息的 msg_id，或 {"msg_id", "sender", "sender_id", "content"}）
  chatlab   ChatLab 开放格式 {"chatlab":{...},"meta":{...},"members":[...],"messages":[...]}
  txt       纯文本，逐行尝试：
              2019-01-01 12:00:00 张三: 内容
              [2019-01-01 12:00] 张三：内容
              张三 2019/1/1 12:00:00        （下一行起是内容；日期可写 2019-01-01，秒可省）
            解析不了的行并入上一条（多行消息）。
            整份文件一行带时间的都没有时，按「张三：内容」逐行读（无时间形态，手动复制常见）：
              日期来自文件里单独一行的日期（2024-01-01 / 2024/1/1 / 2024年1月1日，之后的消息都算这一天），
              或 group 里写 "date": "2024-01-01"；每条按文件顺序从 00:00:00 起每条 +1 秒。
              两者都没有就报错。时刻是假的：这个群记进 work/ingest.json 的 no_time，数据页的作息类统计自动排除它。
  csv       默认列 time,sender,content；可在 group 里写 "columns": {"time":"时间","sender":"发送者","content":"内容","id":"消息ID"}
  qq        QQ 消息管理器导出 txt：「2019-01-01 12:00:00 昵称(QQ号)」下一行起是内容
  telegram  Telegram Desktop 导出的 result.json

文本编码：先按 UTF-8 读，不是的话依次试 GB18030、UTF-16，读出来会提示用的哪种。
作者本人：json-array 的 is_self、chatlab 的 meta.ownerId 自动识别；其他格式用 aliases 把作者的昵称/账号映射成 config.me。
aliases 的键既可以是昵称，也可以是平台账号（sender_id / QQ号 / platformId / Telegram from_id）。

旁路文件（只有指定的脚本读）：
  work/senders.json（roster.py）：{"v": 1, "rows": [[u, n, r], ...]}，第 i 项对应 all.json 第 i 条：
    u = 发送者平台账号（"<平台>:<账号>"，没有就是 null），n = 导出里的原始昵称（未过 aliases），
    r = 被引用消息的稳定键（有引用 ID 时，否则 null）。
  work/ingest.json（build_stats.py）：{"v": 1, "no_time": [没有真实时刻的群 label]}。
"""
import calendar
import collections
import csv
import io
import json
import re
import shlex
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ME, REPLY_RE, args, members  # noqa: E402

DROP = object()  # 适配器返回此值表示丢弃（系统消息、撤回提示）
NOTIME = set()   # 按无时间形态读的文件（ingest 据此把群记进 work/ingest.json 的 no_time）
_decoded = {}


def read_text(path):
    """读文本：UTF-8（可带 BOM）→ UTF-16（有 BOM 或满是 \\0）→ GB18030；不是 UTF-8 时提示一次用的哪种。都不行就报错。"""
    path = Path(path)
    raw = path.read_bytes()
    tries = ['utf-8-sig']
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff') or raw[:200].count(b'\0') > 10:
        tries.append('utf-16')
    tries.append('gb18030')
    for enc in tries:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if '\0' in text:
            continue
        if enc != 'utf-8-sig' and path not in _decoded:
            _decoded[path] = enc
            print(f'提示：{path.name} 不是 UTF-8，已按 {enc.upper()} 读取（内容乱码的话先转成 UTF-8）', file=sys.stderr)
        return text
    q = shlex.quote(str(path))
    raise ValueError(f'认不出文本编码（试过 UTF-8、GB18030、UTF-16）。先转成 UTF-8 再导入，例如：'
                     f'iconv -f <原编码> -t UTF-8 {q} > {shlex.quote(str(path.with_suffix(".utf8" + path.suffix)))}')


def clip(c, n=300):
    c = (c or '').replace('\r\n', '\n').replace('\r', '\n').strip().replace('\n', ' ⏎ ')
    return c[:n] + ('…' if len(c) > n else '')


def with_reply(text, who, quoted):
    if who is None and not quoted:
        return text
    q = (quoted or '').replace('\n', ' ').strip()[:40]
    return f'{text}（回复 {who or "?"}: {q}）'


TIME_FMTS = ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M')


def parse_time(s):
    s = str(s).strip()
    if re.fullmatch(r'\d{10}(\.\d+)?', s):
        return datetime.fromtimestamp(float(s))
    if re.fullmatch(r'\d{13}', s):
        return datetime.fromtimestamp(int(s) / 1000)
    s = re.sub(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', lambda m: '%s-%02d-%02d' % (m[1], int(m[2]), int(m[3])), s)
    s = re.sub(r'(?<=[ T])(\d):', r'0\1:', s).replace('T', ' ')
    s = re.sub(r'(\.\d+)?([+-]\d{2}:?\d{2}|Z)?$', '', s)
    for f in TIME_FMTS:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    raise ValueError(f'无法解析时间：{s!r}')


def rec(t, s, c, pid=None, uid=None, ts=None, self=False, ref=None, plat=None):
    """适配器产出的统一中间记录。t: datetime; s: 原始昵称; uid: 平台账号; pid: 平台消息ID; ref: 被引用消息的平台ID; plat: 账号所属平台。"""
    return {'t': t, 's': s, 'uid': uid, 'c': c, 'pid': pid, 'ts': ts, 'self': self, 'ref': ref, 'plat': plat}


# ---------------- json-array ----------------
# type 的取值（大小写不敏感；中文类型名也认）→ 占位符种类。text / reply 是文字，system 丢弃，其他没列出的记为 [其他]。
ARRAY_KIND = {'image': '图片', 'photo': '图片', 'sticker': '表情', 'emoji': '表情', 'voice': '语音', 'audio': '语音',
              'video': '视频', 'article': '文章', 'link': '链接', 'mini-program': '小程序', 'channel-video': '视频号',
              'music': '音乐', 'file': '文件', 'location': '位置', 'red-packet': '红包', 'transfer': '转账', 'pat': '拍一拍',
              'chat-history': '聊天记录', 'contact': '名片', 'solitaire': '接龙', 'call': '通话',
              '图片': '图片', '表情': '表情', '语音': '语音', '视频': '视频', '文章': '文章', '链接': '链接',
              '小程序': '小程序', '视频号': '视频号', '视频号直播': '视频号', '音乐': '音乐', '文件': '文件',
              '位置': '位置', '实时位置共享': '位置', '红包': '红包', '转账': '转账', '拍一拍': '拍一拍',
              '聊天记录': '聊天记录', '名片': '名片', '企业微信联系人': '名片', '接龙': '接龙', '通话': '通话'}
ARRAY_TEXT = {'', 'text', 'reply', '文本', '引用回复'}
ARRAY_SYSTEM = {'system', 'recall', '系统提示', '系统通知'}
WITH_TITLE = {'文章', '链接', '小程序', '视频号', '音乐', '文件', '位置', '聊天记录', '接龙', '拍一拍'}


# 兼容早期导出的字段名（不在文档里写）
LEGACY_KEYS = {'server_id': 'msg_id', 'type_name': 'type'}


def _arr(x):
    """一条消息 → 统一字段（同时认 LEGACY_KEYS 里的旧字段名）。"""
    y = dict(x)
    for old, key in LEGACY_KEYS.items():
        if x.get(old) is not None and (y.get(key) is None or (key == 'type' and not isinstance(y.get(key), str))):
            y[key] = x[old]  # 旧导出的 type 是数字码，类型名在 type_name 里
    x = y
    d = x.get('detail') if isinstance(x.get('detail'), dict) else {}
    ref = x.get('reply_to')
    if ref is None and isinstance(d.get('refer'), dict):
        r = {LEGACY_KEYS.get(k, k): v for k, v in d['refer'].items()}
        ref = {'msg_id': r.get('svrid'), 'sender': r.get('sender'), 'sender_id': r.get('sender_id'), 'content': r.get('summary')}
    return {'time': x.get('time'), 'ts': x.get('timestamp'), 'sender': x.get('sender'), 'uid': x.get('sender_id'),
            'pid': x.get('msg_id'), 'type': str(x.get('type') or '').strip().lower(), 'content': x.get('content') or '',
            'text': d.get('text'), 'title': x.get('title') or d.get('title'), 'self': bool(x.get('is_self')), 'ref': ref}


def read_json_array(path, g, norm):
    data = [_arr(x) for x in json.loads(read_text(path)) if isinstance(x, dict)]
    # 同一账号最常用的昵称，用来把引用回复里的旧昵称归一
    names = collections.defaultdict(collections.Counter)
    selfid = set()
    byid = {}
    for x in data:
        if x['pid'] not in (None, ''):
            byid[str(x['pid'])] = x
        if x['uid'] and x['type'] not in ARRAY_SYSTEM:
            names[x['uid']][x['sender']] += 1
            if x['self']:
                selfid.add(x['uid'])
    for x in data:
        tp = x['type']
        if tp in ARRAY_SYSTEM or x['sender'] == '系统':
            continue
        c = x['content']
        ref = None
        if tp in ARRAY_TEXT:
            r = x['ref']
            if r is not None and not isinstance(r, dict):
                hit = byid.get(str(r))
                r = {'msg_id': r, 'sender': hit and hit['sender'], 'sender_id': hit and hit['uid'],
                     'content': hit and (hit['text'] or hit['content'])} if hit else {'msg_id': r}
            body_ = x['text'] or c
            if r:
                ref = r.get('msg_id')
                uid = r.get('sender_id')
                top = uid and names[uid].most_common(1)
                who = norm(top[0][0] if top else r.get('sender'), uid, uid in selfid) if (uid or r.get('sender')) else None
                c = with_reply(body_, who, r.get('content'))
            else:
                c = body_
        else:
            k = ARRAY_KIND.get(tp, '其他')
            title = x['title'] or re.sub(r'^\[[^\]]*\]\s*', '', c)
            c = f'[{k}]' + (' ' + title[:80] if title and (k in WITH_TITLE or k == '其他') else '')
            if k == '其他':
                c = f'[其他] {tp} {title[:60]}'.rstrip()
        t = parse_time(x['time']) if x['time'] else parse_time(x['ts'])
        yield rec(t, x['sender'], c, pid=x['pid'] or None, uid=x['uid'], ts=x['ts'], self=x['self'], ref=ref, plat='wx')


# ---------------- chatlab ----------------
PLAT = {'wechat': 'wx', 'weixin': 'wx', 'qq': 'qq', 'telegram': 'tg'}  # 账号命名空间（内部前缀）
CL_KIND = {1: '图片', 2: '语音', 3: '视频', 4: '文件', 5: '表情', 7: '链接', 8: '位置', 20: '红包', 21: '转账',
           22: '拍一拍', 23: '通话', 24: '小程序', 26: '聊天记录', 27: '名片'}


def read_chatlab(path, g, norm):
    data = json.loads(read_text(path))
    owner = (data.get('meta') or {}).get('ownerId')
    plat = PLAT.get((data.get('meta') or {}).get('platform'), (data.get('meta') or {}).get('platform') or 'chatlab')
    member = {m.get('platformId'): (m.get('groupNickname') or m.get('accountName')) for m in data.get('members') or []}
    msgs = data.get('messages') or []
    byid = {str(m.get('platformMessageId')): m for m in msgs if m.get('platformMessageId') is not None}

    def name(m):
        return m.get('groupNickname') or m.get('accountName') or member.get(m.get('sender')) or str(m.get('sender'))

    for m in msgs:
        tp = m.get('type', 0)
        if tp in (80, 81):
            continue
        c = m.get('content') or ''
        rid = None
        if tp in (0, 25):
            rid = m.get('replyToMessageId')
            if rid is not None and str(rid) in byid:
                r = byid[str(rid)]
                c = with_reply(c, norm(name(r), r.get('sender'), r.get('sender') == owner), r.get('content'))
        else:
            k = CL_KIND.get(tp, '其他')
            c = f'[{k}]' + (' ' + c[:80] if c and k not in ('图片', '语音', '视频', '表情') else '')
        yield rec(datetime.fromtimestamp(m['timestamp']), name(m), c, pid=m.get('platformMessageId'),
                  uid=m.get('sender'), ts=m['timestamp'], self=owner is not None and m.get('sender') == owner,
                  ref=rid, plat=plat)


# ---------------- txt ----------------
DT = r'(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)'
TXT_LINE = [re.compile(r'^' + DT + r'\s+(.+?)\s?[:：]\s?(.*)$'),          # 2019-01-01 12:00:00 张三: 内容
            re.compile(r'^\[' + DT + r'\]\s*(.+?)\s?[:：]\s?(.*)$')]      # [2019-01-01 12:00] 张三：内容
TXT_HEAD = re.compile(r'^(.+?)\s+' + DT + r'$')                           # 张三 2019/1/1 12:00:00
TXT_DATE = re.compile(r'^\s*(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*日?\s*$')  # 单独一行的日期
TXT_NOTIME = re.compile(r'^([^\s:：][^:：]{0,23}?)\s?[:：](?!//)\s?(.*)$')  # 张三：内容（无时间形态；昵称 ≤24 字）


def read_lines(path, head_re, line_res, mkhead):
    cur = None
    for raw in read_text(path).splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        hit = None
        for r in line_res:
            mm = r.match(line)
            if mm:
                hit = rec(parse_time(mm[1]), mm[2].strip(), mm[3])
                break
        if hit is None and head_re:
            mm = head_re.match(line)
            if mm:
                hit = mkhead(mm)
        if hit is not None:
            if cur and cur['c'].strip():
                yield cur
            cur = hit
        elif cur is not None:
            cur['c'] = (cur['c'] + '\n' + line) if cur['c'] else line
    if cur and cur['c'].strip():
        yield cur


def read_txt(path, g, norm):
    timed = list(read_lines(path, TXT_HEAD, TXT_LINE, lambda mm: rec(parse_time(mm[2]), mm[1].strip(), '')))
    if timed:
        return timed
    NOTIME.add(Path(path))
    return read_txt_notime(path, g)


def read_txt_notime(path, g):
    """「张三：内容」无时间形态：日期取文件里的日期行或 group.date，每天从 00:00:00 起按顺序每条 +1 秒。"""
    day = None
    if g.get('date'):
        mm = TXT_DATE.match(str(g['date']))
        if not mm:
            raise ValueError(f'group.date 写成 YYYY-MM-DD：{g["date"]!r}')
        day = datetime(int(mm[1]), int(mm[2]), int(mm[3]))
    seq, cur, out = collections.Counter(), None, []
    for raw in read_text(path).splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        mm = TXT_DATE.match(line)
        if mm:
            day = datetime(int(mm[1]), int(mm[2]), int(mm[3]))
            continue
        mm = TXT_NOTIME.match(line)
        if mm:
            if day is None:
                raise ValueError('这份 txt 没有时间也没有日期行：在文件开头加一行日期（如 2024-01-01），'
                                 '或在 config 的这个群里写 "date": "2024-01-01"（init_project 可写成 文件:txt@2024-01-01）')
            if cur and cur['c'].strip():
                out.append(cur)
            cur = rec(day + timedelta(seconds=seq[day]), mm[1].strip(), mm[2])
            seq[day] += 1
        elif cur is not None:
            cur['c'] = (cur['c'] + '\n' + line) if cur['c'] else line
    if cur and cur['c'].strip():
        out.append(cur)
    return out


# ---------------- qq ----------------
QQ_HEAD = re.compile(r'^(\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{2}:\d{2})\s+(.*?)(?:\((\d+)\)|<([^>]+)>)?$')


def read_qq(path, g, norm):
    def mk(mm):
        return rec(parse_time(mm[1]), mm[2].strip(), '', uid=mm[3] or mm[4], plat='qq')
    for r in read_lines(path, QQ_HEAD, [], mk):
        if r['uid'] in ('10000', '1000000') or r['s'] == '系统消息':
            continue
        yield r


# ---------------- csv ----------------
def read_csv(path, g, norm):
    col = {'time': 'time', 'sender': 'sender', 'content': 'content', 'id': 'id'}
    col.update(g.get('columns') or {})
    for row in csv.DictReader(io.StringIO(read_text(path), newline='')):
        if not (row.get(col['time']) or '').strip():
            continue
        yield rec(parse_time(row[col['time']]), (row.get(col['sender']) or '').strip(),
                  row.get(col['content']) or '', pid=(row.get(col['id']) or None))


# ---------------- telegram ----------------
def tg_text(t):
    if isinstance(t, str):
        return t
    return ''.join(x if isinstance(x, str) else x.get('text', '') for x in t or [])


TG_MEDIA = {'sticker': '表情', 'voice_message': '语音', 'video_file': '视频', 'video_message': '视频',
            'animation': '表情', 'audio_file': '音乐'}


def read_telegram(path, g, norm):
    data = json.loads(read_text(path))
    msgs = data.get('messages') or []
    byid = {m.get('id'): m for m in msgs}
    for m in msgs:
        if m.get('type') != 'message':
            continue
        text = tg_text(m.get('text'))
        k = None
        if 'photo' in m:
            k = '图片'
        elif m.get('media_type') in TG_MEDIA:
            k = TG_MEDIA[m['media_type']]
        elif 'file' in m:
            k = '文件'
        elif 'location_information' in m:
            k = '位置'
        elif 'poll' in m:
            k, text = '其他', '投票 ' + (m['poll'].get('question') or '')
        if k:
            c = f'[{k}]' + (' ' + text[:80] if text else '')
        else:
            c = text
        if m.get('forwarded_from') and not k:
            c = f'[聊天记录] 转发自 {m["forwarded_from"]}：{text[:80]}'
        r = byid.get(m.get('reply_to_message_id'))
        ref = m.get('reply_to_message_id') if r and not k else None
        if r and not k:
            c = with_reply(c, norm(r.get('from') or '?', r.get('from_id')), tg_text(r.get('text')))
        if not c.strip():
            continue
        t = datetime.fromtimestamp(int(m['date_unixtime'])) if m.get('date_unixtime') else parse_time(m['date'])
        yield rec(t, m.get('from') or m.get('actor') or '?', c, pid=m.get('id'), uid=m.get('from_id'),
                  ts=int(m['date_unixtime']) if m.get('date_unixtime') else None, ref=ref, plat='tg')


ADAPTERS = {'json-array': read_json_array, 'chatlab': read_chatlab, 'txt': read_txt, 'csv': read_csv,
            'qq': read_qq, 'telegram': read_telegram}
def group_files(g):
    """config.groups[].file：字符串，或同一个群多次导出的列表（元素是路径，或 {"file", "format", "date"}）。返回路径列表。"""
    return [x['file'] if isinstance(x, dict) else x for x in group_entries(g)]


def group_entries(g):
    f = g.get('file')
    return list(f) if isinstance(f, list) else [f]


def entry_format(g, x):
    """某一份导出的格式：元素里写了 format 用它，否则用群的 format。"""
    return (x.get('format') if isinstance(x, dict) else None) or g.get('format')


def dedup_key(r):
    """同一个群多次导出的去重键：平台消息 ID；没有就用 时间 + 发送者（账号或昵称）+ 内容。"""
    if r['pid'] not in (None, '', 0):
        return ('p', str(r['pid']))
    return ('l', r['t'], str(r['uid']) if r['uid'] is not None else r['s'], (r['c'] or '').strip())


def loose_key(r):
    """不同格式的导出没有共同的消息 ID、发送者写法也可能不同：按 分钟 + 内容 去重。"""
    return ('x', r['t'].strftime('%Y-%m-%d %H:%M'), re.sub(r'\s+', '', r['c'] or ''))


def read_group(g, project, norm):
    """读一个群的全部导出文件；多份时按 dedup_key（混合格式时按 loose_key）做“多重集取最大”合并
    （同一份里本来就重复的消息保留）。返回 (记录列表, 去重掉的条数, 是否有无时间的文件)。"""
    entries = group_entries(g)
    mixed = len({entry_format(g, x) for x in entries}) > 1
    out, seen, dropped, notime = [], collections.Counter(), 0, False
    for x in entries:
        f, fmt = (x['file'] if isinstance(x, dict) else x), entry_format(g, x)
        gx = {**g, **x} if isinstance(x, dict) else g
        path = Path(f).expanduser()
        if not path.is_absolute():
            path = project / path
        here = collections.Counter()
        try:
            recs = list(ADAPTERS[fmt](path, gx, norm))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            raise ValueError(f'{f}（{fmt}）：{e}') from None
        notime |= path in NOTIME
        for r in recs:
            key = loose_key(r) if mixed else dedup_key(r)
            here[key] += 1
            if here[key] <= seen[key]:
                dropped += 1
                continue
            out.append(r)
        for key, n in here.items():
            seen[key] = max(seen[key], n)
    if len(entries) > 1:
        out.sort(key=lambda r: r['t'])  # 稳定排序：同一秒内保持先旧导出、后新导出的顺序
    return out, dropped, notime


def main():
    a = args(__doc__)
    cfg = a.cfg
    aliases = cfg.get('aliases') or {}
    me_name = cfg.get('me')

    def norm(name, uid=None, self=False):
        if self:
            return ME
        n = aliases[str(uid)] if uid is not None and str(uid) in aliases else aliases.get(name, name)
        return ME if me_name and n == me_name else n

    def fix_reply(c):
        """引用回复 `（回复 X: …）` 里的 X 也过 aliases；作者本人写成 config.me 的显示名（所有格式统一在这里处理）。"""
        def sub(m):
            who = norm(m.group(1).strip()) if m.group(1).strip() not in ('', '?') else m.group(1)
            who = (me_name or ME) if who == ME else who
            return m.group(0)[:m.start(1) - m.start(0)] + who + m.group(0)[m.end(1) - m.start(0):]
        return REPLY_RE.sub(sub, c)

    allm, no_time = [], []
    for gi, g in enumerate(cfg['groups']):
        bad = [entry_format(g, x) for x in group_entries(g) if entry_format(g, x) not in ADAPTERS]
        if bad:
            sys.exit(f'群 {g.get("label")} 的 format={bad[0]!r} 不支持，可选：{", ".join(ADAPTERS)}')
        try:
            recs, dropped, notime = read_group(g, a.project, norm)
        except (ValueError, OSError) as e:
            sys.exit(f'[{g.get("key")}] {g.get("label")} 读取失败：{e}')
        fmt = '+'.join(dict.fromkeys(entry_format(g, x) for x in group_entries(g)))
        if notime:
            no_time.append(g['label'])
        seq = collections.Counter()
        rows = []
        for r in recs:
            t = r['t'].strftime('%Y-%m-%d %H:%M:%S')
            ts = r['ts'] if r['ts'] is not None else calendar.timegm(r['t'].timetuple())
            if r['pid'] not in (None, '', 0):
                k = f'{g["key"]}:{r["pid"]}'
            else:
                k = f'{g["key"]}:L{ts}_{seq[ts]}'
                seq[ts] += 1
            u = None if r['uid'] in (None, '') else (f'{r["plat"]}:{r["uid"]}' if r['plat'] else str(r['uid']))
            ref = None if r['ref'] in (None, '', 0) else f'{g["key"]}:{r["ref"]}'
            rows.append({'k': k, 'g': g['label'], 't': t, 's': norm(r['s'], r['uid'], r['self']), 'c': fix_reply(r['c']),
                         '_o': (gi, len(rows)), '_x': [u, r['s'], ref]})
        if not rows:
            print(f'[{g["key"]}] {g["label"]}: 0 条（检查文件和 format）')
            continue
        dup = len(rows) - len({x['k'] for x in rows})
        nf = len(group_files(g))
        print(f'[{g["key"]}] {g["label"]} ({fmt}{f"，{nf} 份导出合并，去重 {dropped} 条" if nf > 1 else ""}): '
              f'{len(rows)} 条，{min(x["t"] for x in rows)} ~ {max(x["t"] for x in rows)}'
              + (f'，警告：{dup} 条稳定键重复' if dup else '') + ('；没有真实时刻（作息类统计不算这个群）' if notime else ''))
        allm += rows

    allm.sort(key=lambda m: (m['t'], m['_o']))
    n = collections.Counter()
    gkey = {g['label']: g['key'] for g in cfg['groups']}
    for m in allm:
        m['c'] = clip(m['c'])
        m.pop('_o')
        key = gkey[m['g']]
        m['id'] = f'{key}{n[key]}'
        n[key] += 1
    out = [{'id': m['id'], 'k': m['k'], 'g': m['g'], 't': m['t'], 's': m['s'], 'c': m['c']} for m in allm]
    a.work.mkdir(parents=True, exist_ok=True)
    (a.work / 'all.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    (a.work / 'senders.json').write_text(json.dumps({'v': 1, 'rows': [m['_x'] for m in allm]}, ensure_ascii=False),
                                         encoding='utf-8')
    (a.work / 'ingest.json').write_text(json.dumps({'v': 1, 'no_time': no_time}, ensure_ascii=False), encoding='utf-8')
    spk = collections.Counter(m['s'] for m in out)
    print(f'合计 {len(out)} 条，{len(spk)} 位发言人 → {a.work / "all.json"}')
    shown = lambda s: f'{me_name}（作者本人）' if s == ME and me_name else ('我（作者本人）' if s == ME else s)  # noqa: E731
    print('发言最多：' + '、'.join(f'{shown(s)}({c})' for s, c in spk.most_common(15)))
    miss = [p for p in (cfg.get('members') or []) + (cfg.get('people') or []) if (ME if p == me_name else p) not in spk]
    if miss:
        print('警告：config.members/people 里这些人在数据中没有发言（检查 aliases）：' + '、'.join(dict.fromkeys(miss)))
    members(cfg, out)  # 没配 members 时打印推断结果


if __name__ == '__main__':
    main()
