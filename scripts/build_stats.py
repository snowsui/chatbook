"""「数据」页：从 work/all.json 数出群聊统计 → work/stats.json，并出单文件版 out/stats.html（数据内嵌）。

用法：python3 scripts/build_stats.py --project <dir> [--no-page]

- 只数不读：页面上没有聊天原文。例外只有三类短句——复读句、口头禅/笑法、词云的词——都要过敏感词表和隐私闸门。
- 复读句只取 config.pages.show_chat_groups 里的群（与大事记「可以展示原文的群」同一个开关；默认空 = 不展示，只算次数）。
- 口径（全部可在 config.stats 里调）、为什么这么定、哪些视图要用户拍板：references/15-stats-dashboard.md。
- 登录版网站：package_site.py 会把 out/stats.html 拆成带哈希的数据与脚本，作为第四栏 /stats。
- 没有真实时刻的群（无时间 txt，ingest 记在 work/ingest.json 的 no_time）不进作息类统计：热力图、活跃时段、
  夜猫子/早鸟、回复时延；页面脚注写明。roster.py apply --drop 排除的人（机器人、广告号）整个不计。
"""
import bisect
import collections
import json
import math
import re
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from common import LIST_ITEM, all_names, kind, reply_to  # noqa: E402
from pagekit import TEMPLATES, esc, fill, font_css, pages, tabs_html  # noqa: E402
from privacy_gate import WORK_CHANGE, Rules, enforce, real_names, scan_text  # noqa: E402

a = common.args(__doc__, lambda p: p.add_argument('--no-page', action='store_true', help='只写 work/stats.json，不出页面'))
proj, cfg = a.project, a.cfg
EN = cfg.get('lang') == 'en'
SC = {'repeat_min_people': 2, 'repeat_window_min': 10, 'phrase_max': 4 if EN else 8, 'catch_min_count': 5,
      'catch_min_months': 3, 'night': [0, 5], 'early': [5, 9], 'board_min_msgs': 200, 'divers': 'core', 'divers_n': 3,
      'hide': [], **(cfg.get('stats') or {})}
REPEAT_KEY_MAX = 6 if EN else 12  # 参与复读判定的句子长度上限（词 / 字）；展示还要 ≤ phrase_max
SESSION_GAP, OPEN_GAP, NEXT_GAP, LAT_MAX, LAT_MIN_N = 1800, 3 * 3600, 600, 12 * 3600, 10

# ---------------- 消息类型：all.json 只有占位符，按 c 开头的 [种类] 归类 ----------------
CATS = ['文字', '图片', '表情', '语音', '视频', '链接', '小程序', '其他']
CAT_OF = {'文字': '文字', '图片': '图片', '表情': '表情', '语音': '语音', '视频': '视频', '视频号': '视频',
          '文章': '链接', '链接': '链接', '音乐': '链接', '小程序': '小程序'}

# ---------------- 敏感词：内置通用表（展示的短句与词云的词都要过） ----------------
SENS_ZH = re.compile(
    r'\d{2,}|[0-9一二三四五六七八九十两百千万]+(?:块|元|万|k|w|刀|毛)|[¥￥$]|钱|工资|薪|房贷|房租|首付|贷款|红包|转账|理财|基金|股|彩礼|存款'  # 金额
    r'|病|医|药|疼|痛|发烧|烧了|咳|癌|术|住院|挂号|体检|血|核酸|阳了|感冒|吐了|过敏|失眠|抑郁|焦虑'  # 健康
    r'|孕|胎|生(?!日|快)|恭喜|婚|宝宝|宝贝|娃|孩子|产|奶粉|喂奶|母乳|月子|姨妈|例假|怀|备|预产|B超|宫|当妈|当爹|奶爸|接班人|下一代|添丁'  # 孕育
    r'|小区|地址|住址|路|号楼|单元|栋|室|街|门牌'  # 住址
    r'|胖|瘦|体重|斤|减肥|秃|发际线|颜值|整容|丑'  # 外貌
    r'|离婚|分手|相亲|对象|男朋友|女朋友|男友|女友|单身|脱单|暧昧|表白|前任|约会|出轨|cp|嗑'  # 感情
    r'|' + WORK_CHANGE +  # 工作变故（与隐私闸门同一份词表）
    r'|公司|单位|集团|老板|领导|同事|上班|加班|部门|组长|经理|总监|甲方|客户'  # 公司单位
    r'|阿里|腾讯|百度|字节|美团|京东|华为|小米|网易|滴滴|快手|拼多多|携程|蚂蚁|微软|谷歌', re.I)
