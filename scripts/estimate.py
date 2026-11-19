"""成本估算：ingest（最好也 split）之后，按字数、人数、分段数估算各模块的 token 量 → 打印表格（并写 work/estimate.md）。

用法：
  python3 scripts/estimate.py --project <dir> [--tier lite|standard|deep] [--rounds 1] [--all-tiers] [--calibrate]

--tier 缺省取 config.tier（再缺省 standard）；--all-tiers 三档各出一张汇总；--rounds 人物模型「盲测+修订」轮数（pipeline 默认 1）；
--calibrate 额外打印校准场景（真实项目：约 600 万字、9 人、4 轮修订，旧流程读两遍）的估算，与实测 8.2 亿 token 对照。

模型（子任务是“边读边调工具”的代理循环：每一轮调用都把当前上下文整个再送一遍，绝大部分是缓存读）：
  一个子任务的输入 ≈ 轮数 × (基础上下文 B + 材料 M/2 + 中途产生的内容 G/2)；其中只有 B + M + G 是首次写入（不走缓存），其余是缓存读。
  逐行阅读：M = 分段 token，轮数 = ceil(行数/350) + 2；写作/建模/审稿：M = 证据/统计/模型等材料，轮数按任务类型给定。
  主控编排：每派一个子任务约 3 轮；主控上下文均值 = 4 万 + 每个已派任务 200（封顶 15 万）。
  返工系数 1.65：补派没读完的、机检退回、用户改需求重写（真实项目实测摊下来约这个量）。
  中文按 1 字 ≈ 1 token；输出含思考，按“正文 × 1.45”计。
系数用真实项目校准（见 references/08-pipeline.md「估算与校准」），误差按 ±50% 理解：只用来选档位和排预算，不是报价。
金额：cheap 按 Claude Sonnet、strong 按 Claude Opus 的官方 API 单价（PRICE，2026-11 的价格，以官方当前价格为准），
  首次写入按缓存写入价、其余按缓存读取价，再给 ±50% 区间；人民币按 USD_CNY 折算。用订阅额度跑的不按这个算。
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, body, is_text, load_all, sender_key  # noqa: E402
from pipeline import ALL, enabled, tier_of  # noqa: E402

B = 25_000           # 子任务基础上下文：系统提示 + 工具 + 填好的说明
ORCH_TURNS = 3       # 每派一个子任务主控要几轮（填说明、派发、核对回报）
REWORK = 1.65
THINK = 1.45
LINES_PER_READ = 350
CHUNK_CHARS = 50_000
EVID_PER_CHUNK = 8 * 50   # 统一阅读：每人每段约 8 条证据 × 50 token
CARD_RATIO = 0.035        # 旧流程 07 证据卡 ≈ 本人切块的 3.5%

# 写作类子任务：(轮数, 额外材料 token, 中途产生 G, 正文输出 token)。材料里的“证据”另按人加。
WRITE = {
    'baseline': (8, 35_000, 10_000, 12_000),
    'portraits': (30, 15_000, 40_000, 8_000),
    'personas': (40, 25_000, 60_000, 20_000),
    'review': (40, 25_000, 80_000, 10_000),
    'blind': (8, 30_000, 5_000, 6_000),
    'revise': (30, 45_000, 50_000, 20_000),
    'factfix': (25, 50_000, 40_000, 8_000),
}
NEEDS_EVID = {'portraits', 'personas'}
# 每百万 token 美元：(输入/缓存写入, 缓存读取, 输出)；cheap = Claude Sonnet 5.5，strong = Claude Opus 5.5（缓存写入按输入 ×1.25）
PRICE = {'cheap': (2.0 * 1.25, 0.20, 10.0), 'strong': (4.0 * 1.25, 0.20, 20.0)}
USD_CNY = 7.2


def orch_ctx(n_tasks):
    """主控平均上下文：随派过的任务数增长（回报、核对结果都留在主控里），封顶 15 万。"""
    return min(40_000 + 200 * n_tasks, 150_000)


def agent(turns, material, grow, out):
    """一个代理循环子任务 → (输入, 其中缓存读, 输出)。"""
    inp = turns * (B + material / 2 + grow / 2)
    fresh = B + material + grow
    return inp, max(inp - fresh, 0), out * THINK


def measure(a):
    """从项目里量出估算参数。"""
    cfg = a.cfg
    allm = load_all(a)
    chunks = []
    cdir = a.work / 'chunks'
    if cdir.exists() and any(cdir.glob('*.txt')):
        for f in cdir.glob('*.txt'):
            t = f.read_text(encoding='utf-8')
            chunks.append((len(t), t.count('\n') + 1))
        src = 'work/chunks'
    else:  # 没 split：按月粗估（每行 ≈ 内容 + 20 字前缀）
        bym = {}
        for m in allm:
            x = bym.setdefault(m['t'][:7], [0, 0])
            x[0] += len(m['c']) + 20
            x[1] += 1
        for c, n in bym.values():
            k = max(1, math.ceil(c / CHUNK_CHARS))
            chunks += [(c / k, n / k)] * k
        src = '按月粗估（还没 split）'
    months = {m['t'][:7] for m in allm}
    ppl = []
    for p in cfg.get('people') or []:
        s = sender_key(cfg, p)
        ppl.append((p, sum(len(body(m['c'])) + 40 for m in allm if m['s'] == s and is_text(m))))  # +40：紧邻上一句上下文
    return dict(chars=sum(len(m['c']) for m in allm), msgs=len(allm), chunks=chunks, months=len(months),
                multi=max(len(chunks) - len(months), 0), people=ppl, src=src,
                deep_read=[p for p in cfg.get('deep_read') or []])


def rows_for(par, stages, rounds, old_flow=False):
    """→ [(模块, 模型档, 任务数, 输入, 缓存读, 输出)]"""
    rows = []

    def add(name, tier, n, r):
        rows.append((name, tier, n, r[0], r[1], r[2]))

    def total(rs):
        return tuple(sum(x[i] for x in rs) for i in range(3))
    P = len(par['people'])
    unified = 'collect' in stages and not old_flow
    if 'read' in stages:
        rs = [agent(math.ceil(ln / LINES_PER_READ) + 2 + (1 if unified else 0), c, 0, c * (0.06 if unified else 0.03)) for c, ln in par['chunks']]
        add('read（统一阅读 00）' if unified else 'read（事件抽取 01）', 'cheap', len(rs), total(rs))
    n_evid = len(par['chunks']) * EVID_PER_CHUNK
    if old_flow and P:  # 旧流程：每人按人切块再读一遍（07）
        rs = []
        for _, pc in par['people']:
            k = max(1, math.ceil(pc / 160_000))
            rs += [agent(math.ceil(pc / k / 40 / LINES_PER_READ) + 2, pc / k, 0, 6_000)] * k
        add('evidence（旧流程 07 逐人再读）', 'cheap', len(rs), total(rs))
    elif 'deepread' in stages and par['deep_read']:
        rs = []
        for p, pc in par['people']:
            if p in par['deep_read']:
                k = max(1, math.ceil(pc / 160_000))
                rs += [agent(math.ceil(pc / k / 40 / LINES_PER_READ) + 2, pc / k, 0, 6_000)] * k
        add('deepread（专人深读 07）', 'cheap', len(rs), total(rs))
    if 'merge' in stages and par['multi']:
        add('merge（02）', 'cheap', par['multi'], total([agent(6, 8_000, 2_000, 3_000)] * par['multi']))
    for name in ('baseline', 'portraits', 'personas', 'review', 'blind', 'revise', 'factfix'):
        if name not in stages or not P:
            continue
        turns, mat, grow, out = WRITE[name]
        rs = []
        for _, pc in par['people']:
            ev = (pc * CARD_RATIO if old_flow else min(n_evid, pc * 0.15)) if name in NEEDS_EVID else 0
            rs.append(agent(turns, mat + ev, grow, out))
        times = rounds if name in ('blind', 'revise') else 1
        add(name + (f'（×{rounds} 轮）' if times > 1 else ''), 'cheap' if name in ('baseline', 'blind') else 'strong', P * times, total(rs * times))
    if 'editor' in stages and P:
        add('editor（09）', 'strong', 1, agent(20 + 5 * P, 6_000 * P, 60_000, 10_000))
    if 'overview' in stages and P:
        add('overview（16）', 'strong', 1, agent(40, 20_000 * P + 15_000, 60_000, 25_000))
    n_tasks = sum(r[2] for r in rows)
    inp = n_tasks * ORCH_TURNS * orch_ctx(n_tasks)
    add('主控编排', 'strong', n_tasks, (inp, inp - n_tasks * ORCH_TURNS * 5_000, n_tasks * 1_500 * THINK))
    return [(n, t, k, i * REWORK, c * REWORK, o * REWORK) for n, t, k, i, c, o in rows]


def fmt(x):
    return f'{x / 1e8:.2f} 亿' if x >= 1e8 else (f'{x / 1e4:.0f} 万' if x >= 1e4 else f'{x:.0f}')


def cost(rows):
    """→ 美元（点估计）。"""
    usd = 0.0
    for _, t, _, i, c, o in rows:
        w, r, out = PRICE[t]
        usd += ((i - c) * w + c * r + o * out) / 1e6
    return usd


def money(usd):
    lo, hi = usd * 0.5, usd * 1.5
    return f'约 ${lo:,.0f}–{hi:,.0f}（¥{lo * USD_CNY:,.0f}–{hi * USD_CNY:,.0f}）'


def table(rows):
    out = ['| 模块 | 模型 | 任务数 | 输入 | 其中缓存读 | 输出 |', '|---|---|---|---|---|---|']
    out += [f'| {n} | {t} | {k} | {fmt(i)} | {fmt(c)} | {fmt(o)} |' for n, t, k, i, c, o in rows]
    for tier in ('cheap', 'strong'):
        rs = [r for r in rows if r[1] == tier]
        if rs:
            out.append(f'| **{tier} 合计** | | {sum(r[2] for r in rs)} | {fmt(sum(r[3] for r in rs))} | {fmt(sum(r[4] for r in rs))} | {fmt(sum(r[5] for r in rs))} |')
    i, c, o = (sum(r[j] for r in rows) for j in (3, 4, 5))
    out.append(f'| **总计** | | {sum(r[2] for r in rows)} | {fmt(i)} | {fmt(c)}（{c / i:.0%}） | {fmt(o)} |' if i else '| 总计 | | 0 | 0 | 0 | 0 |')
    if i:
        out += ['', f'按 API 价格：{money(cost(rows))}（cheap=Sonnet、strong=Opus，缓存价，仅供参考，以官方当前价格为准）']
    return out


def calibration():
    """真实项目：约 600 万字（25 万条，8 年 96 个月）、9 人、4 轮修订；旧流程（01 抽事件 + 07 逐人再读）。"""
    n_chunks = 170
    par = dict(chunks=[(6_000_000 * 1.3 / n_chunks, 1_700)] * n_chunks, multi=n_chunks - 96,
               people=[(f'p{i}', 900_000) for i in range(9)], deep_read=[])
    stages = enabled({}, 'deep')
    return rows_for(par, stages, 4, old_flow=True), rows_for(par, stages, 4)


def extra(p):
    p.add_argument('--tier', choices=ALL, help='缺省取 config.tier')
    p.add_argument('--rounds', type=int, default=1, help='人物模型盲测+修订轮数，默认 1')
    p.add_argument('--all-tiers', action='store_true', help='三档各出一张')
    p.add_argument('--calibrate', action='store_true', help='再打印真实项目校准场景')


def main():
    a = args(__doc__, extra)
    par = measure(a)
    P = len(par['people'])
    head = [f'# 成本估算（{a.project.name}）', '',
            f'聊天 {par["msgs"]:,} 条、{par["chars"]:,} 字；{par["months"]} 个月、{len(par["chunks"])} 个分段（{par["src"]}）；'
            f'要写的人 {P} 位：' + '、'.join(f'{p}（本人切块约 {c / 1e4:.1f} 万字）' for p, c in par['people']), '']
    tiers = ALL if a.all_tiers else (tier_of(a.cfg, a.tier),)
    if not P:
        head += ['**注意**：config 里还没有核心人物（core / people），standard、deep 档里写人物志、人物模型的部分没算进去，'
                 '估算偏低。先跑 roster.py 选好核心人物再估。', '']
    head += ['数据页（build_stats.py）零 LLM 成本；最省的上手顺序：先出数据页 → lite 档出大事记 → 看效果再决定要不要 standard / deep。', '']
    out = head
    for t in tiers:
        out += [f'## 档位 {t}（盲测+修订 {a.rounds} 轮）' if t == 'deep' else f'## 档位 {t}', '']
        out += table(rows_for(par, enabled(a.cfg, t), a.rounds)) + ['']
    if a.calibrate:
        old, new = calibration()
        out += ['## 校准场景：真实项目（约 600 万字、9 人、deep、4 轮修订）', '',
                '实测：总计约 8.2 亿 token，其中约 92% 是缓存读，输出约 680 万。', '', '### 旧流程（01 抽事件 + 07 逐人再读一遍）', '']
        out += table(old) + ['', '### 新流程（00 统一阅读，一遍读完）', ''] + table(new) + ['']
    text = '\n'.join(out) + '\n'
    print(text)
    (a.work / 'estimate.md').write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
