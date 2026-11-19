# ⑧ 核心流水线：统一阅读、引语出处、流程编排、档位与估算

真实项目里最贵的三笔返工：
1. **证据只抄原话不记出处** → 说话人认错一路传进小传和人物模型，返工上百处；
2. **大事记读一遍全量、人物志又按人读一遍全量** → 重复阅读占掉一大块成本；
3. **长项目跨会话，进度只在主控脑子里**、中间文件放临时目录 → 会话一断就丢。
流水线的顺序是：先日常（日常基线 / turn 统计 / 发言类型分布），再写作和建模。

## 1. 统一阅读（一次读，多处用）

`prompts/00-unified-reader.md`：每个分段（split_chunks 的产物）一个阅读员，逐行读完，同时产出 ① 本段事件（与 01 同格式同规则）② 本段里 `config.people` 每个人的证据条目。**每条证据都带消息 id**（分段文件每行开头那串）。

产出 `work/cards/<分段名>.json`：

```json
{"chunk": "2023-05_p1", "lines": 412, "read_to": 412,
 "month": "2023-05", "month_summary": "≤30字",
 "events": [ /* 与 01 完全相同：date title summary people category heat refs groups */ ],
 "people": {
  "显示名": {
   "glance": "这一段里 TA 的样子（≤40字）",
   "items": [
    {"kind": "名场面", "id": "A1236", "who": "显示名", "quote": "逐字原话（可用…删减）", "tone": "真心", "note": "说明"},
    {"kind": "对人方式", "id": "A1250", "who": "显示名", "to": "对象", "quote": "…", "tone": "玩笑", "note": "…"},
    {"kind": "他评", "id": "A1251", "who": "说这话的别人", "quote": "…", "tone": "玩笑", "note": "…"},
    {"kind": "反差", "id": "A1260", "who": "显示名", "also": ["A1201"], "quote": "…", "tone": "真心", "note": "表面…底下…"},
    {"kind": "禁区", "id": "A1270", "topic": "健康"}]}}}
```

| 字段 | 说明 |
|---|---|
| `lines` / `read_to` | 文件总行数 / 实际读到的行；`read_to < lines` 会被 pipeline 判为“没读完”，补派剩余行（见下） |
| `kind` | 名场面、语言指纹、对人方式、在乎与怕、反差、日常 → 这条消息**必须是本人说的**；他评 → **必须是别人说的**；禁区 → 只记 `topic`，不抄原话 |
| `who` | 阅读员认定的说话人（显示名；作者本人写 config.me）——脚本拿它和原文核对 |
| `quote` | 那条消息正文里的逐字原话，可用 … 删减；不含 `（回复 X: …）` 引用部分 |
| `tone` | 真心 / 玩笑 / 反讽 / 复读 / 拿不准 |
| `to` / `also` | 对人方式的对象 / 反差另一面的 id |

每人每段 3–12 条，其中“日常”至少 2 条（TA 在本段有发言时）——日常底色从第一步就留下来。

### collect_evidence.py

`python3 scripts/collect_evidence.py --project <dir>`：
- 事件 → `work/events/<月>.json`（该月只有一段）或 `work/part_events/<分段>.json`（多段，之后照旧走 02 合并、check_events、freeze）。目标文件比卡片新时不覆盖（合并/手改过的不会被冲掉），`--force-events` 强制。
- 证据 → `work/people/<人>/evidence.md`：id 换成稳定键 `k`，按时间排序，每条 `日期 时间｜种类｜k=…｜说话人：「原话」— 说明（语气，对谁）`；另列各段一句话、禁区主题、**待核对**。
- 逐条核对：id 存在且在该分段里；说话人与种类一致（别人的话记在本人名下 → 标出）；`who` 与原文一致；quote 在那条消息正文里；kind 合法。不合格的进「待核对」，不进正文。
- 汇总报告 `work/review/evidence-check.md`：没读完的分段、卡片问题、各人待核对条目。

**补派剩余行**：卡片 `read_to < lines` 时，`pipeline.py next` 给出的命令自动带 `--from-line <read_to+1>`；手动派写
`fill_prompt.py --project <dir> --prompt 00 --files <分段>.txt --from-line <N> --out …`。说明末尾会加一段“只读第 N 行起”，
产出写到 `work/cards/<分段>-b.json`（已有就 -c、-d…，不覆盖原卡片），卡片里多一个 `"from": N`。pipeline 判定“读完”时把原卡片和补读卡片接起来算，
collect_evidence 把两份的事件、证据一起汇总。

### 01、07 什么时候用

