# 数据与配置约定（所有脚本共用）

## 项目目录（用户的工作目录，不是 skill 目录）
```
<project>/
  chronicle.config.json     # 项目配置（见下）
  work/
    all.json                # 标准化后的全部消息
    senders.json            # ingest 的旁路文件：每条消息的发送者账号 / 原始昵称 / 被引用消息（roster 用）
    ingest.json             # ingest 的旁路文件：{"v": 1, "no_time": [没有真实时刻的群 label]}（build_stats 用）
    roster.json roster.md   # 人物名单（roster.py build；编号、合并、推荐等级、可能同一人的建议）
    state.json              # pipeline 进度（任务状态，跨会话可续；incremental 登记的任务也在这里）
    estimate.md             # 成本估算（estimate.py）
    prompts/                # 填好的子任务说明（fill_prompt --out）
    chunks/                 # 分段文本（增量尾部为 <月>_tail_p<i>.txt）
    cards/<分段>.json        # 统一阅读（prompts/00）的产物：事件 + 人物证据；<分段>-b.json 是补读剩余行的卡片
    part_events/ events/ stable/   # 抽取 → 合并 → 冻结（part_events/merged/ 为已并入的增量尾部）
    check.txt               # check_events 的机检输出（pipeline 判“未处理 0 条”）
    check_allow.json        # check_events --allow 标记的“已看过、合理”的警告：[{event: 第一条 ref 的稳定键, rule, note}]
    top10.auto.json         # build_chronicle 按热度自动挑的年度十大候选（每年前 20 件；人工挑好存成 top10.json）
    people/<人>/evidence.md # collect_evidence 汇总的证据（每条带稳定键 k）
    people/<人>/chunks/ cards/     # 逐人切块；cards/ 只在专人深读（config.deep_read，prompts/07）时有
    stats/ metrics.md turnmix.md turns/   # 统计
    stats.json              # 数据页统计（build_stats.py；格式见 references/15-stats-dashboard.md 第五节）
    stories/{in,profiles,notes}/ stories/names.md   # 小剧场素材与档案
    top10.json                # 可选：年度十大（手选）
    base/ holdout/ attr/ test/  # 验证
    review/                 # <人>-citations.md（引语出处表）、evidence-check.md、portraits-editor.md、<人>.md（模型审稿）
    review/in/              # 收回的本人确认码（<人>.txt / .json；本人确认是可选工具）
    review/replies.md review/replies/   # collect_reviews 的汇总与规范化结果（只供参考；构建时打一行汇总提醒）
    privacy/{blocked.txt,allowlist.json,last_scan.json}   # 已删除素材清单 / 标记已看过的命中 / 最近一次闸门结果
    scenes/                 # 群聊戏：beats-<seed>.md/.json、scene-<tag>.md、real-<tag>-<n>.md、blind/
    digest/                 # 月报/年报统计 <期>-stats.md（incremental.py --stats）
    incremental.json        # 增量更新的基线，按群记（每群 label / last / 各月 n·first·last·fp；incremental.py --commit）
    core.md                 # 大群核心人物排名（select_core.py）
  out/
    chronicle.html          # 大事记单文件版
    stories/  stories.html stories-txt/  # 小剧场（stories/CAST.md 为化名表）
    portraits/ people.html  # 人物志
    stats.html              # 数据页单文件版（数据内嵌）
    personas/               # 人物模型（本地私用）
    cards/                  # 分享卡片 <人>.html/.png、_group.html/.png
    wrapped-<年>.html        # 年度报告
    locked/                 # 口令加密单文件
    review/<人>.html         # 本人确认页（可选；含人物模型内容，适合一对一私发）
    digest/                 # 月报/年报正文
  site/                     # 可选：登录版网站（Cloudflare Worker）
```

