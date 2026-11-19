"""各脚本共用的小工具：读配置、读 all.json、判断消息类型、人名映射。不单独运行。"""
import argparse
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ME = 'me'  # all.json 里作者本人的发言人写法（显示名在 config.me）

# 非文字占位符的种类（与 CONTRACT.md 一致）；c 以 "[种类]" 开头即视为非文字消息
KINDS = ('图片', '语音', '表情', '视频', '文章', '链接', '小程序', '视频号', '音乐', '文件', '位置',
         '红包', '转账', '拍一拍', '聊天记录', '名片', '接龙', '通话', '其他')
KIND_RE = re.compile(r'^\[(%s)\]' % '|'.join(KINDS))
REPLY_RE = re.compile(r'（回复 ([^:：]*?): .*?）$')
QUESTION = re.compile(r'[?？]|吗|啥|什么|怎么|为啥|为什么|是不是|有没有|呢$')
LINKS = ('文章', '链接', '小程序', '视频号', '音乐', '聊天记录', '文件')
LIST_ITEM = re.compile(r'^\d+\s*[.、)）]')  # 接龙的「1. 某某」：统计口头禅时不算


def _with_project(argv):
    """兼容旧写法 `xxx.py <项目目录> ...`：没写 --project 时，第一个参数若是目录就当项目目录。"""
    if any(x == '--project' or x.startswith('--project=') for x in argv):
        return argv
    if argv and not argv[0].startswith('-') and Path(argv[0]).expanduser().is_dir():
        return ['--project', argv[0]] + argv[1:]
    return argv


def args(doc, extra=None, argv=None):
    """统一的参数解析：--project <dir>（也可直接把项目目录写成第一个参数；都不写 = 当前目录），extra(parser) 可再加参数。"""
    p = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--project', default='.', help='项目目录（含 chronicle.config.json），默认当前目录')
    if extra:
        extra(p)
    a = p.parse_args(_with_project(sys.argv[1:] if argv is None else argv))
    a.project = Path(a.project).expanduser().resolve()
    cfg_path = a.project / 'chronicle.config.json'
    if not cfg_path.exists():
        sys.exit(f'找不到 {cfg_path}')
    a.cfg = with_defaults(read_config(cfg_path))
    a.work = a.project / 'work'
    return a


# config 里认识的键 → 允许的类型（见 CONTRACT.md）。写错类型直接报错，不认识的键只提示（附拼写相近的建议）。
CONFIG_TYPES = {
    'title': str, 'me': str, 'groups': list, 'aliases': dict, 'core': list, 'members': list, 'people': list,
    'gender': dict, 'relations': list, 'taboo_extra': list, 'fonts': dict, 'tier': str, 'deep_read': list,
    'lang': str, 'scale': str, 'periods': list, 'public_detail': str, 'privacy': dict,
    'sensitive_words': list, 'real_names': (list, dict), 'blocked_snippets': list, 'family_safe': bool,
    'nicknames': dict, 'metric_words': dict, 'holdout_sensitive': list, 'author_title': str, 'worker_name': str,
    'pages': dict, 'stats': dict,
}
CONFIG_CHOICES = {'tier': ('lite', 'standard', 'deep'), 'lang': ('zh', 'en'), 'scale': ('group', 'pair', 'large'),
                  'public_detail': ('standard', 'full')}
GROUP_KEYS = ('key', 'label', 'file', 'format', 'columns', 'date')
TYPE_NAME = {str: '字符串', list: '列表 [...]', dict: '对象 {...}', bool: 'true/false'}


def read_config(path):
    """读 chronicle.config.json：JSON 写错时报出行列号；再按 CONFIG_TYPES 校验。"""
    try:
        cfg = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as e:
        sys.exit(f'{path} 不是合法的 JSON：第 {e.lineno} 行第 {e.colno} 列附近（{e.msg}）。'
                 '常见原因：漏了逗号、多了结尾逗号、用了中文引号。')
    except UnicodeDecodeError:
        sys.exit(f'{path} 不是 UTF-8 编码，请另存为 UTF-8')
    if not isinstance(cfg, dict):
        sys.exit(f'{path} 最外层应该是一个对象 {{...}}')
    check_config(cfg, str(path))
    return cfg


