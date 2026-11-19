# ② 大事记

目标：按月的事件编年史，每个事件有日期、标题、摘要、人物、类别、热度和 2–6 条原文引用；做成单文件网页，可选再做成登录版网站（⑦）。

## 流程

1. **分段**：`python3 scripts/split_chunks.py --project <dir> [--max-chars 50000]` → work/chunks/。每段文件头写月份、第 i/n 段、本月条数（去掉纯图片/表情前后）、本段条数与文件总行数、本月最热的几天。
2. **阅读（并行）**：默认用 prompts/00-unified-reader.md 统一阅读——一遍读完，同时产出事件和人物证据，写 `work/cards/<分段>.json`，再跑 `collect_evidence.py` 导出事件（单段月份 → events/，多段 → part_events/）。只做大事记（lite 档）时可以用 prompts/01-extract-events.md 只抽事件（`python3 scripts/fill_prompt.py --project <dir> --prompt 01 --files <分段文件...> [--family-safe on]`）。`pipeline.py next` 会按档位给出对应命令（references/08-pipeline.md）。
   - 用 01 时，子任务回报 `文件名: N 条（共 M 行，已读完）`；M 和分段文件的总行数对不上、或写了“读到第 X 行”，就补派一个只读剩余行的子任务。用 00 统一阅读时不看回报，按卡片里的 `read_to` 与 `lines` 判断（pipeline 自动判，没读完时 `next` 给出 `--from-line` 补读命令）。
   - 「同一件事」的界定写在 prompts/01：同一场活动/同一话题的连续讨论算一件；隔几天/隔周重演的群梗各自成事件，summary 里写“又一次”。
   - 硬性要求逐行读完；不设数量上限；“多人参与 / 和群里人有关 / 值得纪念”都收。
   - **硬约束，任何模式都生效**：用户点名的禁区（config.taboo_extra）、本群敏感词（sensitive_words）、真名（real_names）一律不写。
   - **公开细节档位** `config.public_detail`：缺省 standard——事件可以收，但不写具体金额（“28k”“3 万”）、住址、证件账号、健康诊断细节、他人隐私，写成概括（“拿到了 offer”“去看了医生”）；闸门对大事记里带数字的金额会重点提醒。用户明确选了 full 才照实记录（真实项目里有用户这样选过，由用户显式选择）。
   - `{{family_safe}}`（只管分寸项）：成品会给家属看时打开，额外不收恋爱暧昧、相亲前任、工作挫折等（官宣的婚讯例外）。
   - 规模不是默认小群时（两人私聊、大群），`config.scale` 会往说明里注入对应的收录门槛（references/12-scale-incremental.md）。
   - 01 的产物：只有 1 段的月份直接写 work/events/；多段的写 work/part_events/。
3. **合并（并行）**：多段的月份用 prompts/02-merge-month.md 合并（`fill_prompt.py --prompt 02 --months <月份...>`），只去重、不删减。
4. **机检**：`python3 scripts/check_events.py --project <dir>` → 逐条警告 + 汇总：refs 2–6 条且都存在、在本月、按时间排序；date 等于最早一条 ref 的日期；title ≤14 / summary ≤80 / month_summary ≤30 字；category、heat 合法；people 都在 members/people/aliases 里（作者写 config.me）；refs 跨度 >3 天（多半是把重演的梗合成了一件）；代词与 config.gender 不符（一句里点到的人都是男却写了“她”，或反之；启发式，句里有异性亲属/伴侣称呼时不报；家属写进 config.gender 也参与判断）。
   - 子任务交稿前用同一个脚本自检：fill_prompt 填出来的说明里有完整命令（绝对路径，`--only` 只查分给它的分段/月份）。
   - **过关标准 = 没有未处理的警告**（pipeline 的 check 阶段同一口径）。还没冻结时直接改 `work/events/<月>.json`（或退回抽取/合并子任务）；冻结后才用 apply_fixes 修订清单。
   - 看过、确实合理的警告（例如“一面被问闭包 → 五天后二面又被问”，两头各只有一条消息，拆开反而说不清）不用硬拆：`check_events.py --project <dir> --allow <键> --rule 跨度 --note "理由"` 标记保留（键是警告里的“键 X”，规则写警告种类里的几个字；记在 work/check_allow.json，冻结前后都认）。refs 不存在/跨月、缺字段这类会让冻结或页面出错的不能标。
5. **冻结**：`python3 scripts/freeze.py --project <dir>` → work/stable/（refs 换成稳定键；事件按 date 稳定排序，所以 stable 里的下标 = 页面顺序 = 修订清单 `E:月份-序号`）。之后 stable/ 是唯一数据源。
6. **让用户过一遍**：给用户看人物列表（谁出现在多少事件里、外号、你推断的性别/关系），请他纠正。这一步通常能发现认错的人、反串称呼、缺失的家属。
7. **修订**：所有改动写成修订清单 JSON，用 `python3 scripts/apply_fixes.py --project <dir> fixes.json` 应用（old 必须唯一命中，否则整批不写）。大批量修订（如全站性别修正）：先 grep 出候选文案分批给子任务审，子任务回修订清单，主控统一应用。
8. **构建**：`python3 scripts/build_chronicle.py --project <dir>` → out/chronicle.html（字体子集内嵌，可离线打开；没配 fonts 时用系统字体并打印提示）。构建前自动过隐私闸门（references/09-privacy.md），列出疑似隐私问题供用户过目，页面照常生成；同时再跑一遍代词与性别的机检并打印提醒；要改的走 apply_fixes 后重跑。
   - **事件多时页面怎么读**：抽取不设上限、合并只去重（lessons 第 1 条），两年下来几百件是常态（试跑：24 个月 579 件）。删减不在数据上做，放在页面上：每年开头有「年度十大」（lite 档也有），每个月默认只摊开热度 2–3 的事，热度 1 的日常收进「展开本月 N 件日常」（本月热度 2 以上不足 2 件时先露两件日常）；按类别、按人筛选时不折叠。
   - **年度十大**：没有 work/top10.json 时按热度、引用条数自动挑，并把每年前 20 件候选写到 work/top10.auto.json（同 top10.json 的格式）。主控可以从候选里挑 10 件、改写入选理由，存成 work/top10.json 再构建；用户想自己定也是改这个文件。

## 可选增强（真实项目里用户要求过的）

- 年度十大（精挑版）：每年交给一个子任务从当年事件（或 work/top10.auto.json 的候选）里挑 10 件并写入选理由，主控人工核对；结果写 work/top10.json，单文件版和网站版都会显示。
- 群友榜：话痨（发言条数）、上镜（出现在事件里的次数）、夜猫子（凌晨发言占比）——只用计数，不展示内容。
- 事件搜索：只搜事件，不搜全部聊天（把全部聊天下发到浏览器有隐私风险，用户否掉过）。
- 吸顶时间跳转：年 × 月面板，跳到某月后可以继续往下翻。

## 质量检查

- 随机抽 3 个月，主控对照原文看有没有明显漏掉的热闹事件。
- 检查 people 字段：家属、改名的人有没有归一；作者本人写成 config.me。
- 禁区通查（lessons.md 第 7 条）。