## chronicle.config.json
```json
{
  "title": "某某群大事记",
  "me": "作者在聊天里的名字",
  "groups": [
    {"key": "A", "label": "主群", "file": "exports/main.json", "format": "json-array"},
    {"key": "B", "label": "家属群", "file": "exports/family.txt", "format": "txt"}
  ],
  "aliases": {"群昵称或旧名": "统一显示名"},
  "core": ["核心人物（roster.py apply --core 写入）"],
  "members": ["全体成员（统一显示名，含作者本人）"],
  "people": ["要写人物志/人物模型的人（统一显示名，可只填一人；不写 = core）"],
  "gender": {"统一显示名": "女|男"},
  "relations": ["A 与 B 是夫妻", "..."],
  "taboo_extra": ["本群特有、不能写的话题"],
  "fonts": {"ink": "path/to/serif.otf", "hand": "path/to/kai.ttf", "brush": "path/to/brush.ttf"}
}
```
- `core`：**核心人物**，用户圈定的权威名单（roster.py apply 写入）。`people` 不写时 = core；数据页的核心成员取 `stats.core` > `core` > `people`（≥3 人）> `members`。
- `members`：全体成员，用于统计、点名判断（turnmix）、横向对比（metrics）、事件 people 的机检（check_events）。roster.py apply 缺省写成 core + 推荐为“成员”的人 + 作者本人；手写项目不写时由 all.json 里发言量 ≥ 全部消息 1%（且 ≥10 条）的发言人推断，脚本会打印推断结果，确认后最好写进来。`core`、`people` 里的人自动并入 members。
- `people`：只决定“为谁切块/写统计/出题/写小传和模型”（person_chunks、person_stats、baseline_sample、holdout、fill_prompt --person）。只写一个人时 people 填一人即可，members 照样写全。

`file` 可以是字符串，也可以是同一个群多次导出的列表（时间重叠，ingest 按平台消息 ID、没有就按 时间+发送者+内容 去重合并；init_project.py 自动识别并写成列表）。
列表元素也可以写成 `{"file": "旧.txt", "format": "txt", "date": "2024-01-01"}`：同一个群的不同格式导出并在一起（这时按 分钟+内容 去重；`init_project.py --same B=A` 会这样写），或者单独给某份无时间 txt 指定日期。
`format` 取值：`json-array`、`chatlab`、`txt`、`csv`、`qq`、`telegram`，各是什么、怎么导出见 references/00-export-guide.md（格式表只在那里列一次），字段细节见 `scripts/ingest.py` 顶部说明，样例在 `assets/samples/`。
群上可选：`columns`（csv 列名映射）、`date`（无时间 txt 的日期）。

流程与隐私相关的键（都可选）：
| 键 | 取值 | 作用 |
|---|---|---|
| `tier` | `lite` / `standard`（缺省）/ `deep` | pipeline 启用哪些阶段（references/08-pipeline.md） |
| `deep_read` | `[显示名]` | 为这些人另做专人深读（prompts/07） |
| `lang` | `zh`（缺省）/ `en` | 模板语言与统计口径（references/13-english.md） |
| `scale` | `group`（缺省）/ `pair` / `large` | 规模规则，填进 01/00 的 `{{scale_rules}}`（references/12-scale-incremental.md） |
| `periods` | `[{"name","from","to"}]` | 长跨度分期（仅记录，目前没有脚本使用） |
| `public_detail` | `standard`（缺省）/ `full` | standard：公开页面不写具体金额、住址、证件、诊断细节、他人隐私，闸门对大事记、人物志、月报里带数字的金额和门牌住址重点提醒；full 由用户明确选择（references/09-privacy.md 第一节） |
| `sensitive_words` | `[词]` | 本群敏感词：公开页面里重点提醒；也注入抽取说明 |
| `real_names` | `[真名]` 或 `{显示名: 真名或[真名]}` | 小剧场里重点提醒、其他页面普通警告；也注入抽取说明 |
| `blocked_snippets` | `[片段]` | 已删除素材（与 work/privacy/blocked.txt 合并），公开页面里重点提醒 |
| `privacy` | `{"strict": true}` | 隐私闸门：默认只提醒、开 `strict` 才拦（重点命中时中止构建；references/09-privacy.md 第二节） |

`taboo_extra`（用户点名的禁区）与 `sensitive_words`、`real_names` **在任何模式下都生效**；`family_safe` 只管恋爱暧昧、工作挫折这类分寸项。

可选键：`family_safe`（true/false，事件抽取的隐私开关缺省值，见 prompts/01；fill_prompt 的 `--family-safe` 可覆盖）、`groups[].columns`（csv 列名映射）、`nicknames`（`{显示名: [外号]}`，turnmix 判断点名用）、`metric_words`（`{类别: 正则}`，覆盖 metrics 词表）、`holdout_sensitive`（`[词]`，覆盖盲测敏感词默认表）。
`aliases` 的键可以是昵称，也可以是平台账号（json-array 的 sender_id / QQ 号 / ChatLab platformId / Telegram from_id）；映射到 `me` 的值即视为作者本人。