- lite 档只做大事记，read 用 01；standard/deep 用 00，一遍读完事件和人物证据（不用 01 读一遍 + 07 按人再读一遍）。
- **专人深读（可选）**：发言极多、单靠分段证据撑不起一篇的人，写进 `config.deep_read`，pipeline 会为 TA 加 deepread 任务（person_chunks 切块 + 07 逐块读），写作/建模时 evidence.md 与 cards/*.md 一起读。
- 08、11 的材料是 `evidence.md`（+ 若有的深读卡片）；`他评` 条目就是互见法的材料。
- 小剧场（03 人物档案）读 cards；有 evidence.md 时也可以直接读它。

## 2. 引语必须带出处（k 标注）

08 小传、11 人物模型、10 小传回修、14 模型修订：正文里每句引语后紧跟一个 HTML 注释，Markdown 渲染看不见，`pagekit.render_md` 构建时去掉：

| 写法 | 含义 |
|---|---|
| `「原话」<!--k:A:7000123-->` | 本人说的 |
| `「一句…又一句」<!--k:A:7000123,A:7000124-->` | 一句引语跨连发的几条 |
| `「别人的话」<!--k:A:7000130@老周-->` | 别人说的（@ 后写说话人显示名） |
| `「外号」<!--k:none-->` | 引号里不是原话（称呼、梗名、书名），声明免查 |

标注紧挨右引号（中间只允许空白）。小标题里的引语也要标。

`python3 scripts/verify_citations.py --project <dir> --person <人> --md <文件> [--strict]` → `work/review/<人>-citations.md`：
- error：k 不存在；说话人不符（标注说是 A、原文是 B——认错人就在这里抓）；原文不符（忽略空白/标点/⏎，按 … 切段，每段都要找得到）；标注落空。
- warning：未标注的引语（引号内 ≥4 字）。
- 报告同时是**引语出处表**（时间、说话人、k）和**引语语境**（出处前后各 3 条同群消息）；终审（09）看它查题眼、复读梗、替别人配的台词。
- `--strict`：有 error 或未标注就退出码 1；pipeline 用它判定小传/模型能否标 done。

没有标注的稿子可以用 quote_attr.py 按文本全库反查说话人。

## 3. 流程编排：scripts/pipeline.py

状态在 `work/state.json`（项目目录里，跨会话可续）：每个任务 `{stage, status: todo|doing|done|failed, attempts, out: [产出路径], note, manual, updated}`，以及各阶段汇总状态。

```
python3 scripts/pipeline.py --project <dir> status                 # 进度表 + 下一步建议
python3 scripts/pipeline.py --project <dir> next --limit 8 [--peek] # 下一批可派任务
python3 scripts/pipeline.py --project <dir> mark read:2023-01_p1 done|failed [--note …]
python3 scripts/pipeline.py --project <dir> reset portraits         # 任务或整个阶段回 todo
```

- `next` 只在依赖满足的阶段里挑 todo/failed 的任务；子任务数受 `--limit` 并发上限约束（进行中的也占名额），脚本任务另列、不占名额。每个任务给出：id、prompt、`fill_prompt.py` 的完整命令（`--out work/prompts/<任务>.md`；路径已加引号，可直接复制）、前置脚本（如 baseline_sample、holdout）、模型建议、产出路径。列出即记为 doing、尝试次数 +1（`--peek` 不记）；尝试满 3 次仍失败的列为“需人工”。
- 模型建议：**cheap** = 便宜模型（Claude Code 里派子任务时选 sonnet 或 haiku），**strong** = 强模型（选 opus）。
- **自动判定**：每次运行检查产出——存在且机检通过 → done；存在但不过 → failed（附原因，如“没读完 5/9 行”“引语机检：问题 1、未标注 1”）；done 的产出被删或上游更新（卡片比 evidence 新、事件比 check.txt 新、stable 比页面新…）→ 回 todo。手动 `mark done` 的不再自动改。
- `reset` 只清状态；产出还在且机检通过，下次又会自动 done——要重做先删/挪走产出。

**阶段与依赖（写死，按此顺序）**

| 阶段 | 单元 | 类型/模型 | 依赖 | 产出与机检 | 档位 |
|---|---|---|---|---|---|
| ingest | 一次 | 脚本 | — | work/all.json | 全部 |
| split | 一次 | 脚本 | ingest | work/chunks/ | 全部 |
| read | 分段 | 00（lite 用 01）/ cheap | split | cards/<段>.json（+ 补读卡片）：合法、读完 | 全部 |
| collect | 一次 | 脚本 collect_evidence | read | 每人 evidence.md，且比所有卡片新 | S/D |
| merge | 多段月份 | 02 / cheap | read、collect | events/<月>.json | 全部 |
| check | 一次 | 脚本 check_events --dir events > work/check.txt | merge | 0 警告 | 全部 |
| freeze | 一次 | 脚本 | check | 每个 events 月份都有 stable | 全部 |
| chronicle | 一次 | 脚本 build_chronicle | freeze | out/chronicle.html | 全部 |
| person-stats | 一次 | 脚本 person_chunks/person_stats/metrics/turnmix | ingest | metrics.md、turnmix.md、stats/<人>.md | S/D |
| baseline | 人 | baseline_sample + 13 / cheap | person-stats | base/<人>.md | S/D |
| deepread | 人×块 | 07 / cheap（仅 config.deep_read） | person-stats | people/<人>/cards/<块>.md | S/D |
| portraits | 人 | 08 / strong | collect、person-stats、baseline、deepread | out/portraits/<人>.md + 引语机检 | S/D |
| personas | 人 | 11 / strong | collect、person-stats、baseline、deepread | out/personas/<人>.md + 引语机检 | D |
| review | 人 | 12 / strong | personas | review/<人>.md | D |
| blind | 人 | holdout + 15 r1 / cheap | personas | test/<人>-r1.md | D |
| revise | 人 | 14 r1 / strong | review、blind | .v1 备份存在、正文比备份新、引语机检 | D |
| factfix | 人 | 10 / strong | revise、portraits | portraits.bak 存在、正文更新、引语机检 | D |
| overview | 一次 | 16 / strong | revise | out/personas/00-群像总览.md | D |
| editor | 一次 | 09 / strong | portraits、factfix | review/portraits-editor.md | S/D |
| build | 一次 | 脚本 build_portraits | editor、chronicle | out/people.html，比所有小传新 | S/D |

未启用的依赖忽略（例如 standard 没有 factfix，editor 只等 portraits）。person-stats/baseline 在 portraits/personas 之前——**先日常，后写作与建模**。第二轮及以后的修订/盲测不进默认流程，需要时手动派（`fill_prompt --prompt 14 --round 2`）。

**pipeline 不管的模块**：小剧场（③，references/03-stories.md）、数据页（⑮ build_stats.py）、本人确认（⑨ build_review_pages / collect_reviews）、分享卡片与年度报告（⑪）、登录版站点（⑦ package_site）、增量更新与月报年报（⑫，incremental.py 登记的尾部任务除外）、群聊戏（⑭）。这些按各自文档手动跑。

## 4. 档位与成本估算

`config.tier`：`lite` / `standard`（缺省）/ `deep`，pipeline 按它启用阶段（见上表）。

| 档位 | 做什么 | 适合 |
|---|---|---|
| lite | 大事记：01 便宜模型抽事件 → 合并 → 机检 → 冻结 → 页面 | 只要时间线；记录量大、预算紧 |
| standard | + 统一阅读（事件与人物证据一遍读完）、统计、日常基线、小传（带出处标注、机检）、总编终审 | 大事记 + 人物志，绝大多数项目 |
| deep | + 人物模型、独立审稿、盲测、一轮修订、小传回修、群像总览 | 要可推演的人物模型、和本人对照 |

`python3 scripts/estimate.py --project <dir> [--tier …] [--all-tiers] [--rounds N] [--calibrate]`（ingest 后即可跑，split 后更准）→ 表格（模块、cheap/strong、任务数、输入、其中缓存读、输出）+ cheap/strong 合计 + 按 API 价格折算的金额区间（cheap 按 Sonnet、strong 按 Opus，缓存价，±50%，价格写在脚本的 PRICE 里，以官方当前价格为准），写 `work/estimate.md`。还没选核心人物（core/people 为空）时会提示 standard/deep 的写作部分没算进去。开工前给用户看一眼再定档位。

### 估算模型

子任务是“边读边调工具”的代理循环：每轮调用都把当前上下文整个再送一遍。
- 一个子任务输入 ≈ 轮数 × (基础上下文 B 2.5 万 + 材料 M/2 + 中途产生 G/2)；首次写入（不走缓存）≈ B + M + G，其余是缓存读。
- 逐行阅读：M = 分段 token（中文 1 字 ≈ 1 token），轮数 = ceil(行数/350) + 2（统一阅读再 +1，输出量翻倍）。
- 写作/建模/审稿：轮数与材料按任务类型给定（小传 30 轮、模型 40、审稿 40、修订 30、回修 25、盲测 8、基线 8）；小传/模型的材料再加该人的证据量。
- 主控编排：每派一个子任务约 3 轮；主控上下文 = 4 万 + 每个已派任务 200（封顶 15 万）。
- 返工系数 1.65（补派、机检退回、需求改动重写）；输出含思考，按正文 × 1.45。

### 校准依据

真实项目：9 位核心群友、8 年、约 25 万条 / 600 万字，旧流程（01 抽事件 + 07 逐人再读一遍）+ 小传 + 人物模型 + 审稿 + 4 轮盲测与修订 + 回修 + 终审 + 群像总览，实测 **约 8.2 亿 token，其中约 92% 是缓存读，输出约 680 万**。

`estimate.py --calibrate` 用同样参数（170 个分段、每段约 1700 行，每人本人切块约 90 万字，4 轮）复算旧流程：**约 8.1 亿、缓存读 91%、输出约 690 万**，与实测吻合；同场景换成统一阅读约 6.8 亿（省掉第二遍逐人阅读和对应的主控编排）。

读这张表要知道：
- 大头不是“读原文”，而是写作/建模/审稿/修订子任务和主控在长上下文里的反复调用（缓存读）。省钱主要靠：少开轮次（deep 默认 1 轮修订）、让便宜模型做阅读与盲测、统一阅读不重复读。
- 系数是反推的，误差按 ±50% 理解，只用来选档位和排预算。脚本给的金额按缓存价算；用订阅额度跑的不按这个算。