def _type_ok(v, t):
    ts = t if isinstance(t, tuple) else (t,)
    return isinstance(v, ts) and not (bool not in ts and isinstance(v, bool))


def check_config(cfg, where='config'):
    errs, warns = [], []
    for k, v in cfg.items():
        if k.startswith('_') or k.startswith('//'):
            continue  # 注释
        if k not in CONFIG_TYPES:
            near = difflib.get_close_matches(k, CONFIG_TYPES, n=1, cutoff=0.6)
            warns.append(f'不认识的键 "{k}"' + (f'，是不是 "{near[0]}"？' if near else '（会被忽略）'))
            continue
        t = CONFIG_TYPES[k]
        if v is None:
            continue
        if not _type_ok(v, t):
            want = ' 或 '.join(TYPE_NAME[x] for x in (t if isinstance(t, tuple) else (t,)))
            hint = f'，例如 "{k}": ["{v}"]' if list in (t if isinstance(t, tuple) else (t,)) and isinstance(v, str) else ''
            errs.append(f'"{k}" 应该是{want}，现在是 {type(v).__name__}{hint}')
        elif k in CONFIG_CHOICES and v not in CONFIG_CHOICES[k]:
            errs.append(f'"{k}" 只能取 {" / ".join(CONFIG_CHOICES[k])}，现在是 {v!r}')
    for i, g in enumerate(cfg.get('groups') or []):
        if not isinstance(g, dict):
            errs.append(f'groups[{i}] 应该是对象 {{"key", "label", "file", "format"}}')
            continue
        miss = [x for x in ('key', 'label', 'file', 'format') if not g.get(x)]
        if miss:
            errs.append(f'groups[{i}] 缺 {"、".join(miss)}')
        for x in g:
            if x not in GROUP_KEYS and not x.startswith('_'):
                near = difflib.get_close_matches(x, GROUP_KEYS, n=1, cutoff=0.6)
                warns.append(f'groups[{i}] 里不认识的键 "{x}"' + (f'，是不是 "{near[0]}"？' if near else ''))
        f = g.get('file')
        if f is not None and not isinstance(f, (str, list)):
            errs.append(f'groups[{i}].file 应该是路径字符串或列表')
    pv = cfg.get('privacy')
    if isinstance(pv, dict) and pv.get('strict') is not None and not isinstance(pv['strict'], bool):
        errs.append(f'"privacy.strict" 应该是 true/false（不加引号），现在是 {pv["strict"]!r}')
    for k in ('members', 'core', 'people', 'sensitive_words', 'taboo_extra', 'relations', 'deep_read', 'blocked_snippets'):
        if isinstance(cfg.get(k), list) and not all(isinstance(x, str) for x in cfg[k]):
            errs.append(f'"{k}" 里每一项都应该是字符串')
    for w in warns:
        print(f'提示（{where}）：{w}', file=sys.stderr)
    if errs:
        sys.exit(f'{where} 有问题：\n- ' + '\n- '.join(errs))


def with_defaults(cfg):
    """config.core（核心人物，roster.py apply 写入）是“要写的人”的缺省：没写 people 时 people = core。
    members 的缺省（core + 发言量推断）在 members() 里。"""
    if not cfg.get('people') and cfg.get('core'):
        cfg['people'] = list(cfg['core'])
    return cfg


def load_all(a):
    f = a.work / 'all.json'
    if not f.exists():
        sys.exit(f'找不到 {f}，先运行 ingest.py')
    return json.loads(f.read_text(encoding='utf-8'))


def kind(c):
    """消息类型：'文字' 或占位符种类（只看开头的占位符；带配文的图片/链接仍算占位符种类）。"""
    m = KIND_RE.match(c)
    return m.group(1) if m else '文字'


