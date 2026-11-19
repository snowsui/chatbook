"""按「一次发言」（turn = 同群连续同一人的消息）统计说话方式 → work/turnmix.md + work/turns/<人>.md。

用法：
  python3 scripts/turnmix.py --project <dir> [--examples 8] [--seed 1]

每个 turn 归入一类（按此优先级判定，先中先得）：
  只发图/语音  全是 [图片][语音][视频]（可夹 [表情]）
  纯反应      只有表情，或文字只剩 哈哈/嗯/好的/确实/卧槽/666 这类附和
  转链接      含 [文章][链接][小程序][视频号][音乐][聊天记录][文件]，且文字 ≤15 字
  跳线        文字 ≥15 字、不是提问、与同群上文 4 条没有任何共同的二元字词（上文须在 2 小时内且有文字）
  点名他人    提到其他成员的称呼（config.members 的显示名 + aliases 反查 + config.nicknames）或含 @
  追问        含问号/疑问词
  讲自己      含「我」（不算「我们」）且 ≥6 字
  短评        文字 ≤15 字
  其他
另给条件分布：上一 turn 提到 TA / 上文 4 条有问号 / 一般接话（冷场 2 小时后开话题的 turn 不计入），
各条件下 纯反应 / 短内容(≤15字) / 长内容(>15字) 的比例（只发图/语音、只发链接的 turn 不计入）。
config.lang = "en" 时：附和词换英文（lol/haha/ok/same/true/fr…），跳线按「去掉停用词的 ≥3 字母单词」比较，
「讲自己」看 I/I'm/my 等，长度阈值按词数（15 字 → 6 词，6 字 → 3 词）。
列 = 全体成员（config.members，缺省按发言量推断）。这里的“文字”只算纯文字消息：`[图片] 配文`、`[链接] 标题` 按占位符类归类。
"""
import collections
import random
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (LINKS, ME, QUESTION, args, body, display, is_pure_text, kind, load_all, members,  # noqa: E402
                    names_of, safe, sender_key, turns)

CATS = ['只发图/语音', '纯反应', '转链接', '跳线', '点名他人', '追问', '讲自己', '短评', '其他']
CONDS = ['上一turn提到TA', '上文有问号', '一般接话']
NOISE = re.compile(r'\[[^\]]{1,6}\]|[哈嘿呵嗯哦噢喔啊哇呀嘻嘛额呃唉哎诶嗷吼hHaA6~～!！?？。.,，…\s👍😂🤣😄😁🙏👏]')
REACT = re.compile(r'(?:好的?|好滴|好吧|对的?|是的?|确实|可以|牛逼?|厉害|绝了|真的|卧槽|我靠|笑死|ok|OK|Ok|收到|同意|赞|\+1|'
                   r'太强了|真好|羡慕|恭喜|666+|yes|嗯嗯|哈+|呵+|嘿+|是啊|对啊|好啊|可以啊|行|没错|有道理|哇)+')
BIGRAM = re.compile(r'[一-鿿A-Za-z0-9]{2}')
GAP = 2 * 3600
REACT_EN = re.compile(r'(?:lo+l+|lmf?ao+|rofl|ha(?:ha)+h?|hehe+|ok(?:ay)?|kk?|yes+|yea+h?|yep|yup|true|same|nice|omg|wow|fr|bet|'
                      r'facts|agreed|exactly|right|congrats|ty|thanks|\+1|cool|damn|wild|nooo*|yas+)+', re.I)
NOISE_EN = re.compile(r'\[[^\]]{1,6}\]|\b(?:lo+l+|lmf?ao+|ha(?:ha)+h?|hehe+|xd)\b|[!?.,…\s~👍😂🤣😄😁🙏👏💀😭]', re.I)
STOP_EN = set('the and for you are but not this that with have just was its it\'s what all can get got like too out'
              ' now how why who when one about from they them his her she him our your yeah lol haha'.split())
SELF_EN = re.compile(r"\b(i|i'm|im|i've|i'll|i'd|me|my|mine|myself)\b", re.I)
QUESTION_EN = re.compile(r'\?|\b(what|why|how|when|where|who|which|anyone|anybody)\b', re.I)


