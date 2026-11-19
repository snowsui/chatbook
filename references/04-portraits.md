# ④ 人物志（非虚构人物小传）

目标：给要写的群友（config.people，可以只有一人）每人一篇非虚构小传（篇幅按发言量 1500–4000 字，见 prompts/08）。事都是真的、话都是原话、日期都对得上；本人读了会说“这就是我”，熟人读了会笑、会多懂 TA 一点。用群内称呼，不用化名。

**两份名单别混**：`config.people` 只是“要写的人”；统计、点名判断、横向对比用的是 `config.members`（全体成员）。只写一个人时也要把 members 写全（或留空让脚本按发言量推断），否则 metrics 只剩一列、turnmix 的“点名他人”会漏掉对其他群友的点名。

## 流程

1. **证据：00 统一阅读 + collect_evidence**：大事记的统一阅读（prompts/00）已经为 config.people 里的每个人逐段记了证据（每条带消息 id）；`python3 scripts/collect_evidence.py --project <dir>` 汇总成 work/people/<人>/evidence.md（换成稳定键 k、核对说话人与原话，对不上的进「待核对」）。不用再按人读第二遍全量（references/08-pipeline.md）。
2. **可选：专人深读**：发言极多、单靠分段证据撑不起一篇的人，写进 config.deep_read，再用 `person_chunks.py` 切块、prompts/07-evidence-reader.md 逐块读（`fill_prompt.py --prompt 07 --person <人>`，说明末尾写明块号）→ work/people/<人>/cards/。
3. **统计**：`python3 scripts/person_stats.py --project <dir>`、`metrics.py`、`turnmix.py`（同样 `--project <dir>`；给写作员做数据卡和“日常样子”）。person_stats 只算 people；metrics、turnmix 的列是全体 members。
4. **写作（并行，每人一个子任务，强模型）**：prompts/08-portrait-write.md（`fill_prompt.py --prompt 08 --person <人>`）。正文里每句引语带出处标注 `<!--k:…-->`，写作员交稿前自跑 `verify_citations.py --strict` 清零（报告 work/review/<人>-citations.md 就是引语出处表）。方法融合：太史公以事见人与互见法、McKee 压力下的选择、Forster 圆形人物（至少一处意外但可信的反差）、《世说新语》式品藻（8–16 字）、Talese 式具体时刻开场、汪曾祺白描与闲笔、按数据跨度写人物弧线（看不出变化就不硬写）、结尾“{{author_title}}曰”。作者本人那篇：结尾改为“众人曰”（群友对他的原话拼成）+ 一段克制的自况。
5. **总编终审**：prompts/09-portrait-editor.md——品藻与开头去撞车、跨篇事实一致、禁区通查、篇幅；只有一两篇时走模板里的「单篇模式」（篇内一致、题眼语境、先看 verify_citations 报告再抽查语境、对号入座）。
6. **用户拍板**：终审列出的“需要用户确认的点”集中给用户拍板。
7. **本人确认**（可选）：想让被写的人先看看时，build_review_pages → 一对一私发 → collect_reviews（references/09-privacy.md 第四节）。
8. **构建**：`python3 scripts/build_portraits.py --project <dir>` → out/people.html（自动过隐私闸门；标注不进页面）。

## 强烈建议：用 ⑥ 的核查结果回修

第一版小传和第一版人物模型用的是同一批证据卡，会带着同样的误读（说话人认错、语境读反、把玩笑当真心）。做完 ⑤⑥ 后用 prompts/10-portrait-factfix.md 回修，每篇再补一两笔日常样子；之后再派一次独立终审。真实项目里这一轮修正了约 140 处，其中包括一篇的“题眼”原话其实是替别人配的台词。