SENS_EN = re.compile(
    r'\d{2,}|[$£€¥]|\b(?:money|salary|paid|pay|rent|mortgage|loan|debt|bonus|wage|bucks?|grand|venmo|paypal)\b'
    r'|\b(?:sick|ill|hospital|doctor|clinic|surgery|cancer|covid|meds?|pills?|therapy|therapist|depress\w*|anxiety|diagnos\w*|pain|fever)\b'
    r'|\b(?:pregnan\w*|baby|babies|kids?|ivf|due date|period|maternity)\b'
    r'|\b(?:address|street|st\.|ave|avenue|road|apt|apartment|zip)\b'
    r'|\b(?:fat|weight|diet|skinny|bald|ugly)\b'
    r'|\b(?:ex|breakup|broke up|divorce\w*|dating|date|boyfriend|girlfriend|bf|gf|crush|single|tinder|hinge)\b'
    r'|\b(?:fired|laid off|layoffs?|quit|resign\w*|interview\w*|offer|promotion|boss|manager|company|office|coworkers?|colleagues?|work|job)\b', re.I)
SENS = SENS_EN if EN else SENS_ZH
SAFE_NUM = re.compile(r'^(?:6+|2333*|\+?1+|8+|9+)$')  # 666、2333、+1、888 不是数字信息
EMOJI_CODE = re.compile(r'\[[^\[\]]{1,8}\]')  # 微信小表情 [捂脸]
if EN:
    LAUGH = re.compile(r'^(?:(?:ha)+h?|(?:he)+h?|lol+|lmao+|lmfao|rofl|xd+|😂|🤣|💀|[!.~ ])+$', re.I)
    QUESTION = re.compile(r'\?|^(?:what|why|how|when|where|who|which|anyone|is|are|do|does|did|can|could|should|would)\b', re.I)
    GENERIC = {'ok', 'okay', 'k', 'yes', 'yeah', 'yep', 'no', 'nope', 'same', 'true', 'nice', 'cool', 'sure', 'thanks', 'thx',
               'ty', 'np', 'me too', 'me', 'agreed', '+1', 'right', 'fr', 'bet', 'good', 'wow', 'omg', 'night', 'gn', 'morning'}
else:
    LAUGH = re.compile(r'^(?:[哈嘿嘻呵嘎桀噗咯hH]|笑死(?:我了)?|xswl|233+)+[!！~～。.…]*$')
    QUESTION = re.compile(r'[?？]|[吗嘛么呢]$|^(?:啥|什么|咋|怎么|为啥|谁|哪)')
    # 两个人先后说同一句，常常只是各自回答同一个问题（“我也是”“不去”），不是复读梗；单拎出来展示还容易断章取义
    GENERIC = set('好的 好 好吧 收到 可以 行 对 对的 对啊 是的 是啊 嗯 嗯嗯 哦 哦哦 噢 啊 在 在的 我也是 我也 同 同意 +1 1 不去 去 我去 '
                  '没有 没 有 不是 是 不知道 知道了 晚安 早 早安 谢谢 谢谢谢谢 辛苦了 ok OK 好滴 好嘞 来了 到了 走了'.split())