def body(c):
    """正文：去掉开头的占位符（`[图片] 配文` → `配文`）、引用回复尾巴、换行标记。"""
    return KIND_RE.sub('', REPLY_RE.sub('', c), count=1).replace(' ⏎ ', '\n').strip()


def is_text(m):
    """有文字：纯文字消息，或去掉占位符后还有配文/标题的消息（与 split_chunks 的口径一致）。"""
    return bool(body(m['c']))


def is_pure_text(m):
    """严格的纯文字消息（不以占位符开头）。turnmix 判发言类型时用。"""
    return kind(m['c']) == '文字'


def reply_to(c):
    m = REPLY_RE.search(c)
    return m.group(1) if m else None


def sender_key(cfg, person):
    """config.people 里的显示名 → all.json 里的 s（作者本人是 me）。"""
    return ME if person == cfg.get('me') else person


def display(cfg, s):
    return cfg.get('me', ME) if s == ME else s


def people(cfg, only=None):
    """要写人物志/人物模型的人（config.people，可只填一人）。"""
    ps = cfg.get('people') or []
    if only:
        ps = [p for p in ps if p in only]
    if not ps:
        sys.exit('config.people 为空（或 --person 不在其中）')
    return ps


MEMBER_MIN_SHARE = 0.01  # 未配置 members 时：发言量 ≥ 全部消息 1%（且 ≥10 条）的发言人算成员
_warned = set()


def members(cfg, allm=None):
    """全体成员（统计、点名、横向对比用）：config.members ∪ config.core ∪ config.people；
    没配 members 时由 all.json 里发言量 ≥ 阈值的发言人推断，并打印提示。返回显示名列表。"""
    ms = list(cfg.get('members') or [])
    if not ms and allm is not None:
        cnt = Counter(m['s'] for m in allm)
        least = max(10, int(len(allm) * MEMBER_MIN_SHARE))
        ms = [display(cfg, s) for s, n in cnt.most_common() if n >= least]
        if 'members' not in _warned:
            _warned.add('members')
            print(f'提示：config.members 未配置，按发言量 ≥{least} 条推断全体成员为：{"、".join(ms) or "（无）"}'
                  '——不对就在 config.members 里写全。', file=sys.stderr)
    for p in (cfg.get('core') or []) + (cfg.get('people') or []):
        if p not in ms:
            ms.append(p)
    return ms


def main_group(cfg):
    gs = cfg.get('groups') or []
    return gs[0]['label'] if gs else None


def names_of(cfg, allm=None):
    """每位成员的所有称呼：显示名 + aliases 反查 + 可选 nicknames。用于“点名”判断。只收 ≥2 字的。"""
    out = {}
    for p in members(cfg, allm):
        s = sender_key(cfg, p)
        ns = {p} | {k for k, v in (cfg.get('aliases') or {}).items() if v == p}
        ns |= set((cfg.get('nicknames') or {}).get(p, []))
        out[s] = sorted((n for n in ns if len(n) >= 2 and not n.isdigit()), key=len, reverse=True)
    return out


def all_names(cfg, allm=None):
    """所有成员的称呼（显示名、作者本人、aliases 两侧、nicknames）。口头禅统计排除“纯称呼”用。"""
    out = set(members(cfg, allm)) | {cfg.get('me') or ''} | set(cfg.get('aliases') or {}) | set((cfg.get('aliases') or {}).values())
    for v in (cfg.get('nicknames') or {}).values():
        out |= set(v)
    return {x for x in out if x}


def safe(name):
    return re.sub(r'[\\/:*?"<>|\s]+', '_', name)


def turns(msgs):
    """按群切 turn：同群连续同一人的消息为一个 turn。返回 [(群, 发言人, [msg 下标...])]，按首条时间排序。"""
    last = {}
    out = []
    for i, m in enumerate(msgs):
        cur = last.get(m['g'])
        if cur is not None and out[cur][1] == m['s']:
            out[cur][2].append(i)
        else:
            out.append((m['g'], m['s'], [i]))
            last[m['g']] = len(out) - 1
    return out