def words_en(t):
    return {w for w in re.findall(r"[a-z']{3,}", t.lower()) if w not in STOP_EN}


def bigrams(t):
    t = re.sub(r'[^一-鿿A-Za-z0-9]', ' ', t)
    return {t[i:i + 2] for i in range(len(t) - 1) if BIGRAM.fullmatch(t[i:i + 2])}


def is_reaction(t):
    if not NOISE.sub('', t):
        return True
    core = re.sub(r'[\s!！~～。.,，…?？]', '', t)
    return len(core) <= 8 and bool(REACT.fullmatch(core))


def mentions(t, names):
    return any(n in t for n in names)


def main():
    a = args(__doc__, lambda p: (p.add_argument('--examples', type=int, default=8, help='每类示例条数'),
                                 p.add_argument('--seed', type=int, default=1)))
    cfg = a.cfg
    en = cfg.get('lang') == 'en'
    if en:  # 换成英文口径：长度按词数，跳线按单词重合，附和词与“讲自己”用英文
        global bigrams, is_reaction, QUESTION
        bigrams, QUESTION = words_en, QUESTION_EN
        is_reaction = lambda t: (not NOISE_EN.sub('', t)) or (len(t.split()) <= 4 and bool(  # noqa: E731
            REACT_EN.fullmatch(re.sub(r'[\s!~.,…?]', '', t))))
    size = (lambda t: len(t.split())) if en else (lambda t: len(t.replace('\n', '')))
    short, self_min = (6, 3) if en else (15, 6)
    self_re = SELF_EN if en else re.compile(r'我(?!们)')
    rnd = random.Random(a.seed)
    allm = load_all(a)
    ts = [datetime.strptime(m['t'], '%Y-%m-%d %H:%M:%S') for m in allm]
    names = names_of(cfg, allm)
    prev_idx = []  # 同群上一条
    last = {}
    for i, m in enumerate(allm):
        prev_idx.append(last.get(m['g']))
        last[m['g']] = i

    def ctx(i, n):
        out = []
        j = prev_idx[i]
        while j is not None and len(out) < n:
            out.append(j)
            j = prev_idx[j]
        return out[::-1]

    def nm(s):
        return names.get(s) or ([s] if s != ME else [cfg.get('me', ME)])

    tl = turns(allm)
    cat_n = collections.defaultdict(collections.Counter)
    single = collections.Counter()
    cond_n = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    examples = collections.defaultdict(lambda: collections.defaultdict(list))
    prev_turn = {}
    for g, s, idx in tl:
        msgs = [allm[i] for i in idx]
        ks = [kind(m['c']) for m in msgs]
        text = '\n'.join(body(m['c']) for m in msgs if is_pure_text(m))
        tlen = size(text)
        before = ctx(idx[0], 4)
        fresh = not before or (ts[idx[0]] - ts[before[-1]]).total_seconds() > GAP
        others = [n for x, ns in names.items() if x != s for n in ns]
        if not text and all(k in ('图片', '语音', '视频', '表情') for k in ks) and any(k != '表情' for k in ks):
            c = '只发图/语音'
        elif (not text and all(k == '表情' for k in ks)) or (text and is_reaction(text) and all(k in ('文字', '表情') for k in ks)):
            c = '纯反应'
        elif any(k in LINKS for k in ks) and tlen <= short:
            c = '转链接'
        elif tlen >= short and not QUESTION.search(text) and not fresh and (cb := set().union(*(bigrams(body(allm[j]['c'])) for j in before if is_pure_text(allm[j])))) and not (bigrams(text) & cb):
            c = '跳线'
        elif text and ('@' in text or mentions(text, others)):
            c = '点名他人'
        elif text and QUESTION.search(text):
            c = '追问'
        elif self_re.search(text) and tlen >= self_min:
            c = '讲自己'
        elif text and tlen <= short:
            c = '短评'
        else:
            c = '其他'
        cat_n[s][c] += 1
        single[s] += len(idx) == 1
        ex = examples[s][c]
        if len(ex) < 200:  # 蓄水池抽样，最后再从中抽示例
            ex.append(idx)
        elif (j := rnd.randrange(cat_n[s][c])) < 200:
            ex[j] = idx
        pt = prev_turn.get(g)
        if not fresh and c not in ('只发图/语音', '转链接'):
            ptext = ' '.join(body(allm[i]['c']) for i in pt[2]) if pt else ''
            if pt and mentions(ptext, nm(s)):
                cond = CONDS[0]
            elif any(re.search(r'[?？]', allm[j]['c']) for j in before):
                cond = CONDS[1]
            else:
                cond = CONDS[2]
            bucket = '纯反应' if c == '纯反应' else ('短内容' if tlen <= short else '长内容')
            cond_n[s][cond][bucket] += 1
        prev_turn[g] = (g, s, idx)

    def pct(x, n):
        return f'{100 * x / n:.1f}%' if n else '-'

    cols = [(p, sender_key(cfg, p)) for p in members(cfg, allm)]
    tot_cat = collections.Counter()
    for s in cat_n:
        tot_cat.update(cat_n[s])
    tot_single = sum(single.values())
    lines = ['# 发言方式（按 turn）', '', 'turn = 同群连续同一人的消息。分类优先级与定义见 scripts/turnmix.py 顶部说明。', '',
             '| 指标 | ' + ' | '.join(p for p, _ in cols) + ' | 全群 |', '|' + '---|' * (len(cols) + 2)]
    nt = {s: sum(cat_n[s].values()) for _, s in cols}
    allt = sum(tot_cat.values())
    lines.append('| turn 数 | ' + ' | '.join(str(nt[s]) for _, s in cols) + f' | {allt} |')
    lines.append('| 单条 turn 占比 | ' + ' | '.join(pct(single[s], nt[s]) for _, s in cols) + f' | {pct(tot_single, allt)} |')
    for c in CATS:
        lines.append(f'| {c} | ' + ' | '.join(pct(cat_n[s][c], nt[s]) for _, s in cols) + f' | {pct(tot_cat[c], allt)} |')
    lines += ['', '## 条件分布（纯反应 / 短内容 / 长内容，括号内为样本数）', '',
              '| 人 | ' + ' | '.join(CONDS) + ' |', '|' + '---|' * (len(CONDS) + 1)]

    def cond_cells(s):
        cells = []
        for cd in CONDS:
            x = cond_n[s][cd]
            n = sum(x.values())
            cells.append(f'{pct(x["纯反应"], n)} / {pct(x["短内容"], n)} / {pct(x["长内容"], n)} ({n})')
        return cells

    for p, s in cols:
        lines.append(f'| {p} | ' + ' | '.join(cond_cells(s)) + ' |')
    (a.work / 'turnmix.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    tdir = a.work / 'turns'
    tdir.mkdir(parents=True, exist_ok=True)
    for p, s in cols:
        out = [f'# {p} 的发言方式（{nt[s]} 个 turn，单条占比 {pct(single[s], nt[s])}）', '',
               '| 类别 | 占比 | 数量 |', '|---|---|---|']
        out += [f'| {c} | {pct(cat_n[s][c], nt[s])} | {cat_n[s][c]} |' for c in CATS]
        out += ['', '## 条件分布（纯反应 / 短内容 / 长内容）', ''] + [f'- {cd}：{v}' for cd, v in zip(CONDS, cond_cells(s))]
        for c in CATS:
            pool = examples[s][c]
            if not pool:
                continue
            out += ['', f'## {c} 示例']
            for idx in sorted(rnd.sample(pool, min(a.examples, len(pool)))):
                m0 = allm[idx[0]]
                out.append(f'\n{m0["t"][:16]} ‹{m0["g"]}›')
                out += [f'    {display(cfg, allm[j]["s"])}: {allm[j]["c"][:80]}' for j in ctx(idx[0], 2)]
                out += [f'  ► {allm[i]["c"]}' for i in idx]
        (tdir / f'{safe(p)}.md').write_text('\n'.join(out) + '\n', encoding='utf-8')
    print(f'{len(tl)} 个 turn → {a.work / "turnmix.md"}，逐人示例 → {tdir}')


if __name__ == '__main__':
    main()