STOP_ZH = set('''我们 你们 他们 她们 什么 怎么 这个 那个 就是 还是 可以 没有 不是 一个 现在 今天 明天 昨天 时候 感觉 知道 觉得 真的 然后 但是 因为
所以 已经 应该 自己 一下 这么 那么 还有 如果 而且 不过 起来 出来 一起 这样 那样 一样 有点 哈哈 哈哈哈 哈哈哈哈 嘿嘿 嘻嘻 呵呵 一点 好像
这种 那种 这些 那些 大家 东西 为什么 怎么样 可能 其实 比较 直接 只是 不能 不会 不要 需要 还要 要是 的话 之后 之前 以后 以前 一直 最近 刚才 刚刚 时间
今年 去年 明年 开始 看到 看看 一个人 是不是 有没有 好的 好吧 不错 没事 地方 问题 回来 过来 上去 下去 一次 两个 几个 一些 怎么办 是的 对啊 是啊
不用 这里 那里 哪里 哪个 那边 这边 多少 有人 别人 人家 只有 只能 而已 还好 太好了 好多 很多 非常 特别 确实 估计 肯定
其他 不行 不了 一般 突然 终于 居然 竟然 果然 本来 原来 简直 反正 虽然 一定 一会 完了 了吧 吧吧 啊啊 嗯嗯 哦哦 哈哈哈哈哈 图片 表情 链接 文章 小程序
引用 回复 所有人 拍了拍 视频 语音 撤回 消息 发现 以为 这是 真是 为啥 一天 有个 最后 每天 不到 或者 小时 不好 主要 我要 上次 不想 意思 下次 看着 为了
毕竟 想到 甚至 大概 过去 完全 别的 结果 个人 打算 打开 不如 分钟 听说 回去 理解 是因为 基本 不然 每次 一年 情况 后面 想起 三个 干嘛 可是 问问 几天
事情 容易 里面 重要 当时 好好 啥时候 考虑 关系 记得 群里 我家 这次 那次 看见 好看 一会儿 等等 然而 之类 部分 不少 只要 而是 地说 说话 告诉 我会
会不会 能不能 要不要 好不好 对不对 不知道 我觉得 怎么回事 一点儿 哪儿 这儿 那儿 有些 有的 每个 这么多 那么多 多久 多大 多长 以上 以下 左右 之间
中间 前面 上面 下面 外面 后来 一开始 刚好 正好 还没 没想到 想要'''.split())
STOP_EN = set('''the and for that this with you your are was were have has had not but just like what when where who why how all any can
could would should will its it's i'm im you're dont don't didnt didn't doesnt doesn't cant can't wont won't thats that's there their they them then
than too very really yeah yes yep okay lol lmao haha hahaha haha also about from into out our ours we've we're she he her his him been being get got
gonna wanna know think going one some more much here now still even back over only well good see said say make made want need let lets let's
time today tomorrow yesterday tonight week day did does doing done which because maybe probably actually literally thing things stuff something
anyone everyone someone guys guy dude bro omg wow nice sure right though thought way gotta oh ohh ahh hmm hey hi'''.split())

# ---------------- 读消息 ----------------
allm = common.load_all(a)
me_name = cfg.get('me') or '我'
disp = lambda s: common.display(cfg, s)
_rf, _if = a.work / 'roster.json', a.work / 'ingest.json'
DROPPED = {p['name'] for p in json.loads(_rf.read_text(encoding='utf-8')).get('people', []) if p.get('dropped')} if _rf.exists() else set()
NO_TIME = set(json.loads(_if.read_text(encoding='utf-8')).get('no_time') or []) if _if.exists() else set()
if DROPPED:
    n0 = len(allm)
    allm = [m for m in allm if disp(m['s']) not in DROPPED]
    print(f'不计 roster 排除的人（{"、".join(sorted(DROPPED))}）：{n0 - len(allm)} 条')
if not allm:
    sys.exit('all.json 是空的')
MEMBERS = common.members(cfg, allm)
PEOPLE = list(MEMBERS)  # 按人统计的对象 = 全体成员；成员以外的发言人只计入整体数字（大群里的路人不上榜）
IDX = {p: i for i, p in enumerate(PEOPLE)}
core_cfg = SC.get('core') or cfg.get('core')  # stats.core > config.core（核心人物）> people（≥3 人）> members
if core_cfg:
    CORE = [p for p in core_cfg if p in IDX]
elif len(cfg.get('people') or []) >= 3:
    CORE = [p for p in cfg['people'] if p in IDX]
else:
    CORE = list(PEOPLE)
CORE_SET = set(CORE)