脚本读 config 时会校验：不认识的键提示（附拼写相近的建议，如 `sensitive_word` → `sensitive_words`）；类型不对（比如列表写成了字符串）、`tier`/`lang`/`scale`/`public_detail` 取值不对、JSON 写错（报行列号）直接报错退出。以 `_` 开头的键当注释，不提示。

## work/all.json（标准化消息，按时间升序）
```json
[{"id": "A0", "k": "A:<稳定键>", "g": "主群", "t": "2019-01-01 12:00:00", "s": "张三", "c": "内容"}]
```
- `id`：群 key + 序号，仅本次运行内有效，给子任务引用。
- `k`：稳定键 = 群 key + `:` + 平台消息 ID（没有就用 `L<时间戳>_<同秒序号>`）；重新导出后不变，用于冻结。
  注意：txt / qq / 没有 id 列的 csv 只能用 `L<时间戳>_<同秒序号>`，重新导出时同一秒内的消息有增删，就会错位到邻居消息（见 references/01-ingest.md「增量更新」）。
- `s`：发言人，经过 `aliases` 归一；作者本人统一写 `me`。
- `c`：纯文本；换行替换为 ` ⏎ `；引用回复写成 `原文（回复 X: 前40字）`，X 经过 aliases 归一、作者本人写 config.me 的显示名（所有格式一致）；非文字写占位符 `[图片] [语音] [表情] [视频] [文章] 标题 [链接] … [小程序] …`，带配文的写 `[图片] 配文`；截断到 300 字；撤回提示等系统消息丢弃。
- all.json 的字段不变（脚本只认这六个键）。发送者的平台账号等放在旁路文件 `work/senders.json`：`{"v": 1, "rows": [[u, n, r], ...]}`，第 i 项对应 all.json 第 i 条——`u` 发送者账号（`<平台>:<账号>`，如 `qq:<QQ号>`、`tg:<from_id>`；txt/csv 为 null），`n` 导出里的原始昵称（未过 aliases），`r` 被引用消息的稳定键（有引用 ID 时，否则 null）。只有 roster.py 读它；旧项目没有这个文件时 roster 退化成只按名字汇总。
- “有文字”的口径（person_chunks / person_stats / metrics / quote_attr / baseline_sample / holdout）：去掉开头占位符和引用尾巴后还有文字就算，所以 `[图片] 配文`、`[链接] 标题` 算有文字；split_chunks 只去掉内容恰好是 `[图片]` 或 `[表情]` 的行。turnmix 判发言类型时例外，只把不以占位符开头的消息当文字（带配文的图片仍归“只发图”、带标题的链接仍归“转链接”）。

## 事件 JSON（events/ 与 stable/ 每月一个文件）
```json
{"month": "YYYY-MM", "month_summary": "≤30字",
 "events": [{"date": "YYYY-MM-DD", "title": "≤14字", "summary": "≤80字",
   "people": ["显示名"], "category": "人生节点|聚会出行|群内热议|名场面",
   "heat": 1, "refs": ["A123", "B45"], "groups": ["主群"]}]}
```
- `date` = refs 里最早一条消息的日期；`refs` 2–6 条、按时间排序、都在本月；`people` 用显示名（作者本人写 config.me，不写 `me`）。`scripts/check_events.py` 机检这些规则。
- 「同一件事」：同一场活动、或同一话题的连续讨论（断开不超过约 3 天）；隔几天/隔周重演的群梗各自成事件（见 prompts/01）。

stable/ 中 refs 已换成稳定键 `k`，事件按 date 稳定排序（修订清单的 `E:月份-序号` 就是 stable 里的下标，也是页面上的显示顺序）。

## 修订清单（apply_fixes.py 的输入）
```json
[{"key": "E:2020-05-3", "field": "summary", "old": "原文片段", "new": "新文", "why": "依据"},
 {"key": "M:2020-05", "field": "summary", "old": "...", "new": "..."},
 {"key": "E:2020-05-3", "field": "people", "add": "显示名"}]
```
`old` 必须在字段里恰好出现一次，否则整批不写。