gkey = {g.get('label'): g.get('key') for g in cfg.get('groups', [])}
present = {m['g'] for m in allm}
group_keys = [g.get('key') for g in cfg.get('groups', []) if g.get('label') in present]
group_keys += sorted(present - set(gkey))  # all.json 里有、config 里没登记的群：用名字当 key
label_of = {k: l for l, k in gkey.items()}
show_cfg = pages(cfg).get('show_chat_groups') or []
QUOTE = {gkey.get(x, x) for x in show_cfg} & set(group_keys)  # show_chat_groups 写 key 或 label 都行

# 称呼 → 人（@ 与引用回复用）：显示名 + aliases 的键 + nicknames；作者本人 = config.me
names = {}
for p in PEOPLE:
    names[p] = p
for k, v in (cfg.get('aliases') or {}).items():
    if v in IDX:
        names[k] = v
for p, ns in (cfg.get('nicknames') or {}).items():
    for n in ns:
        if p in IDX:
            names[n] = p
name_keys = sorted(((k.lower(), v) for k, v in names.items() if len(k) >= (1 if EN else 2) and not k.isdigit()),
                   key=lambda kv: (-len(kv[0]), kv[0]))


def resolve(seg):
    """`@` 后面那一截 / 引用回复里的名字 → 成员显示名。按最长前缀匹配；英文名还要求词边界（Al 不匹配 Alex 以外的 also）。"""
    s = re.sub(r'^[^\w`]+', '', (seg or '').strip()).lower()
    for k, who in name_keys:
        if s.startswith(k) and (not EN or len(s) == len(k) or not s[len(k)].isalnum()):
            return who
    return None


EPOCH = datetime(1970, 1, 1)


def clean(t):
    """比较用的句子：去掉微信小表情码与空白（中文）；英文转小写、合并空白、去掉首尾标点。"""
    t = EMOJI_CODE.sub('', t or '')
    if EN:
        return re.sub(r'^[\s.,!~]+|[\s.,!~]+$', '', ' '.join(t.lower().split()))
    return re.sub(r'\s+', '', t)


def size(t):
    return len(t.split()) if EN else len(t)


msgs = []
for m in allm:
    c = m['c']
    k = kind(c)
    p = disp(m['s'])
    text = ''
    is_reply = reply_to(c) is not None
    if k == '文字':
        text = common.REPLY_RE.sub('', c).replace(' ⏎ ', '\n').strip()
    x = {'g': gkey.get(m['g'], m['g']), 'ts': (datetime.fromisoformat(m['t']) - EPOCH).total_seconds(), 'day': m['t'][:10],
         'hour': int(m['t'][11:13]), 'p': p, 'i': IDX.get(p), 'cat': CAT_OF.get(k, '其他'), 'text': text, 'reply': is_reply,
         'at': set(), 'quote': None, 'nt': m['g'] in NO_TIME}
    if text and '@' in text:
        for seg in text.split('@')[1:]:
            who = resolve(seg[:30])
            if who and who != p:
                x['at'].add(IDX[who])
    if is_reply:
        who = names.get(reply_to(c)) or resolve(reply_to(c))
        if who and who != p:
            x['quote'] = IDX[who]
    msgs.append(x)
msgs.sort(key=lambda x: x['ts'])

# 年份：第一年不足 3 个月时并进下一年（与 build_chronicle 一致）
years_raw = sorted({x['day'][:4] for x in msgs})
first_months = sorted({x['day'][:7] for x in msgs if x['day'][:4] == years_raw[0]})
MERGE = len(years_raw) > 1 and len(first_months) < 3
year_of = lambda d: years_raw[1] if MERGE and d[:4] == years_raw[0] else d[:4]
YEARS = sorted({year_of(x['day']) for x in msgs})

# ---------------- 安全过滤：展示的短句与词 ----------------
gate_rules = Rules(proj, cfg)
extra_words = set(cfg.get('sensitive_words') or []) | set(real_names(cfg))
for t in cfg.get('taboo_extra') or []:  # 禁区多是一句话，拆成 2–6 字的片段当词用（宁可多滤）
    for piece in re.split(r'[\s,，、。；;：:（）()「」“”"\'/]+|的|与|和|及|或|以及|包括|任何人', t):
        if 2 <= len(piece) <= (20 if EN else 6):
            extra_words.add(piece)
extra_words = sorted({w.lower() for w in extra_words if w}, key=len, reverse=True)


def unsafe(t):
    if SENS.search(t) and not SAFE_NUM.match(t):
        return True
    low = t.lower()
    if any(w in low for w in extra_words):
        return True
    return bool(scan_text(gate_rules, '', t, realname_block=True))  # 隐私闸门：重点与警告都不要（不上页面）


# ---------------- 按组合（群 × 年份）计算 ----------------
def streak(days):
    best, start, run, prev, run_start = 0, None, 0, None, None
    for d in sorted(days):
        cur = date.fromisoformat(d)
        run = run + 1 if prev and cur - prev == timedelta(days=1) else 1
        if run == 1:
            run_start = d
        if run > best:
            best, start = run, run_start
        prev = cur
    return [best, start]


def sparse(counter):
    return [[x, y, v] for (x, y), v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


def stream_stats(stream, s, timed=True):
    """同一个群里按时间先后才有意义的统计：接话、冷场开话题、会话段共现、回复时延（timed=False 时不算时延）。"""
    times = collections.defaultdict(list)
    for x in stream:
        if x['i'] is not None:
            times[x['i']].append(x['ts'])
    prev, seg = None, set()

    def close_seg():
        ids = sorted(seg)  # 集合排序后再数：不依赖 hash 顺序
        for i in ids:
            s['segs'][i] += 1
        for j, u in enumerate(ids):
            for v in ids[j + 1:]:
                s['pair'][(u, v)] += 1
    for x in stream:
        gap = x['ts'] - prev['ts'] if prev else None
        if prev and x['i'] is not None and prev['i'] is not None and prev['i'] != x['i'] and gap <= NEXT_GAP:
            s['next'][(prev['i'], x['i'])] += 1
        if prev and gap >= OPEN_GAP and x['i'] is not None:
            s['open'][x['i']] += 1
        if prev is None or gap > SESSION_GAP:
            close_seg()
            seg = set()
        if x['i'] is not None:
            seg.add(x['i'])
            for target in [] if not timed else sorted(x['at'] | ({x['quote']} if x['quote'] is not None else set())):
                ts = times[target]
                k = bisect.bisect_right(ts, x['ts'])
                if k < len(ts) and ts[k] - x['ts'] <= LAT_MAX:
                    s['lat'][target].append((ts[k] - x['ts']) / 60)
        prev = x
    close_seg()


def combo(sel):
    if not sel:
        return None
    s = {k: collections.defaultdict(list) if k == 'lat' else collections.Counter() for k in
         ['n', 'segs', 'pair', 'next', 'open', 'at', 'quote', 'atIn', 'atOut', 'quoteIn', 'lat']}
    days = collections.Counter(x['day'] for x in sel)
    day_p = collections.defaultdict(collections.Counter)
    pdays, pmonths = collections.defaultdict(set), collections.defaultdict(set)
    types = collections.defaultdict(collections.Counter)
    all_types = collections.Counter(x['cat'] for x in sel)
    hours = collections.defaultdict(lambda: [0] * 24)
    heat = [[0] * 24 for _ in range(7)]
    for x in sel:
        if not x['nt']:  # 没有真实时刻的群不进作息类统计
            heat[date.fromisoformat(x['day']).weekday()][x['hour']] += 1
        i = x['i']
        if i is None:
            continue
        s['n'][i] += 1
        day_p[x['day']][i] += 1
        pdays[i].add(x['day'])
        pmonths[i].add(x['day'][:7])
        types[i][x['cat']] += 1
        if not x['nt']:
            hours[i][x['hour']] += 1
        for t in x['at']:
            s['at'][(i, t)] += 1
            s['atOut'][i] += 1
            s['atIn'][t] += 1
        if x['quote'] is not None:
            s['quote'][(i, x['quote'])] += 1
            s['quoteIn'][x['quote']] += 1
    for g in group_keys:
        stream_stats([x for x in sel if x['g'] == g], s, timed=label_of.get(g, g) not in NO_TIME)
    king = collections.Counter()
    for c in day_p.values():
        top = max(c.values())
        for i, v in c.items():
            if v == top:
                king[i] += 1
    person = {}
    for i in sorted(s['n']):
        lat = s['lat'].get(i, [])
        h = hours[i]
        person[i] = {
            'n': s['n'][i], 't': [types[i][c] for c in CATS], 'h': h, 'peak': max(range(24), key=h.__getitem__) if any(h) else None,
            'king': king[i], 'streak': streak(pdays[i]), 'days': len(pdays[i]), 'months': len(pmonths[i]),
            'atOut': s['atOut'][i], 'atIn': s['atIn'][i], 'quoteIn': s['quoteIn'][i], 'open': s['open'][i],
            'med': round(statistics.median(lat), 1) if len(lat) >= LAT_MIN_N else None, 'medN': len(lat),
        }
    hot = []
    for d, n in sorted(days.items(), key=lambda kv: (-kv[1], kv[0]))[:10]:
        top = sorted(day_p[d].items(), key=lambda kv: (-kv[1], kv[0]))
        hot.append([d, n, top[0][0] if top else -1])
    # 小团体：会话段共现，用余弦（共现 / √(各自段数之积)）去掉“话多的人跟谁都共现”的偏差；每人留最强 3 条边
    score = {(u, v): n / math.sqrt(s['segs'][u] * s['segs'][v]) for (u, v), n in s['pair'].items() if n >= 5}
    rank = lambda e: (-score[e], e)
    keep = set()
    for i in s['segs']:
        keep.update(sorted((e for e in score if i in e), key=rank)[:3])
    first, last = min(days), max(days)
    return {
        'total': len(sel), 'members': len({x['p'] for x in sel}), 'first': first, 'last': last,
        'span': (date.fromisoformat(last) - date.fromisoformat(first)).days + 1, 'activeDays': len(days),
        'hot': hot, 'heat': heat, 'types': [all_types[c] for c in CATS], 'p': person,
        'at': sparse(s['at']), 'quote': sparse(s['quote']), 'next': sparse(s['next']),
        'graph': {'nodes': [[i, v] for i, v in sorted(s['segs'].items(), key=lambda kv: (-kv[1], kv[0]))],
                  'edges': [[u, v, s['pair'][(u, v)], round(score[(u, v)], 3)] for u, v in sorted(keep, key=rank)]},
    }


gsel = ['all'] + (group_keys if len(group_keys) > 1 else [])
combos = {}
for g in gsel:
    for y in ['all'] + YEARS:
        c = combo([x for x in msgs if (g == 'all' or x['g'] == g) and (y == 'all' or year_of(x['day']) == y)])
        if c:
            combos[f'{g}|{y}'] = c

# 每日发言趋势：从第一天起按天计数（前端再合成周 / 月）
start, end = date.fromisoformat(msgs[0]['day']), date.fromisoformat(msgs[-1]['day'])
daily = {g: [0] * ((end - start).days + 1) for g in gsel}
for x in msgs:
    k = (date.fromisoformat(x['day']) - start).days
    daily['all'][k] += 1
    if x['g'] in daily and x['g'] != 'all':
        daily[x['g']][k] += 1

# ---------------- 复读 ----------------
# 同一短句被 ≥repeat_min_people 个不同的成员在 repeat_window_min 分钟内接连发出；中间夹的图片/表情不打断，引用回复打断
repeat_events, phrase_ids, phrases = [], {}, []
win = SC['repeat_window_min'] * 60
for g in group_keys:
    stream = [x for x in msgs if x['g'] == g and x['cat'] in ('文字', '图片', '表情')]
    cur, run = None, []
    for x in stream + [None]:
        if x is not None and x['cat'] != '文字':
            continue
        key = clean(x['text']) if x and not x['reply'] else None
        if cur and x and key == cur and x['ts'] - run[0]['ts'] <= win:
            run.append(x)
            continue
        if cur:
            who = list(dict.fromkeys(r['i'] for r in run if r['i'] is not None))
            if len(who) >= SC['repeat_min_people']:
                pid = -1
                if (g in QUOTE and size(cur) <= SC['phrase_max'] and cur not in GENERIC and len(cur) >= 2
                        and not LAUGH.match(cur) and not unsafe(cur)):
                    if cur not in phrase_ids:
                        phrase_ids[cur] = len(phrases)
                        phrases.append(cur)
                    pid = phrase_ids[cur]
                repeat_events.append([run[0]['day'], g, pid, who[0], who[1:]])
        cur, run = (key, [x]) if x and key and size(key) <= REPEAT_KEY_MAX else (None, [])

# ---------------- 口头禅 / 笑法（短整句，≥catch_min_count 次、跨 ≥catch_min_months 个月） ----------------
# 不算：接龙行「1. 某某」、单字、纯称呼（叫人不是口头禅）——与 sharekit.catchphrases（卡片、年度报告）同一口径
NAME_SET = all_names(cfg, allm) | set(names)
said = collections.defaultdict(lambda: collections.defaultdict(list))
laughs = collections.defaultdict(collections.Counter)
for x in msgs:
    if x['i'] is None or not x['text'] or x['reply']:
        continue
    t = clean(x['text'])
    if not t or size(t) > SC['phrase_max']:
        continue
    if LAUGH.match(t):
        laughs[x['i']][t] += 1
    else:
        said[x['i']][t].append(x['day'][:7])
catch, laugh_out = {}, {}
for i in range(len(PEOPLE)):
    rows = [[t, len(ms)] for t, ms in said[i].items()
            if len(ms) >= SC['catch_min_count'] and len(set(ms)) >= SC['catch_min_months'] and len(t) >= 2
            and '@' not in t and not LIST_ITEM.match(t) and t not in NAME_SET and not QUESTION.search(t) and not unsafe(t)]
    catch[i] = sorted(rows, key=lambda r: (-r[1], r[0]))[:5]
    laugh_out[i] = [[t, n] for t, n in sorted(laughs[i].items(), key=lambda kv: (-kv[1], kv[0]))[:3] if n >= 3 and not unsafe(t)]

# ---------------- 词云 ----------------
if EN:
    def cut(t):
        return re.findall(r"[a-z][a-z']+", t.lower())
    tokenizer = 'words'
else:
    try:
        import jieba
        jieba.setLogLevel(60)
        cut, tokenizer = jieba.lcut, 'jieba'
    except ImportError:  # 退化：2–4 字 n-gram（会有半截词，参考 references/15）
        def cut(t):
            return [t[i:i + n] for n in (2, 3, 4) for i in range(len(t) - n + 1)]
        tokenizer = 'ngram'
name_words = {w.lower() for w in set(names) | set(PEOPLE) | {me_name} | set(real_names(cfg)) if len(w) >= 2}
STOP = STOP_EN if EN else STOP_ZH
words = collections.Counter()
for x in msgs:
    if not x['text']:
        continue
    t = re.sub(r'@\S+', '', EMOJI_CODE.sub('', x['text']))
    t = t if EN else re.sub(r'\s+', '', t)
    for w in set(cut(t)):
        lw = w.lower()
        if lw in STOP or LAUGH.match(w) or any(n in lw for n in name_words):
            continue
        if EN:
            if len(w) < 3:
                continue
        elif len(w) < 2 or not re.search(r'[一-鿿]', w) or re.search(r'[0-9a-zA-Z]', w):
            continue
        words[lw if EN else w] += 1
cloud = []
for w, n in sorted(words.items(), key=lambda kv: (-kv[1], kv[0])):
    if len(cloud) >= 100:
        break
    if n >= 2 and not unsafe(w):
        cloud.append([w, n])

# ---------------- 输出 ----------------
ps = pages(cfg, 'stats')
merge_note = {years_raw[1]: [years_raw[0], len(first_months)]} if MERGE else {}
hide = set(SC['hide'])
divers_n = min(SC['divers_n'], len(CORE) // 3)  # 最多点核心成员的三分之一：6 个人里点 3 个就成了半个群倒序
if SC['divers'] == 'off' or divers_n < 1:
    hide.add('divers')
out = {
    'lang': 'en' if EN else 'zh',
    'people': [{'n': p, 'core': p in CORE_SET} for p in PEOPLE],
    'cats': CATS, 'years': YEARS, 'merge': merge_note,
    'groups': [{'k': g, 'label': label_of.get(g, g), 'quote': g in QUOTE,
                'first': min(x['day'] for x in msgs if x['g'] == g), 'last': max(x['day'] for x in msgs if x['g'] == g)}
               for g in group_keys],
    'daily': {'start': start.isoformat(), **daily},
    'combos': combos,
    'repeat': {'events': repeat_events, 'phrases': phrases},
    'catch': catch, 'laugh': laugh_out, 'cloud': cloud, 'tokenizer': tokenizer,
    'cfg': {'night': SC['night'], 'early': SC['early'], 'boardMin': SC['board_min_msgs'], 'diversN': divers_n,
            'repeatMin': SC['repeat_min_people'], 'repeatWin': SC['repeat_window_min'], 'phraseMax': SC['phrase_max'],
            'catchMin': SC['catch_min_count'], 'catchMonths': SC['catch_min_months'], 'hide': sorted(hide),
            'coreAll': len(CORE) == len(PEOPLE)},
    'text': {k: ps[k] for k in ('note', 'core_label', 'other_label', 'divers_note') if ps.get(k)},
    'noTime': sorted(NO_TIME & present),
}
a.work.mkdir(parents=True, exist_ok=True)
stats_path = a.work / 'stats.json'
stats_path.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f'消息 {len(msgs)}，成员 {len(PEOPLE)}（核心 {len(CORE)}），组合 {len(combos)}，复读 {len(repeat_events)} 次'
      f'（可展示短句 {len(phrases)}），口头禅 {sum(map(len, catch.values()))}，词云 {len(cloud)} 词（{tokenizer}）'
      f' → {stats_path}（{stats_path.stat().st_size // 1024} KB）')
if not QUOTE and phrases == []:
    print('提示：config.pages.show_chat_groups 为空，复读句不展示、只算次数（要展示哪个群的短句，问过用户再加）')

# 隐私闸门：stats.json 里所有要上页面的文字 + config.pages.stats 文案
enforce(proj, cfg, 'stats')
if a.no_page:
    sys.exit(0)

# ---------------- 单文件页面 ----------------
OUT = proj / 'out'
tpl = (TEMPLATES / 'stats.html').read_text(encoding='utf-8')
js = (TEMPLATES / 'stats.js').read_text(encoding='utf-8')
name = ps.get('name') or ('Stats' if EN else '数据')
seal = ps.get('seal', '' if EN else '群志')
if EN:
    lede = ps.get('lede') or ('Every message counted, none of them read: who talks most, when the group is loudest, who answers whom.'
                              '<br>No chat history on this page — only counts, plus a few short phrases that passed the privacy filter.')
else:
    lede = ps.get('lede') or ('把群里的每一条消息数一遍：谁话最多、几点最热闹、谁最爱接谁的话。'
                              '<br>只数不读——这里没有聊天原文，只有几句过了隐私筛查的短句。')
data_json = json.dumps(out, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
page = fill(tpl, {
    'LANG': 'en' if EN else 'zh-CN',
    'TITLE': esc(ps.get('title') or f"{pages(cfg).get('name') or re.sub('大事记$', '', cfg.get('title') or '') or ('Group' if EN else '群聊')} · {name}"),
    'TABS': tabs_html(cfg, 'stats', OUT),
    'NAME': esc(name), 'SEAL': f'<i>{esc(seal)}</i>' if seal else '',
    'LEDE': lede, 'LOADING': 'Loading…' if EN else '正在载入数据…',
    'DATA': data_json, 'JS': js.replace('</script', '<\\/script'),
})
plain = re.sub(r'<[^>]+>', '', tpl) + lede + js + data_json + '0123456789'
brush = name + seal + ''.join(PEOPLE) + ('数据群志概览时间消息类型榜单复读口头禅与词云互动小团体数据卡水王每日打卡斗图夜猫子早鸟深海潜水员'
                                         if not EN else 'OverviewTimeMessagetypesLeaderboardsEchoesCatchphrasesInteractionsCirclesDatacards')
fonts = font_css(proj, cfg, {'Ink': plain, 'Hand': plain, 'Brush': brush})
page = page.replace('/*FONTS*/', fonts)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'stats.html').write_text(page, encoding='utf-8')
print(f'→ {OUT / "stats.html"}（{(OUT / "stats.html").stat().st_size // 1024} KB）')