## 页面相关配置（全部可选）
```json
{
  "author_title": "史官",
  "worker_name": "my-group-chronicle",
  "pages": {
    "name": "某某群",
    "show_chat_groups": [],
    "tabs": {"chronicle": "大事记", "stories": "小剧场", "portraits": "人物志"},
    "chronicle": {"seal": "大事记", "lede_tail": "...", "hidden_note": "※ 聊在别的群里，原文不公开", "footer": "..."},
    "stories": {"title": "...", "seal": "小剧场", "hero": "...", "genre": {"01": "武侠"}, "cast_hint": "...", "footer": "..."},
    "portraits": {"title": "...", "seal": "人物志", "hero": "...", "order": ["显示名"], "section": "列传", "footer": "..."},
    "stats": {"title": "...", "name": "数据", "seal": "群志", "lede": "...", "note": "...", "core_label": "...", "other_label": "..."}
  },
  "stats": {"core": [], "repeat_min_people": 2, "repeat_window_min": 10, "phrase_max": 8, "catch_min_count": 5, "catch_min_months": 3,
            "night": [0, 5], "early": [5, 9], "board_min_msgs": 200, "divers": "core", "divers_n": 3, "hide": []}
}
```
- `show_chat_groups`：哪些群的聊天原文可以出现在大事记里，也决定数据页的复读句取自哪些群。默认空 = 一条原文都不放。原文一旦放进去，能登录的人都看得到。
- `author_title`：人物志里「X曰」评语框和落款的称呼。
- `stats`：数据页的口径（复读人数与时间窗、短句长度、口头禅门槛、夜猫子/早鸟时段、潜水榜、要隐藏的视图）；`pages.tabs.stats` 是第四栏的名字（缺省「数据」，英文 Stats）。全部说明见 references/15-stats-dashboard.md 第四节。
- 详细说明见 assets/site/README.md 第 0 节。
- 分享形态：`pages.share = {"quote": {"显示名": "手选的一句原话"}, "seal": "印章字"}`（卡片；原话要能核对上本人的消息）；`pages.wrapped = {"end": "结尾页的一句话", "footer": "落款"}`（年度报告）。

## 统一阅读卡片 work/cards/<分段>.json 与引语标注
卡片 schema（`chunk lines read_to month month_summary events people{显示名: {glance, items[{kind,id,who,quote,tone,note,to?,also?,topic?}]}}`）与字段含义见 references/08-pipeline.md 第 1 节；`collect_evidence.py` 把它汇总成 events/ 与每人的 evidence.md。

小传、人物模型里的引语出处标注（Markdown 里看不见，构建时去掉，读人物志原文的脚本也会去掉）：
`「原话」<!--k:A:7000123-->` 本人说的；`<!--k:A:1,A:2-->` 跨连发几条；`<!--k:A:7000130@显示名-->` 别人说的；`<!--k:none-->` 引号里不是原话。
`verify_citations.py` 逐条核对，见 references/08-pipeline.md 第 2 节。

## 子任务说明的占位（scripts/fill_prompt.py 自动填）
`{{project}}` `{{skill}}` `{{me}}` `{{author_title}}` `{{gender_table}}` `{{relations}}` `{{taboo_extra}}` `{{family_safe}}` `{{groups}}` `{{members}}` `{{people}}` `{{public_detail}}` `{{sensitive_words}}` `{{real_names}}` `{{scale_rules}}` 从配置生成；`{{person}}` `{{chunk_files}}` `{{months}}` `{{story_id}}` `{{story_brief}}` `{{round}}` 来自命令行参数；其他占位（如 18/19 的 `tag`、`blind_id`、`ref_tag`）用 `--set a=1 b=2` 一次写多个——重复写 `--set` 时后一个覆盖前一个。表类占位都填成 Markdown 列表（`- 张三：女`、`- A 与 B 是夫妻`），空的写 `- （无）`。
`--prompt` 写编号或文件名前缀；不唯一时报错并列出候选（`17` → 写 `17-monthly` 或 `17b`）。`config.lang = "en"` 时优先用 prompts/en/ 下的同名模板。

## 命令行
所有脚本都用 `python3 scripts/<脚本>.py --project <项目目录> [参数]`；也可以把项目目录直接写成第一个参数（`build_chronicle.py <dir>`）；都不写就用当前目录。需要 Python 3.9 或更新。
