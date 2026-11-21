# chatbook · 群聊年鉴

一个 skill（标准 SKILL.md 格式，放进支持 skill 的 AI 编程工具即可使用）：把一个老朋友群多年的聊天记录，做成群友会认真看的东西——

- **大事记**：按月的事件编年史，带原文引用、搜索、年度十大、群友榜；单文件网页或登录版网站。
- **小剧场**：以群友为原型、用化名写的多体裁同人短篇（武侠、宫廷、推理、科幻、童话……）。
- **人物志**：逐行读完全部聊天记录后写成的非虚构人物小传（太史公式“以事见人”，每句话可追溯原文）。
- **人物模型**：可推演的人物性格模型（日常基线、发言类型分布、声音模型、关系网、情境推演），附独立审稿与盲测验证——用来和本人对照，或作为后续创作的人物设定。
- **数据页**：只数不读的统计看板——话痨/打卡/斗图/夜猫子榜、星期×小时热力图、复读、口头禅与词云、@/接话/引用矩阵、小团体关系图、每人数据卡（零 LLM 成本）。
- **分享**：每人一张竖版卡片、年度报告翻页（放到免费静态托管时可加访问口令）；月报/年报；按人物模型写群聊片段并和真实片段盲测。
- **流程**：统一阅读（一遍读完，事件与人物证据带消息 id）、pipeline 进度编排（跨会话可续）、lite/standard/deep 三档与成本估算、增量更新、两人私聊/大群适配；英文群为实验性支持（只承诺事件抽取、统计、数据页；建议 lite 档，standard/deep 需人工把关）。
- **隐私**：构建时的隐私扫描（已删除素材、敏感词、个人信息、具体金额与住址、人物模型隔离；默认只提醒、开 `privacy.strict` 才拦，见 references/09-privacy.md）、可选的一对一本人确认页。skill 只负责生成，是否发布、发给谁由创作者决定。

流程来自一个真实项目（9 位核心群友、8 年、约 25 万条消息），踩过的坑都写在 `references/lessons.md`。

> 成品截图：暂未附。想先看样子，把 `assets/samples/` 复制到一个空目录，跑 `ingest.py --project <那个目录>` 和 `build_stats.py --project <那个目录>`，打开里面的 `out/stats.html`。

## English

An agent skill (standard SKILL.md format) that turns years of group-chat exports (QQ, Telegram, ChatLab, a generic JSON array, CSV, or hand-copied text) into a "yearbook" for the people in the chat: a month-by-month event timeline website, non-fiction profiles where every quote is traceable to a message, optional fan fiction and personality models, and a zero-LLM-cost stats dashboard. It ships with a privacy scan that lists likely leaks at build time (warn-only by default, with an optional strict mode that blocks the build) and optional per-person review pages; whether and where to publish is up to the creator. Prompts and docs are written in Chinese; English chats are supported experimentally (event extraction, stats and the dashboard); use the lite tier for them, since the unified reader (00) used by standard/deep has no English version and those tiers need manual review. Triggers: "group chat yearbook", "turn our chat export into a website", "chat history timeline".

## 安装

需要 Python 3.9 或更新。

```bash
git clone https://github.com/snowsui/chatbook.git   # 放进你所用 AI 工具的 skills 目录
pip install fonttools brotli        # 可选：字体子集嵌入
pip install cryptography            # 可选：给免费静态托管的公开链接加访问口令（build_locked.py）
pip install playwright && python3 -m playwright install chromium   # 可选：分享卡片 PNG
pip install jieba                   # 可选：数据页中文词云分词（没装时退化成 2–4 字 n-gram，词云里会有半截词）
# 可选：登录版网站需要 Node.js 与 Cloudflare 账号（npx wrangler）
```

字体不随仓库分发：页面用的三种字体各自是 SIL Open Font License（OFL）开源字体，下载地址和配置见 `assets/fonts/README.md`。不配置也能用，会退回系统字体。

## 用法

在你的 AI 工具里说，例如：

> 我有几个群的聊天导出（~/exports/ 里，有 json 也有 txt），想做一个群大事记网站，再给几个老朋友写人物小传。

> 把我和室友群这四年的聊天记录做成一个年鉴，先看看要花多少钱。

> 这是我们宿舍群的 QQ 导出，帮我出一个数据页，看看谁是话痨、谁是夜猫子。

AI 会先导入（自动识别格式和编码、把同一个群的几次导出合并）、列出跨群合并好的人物编号表让你一句话圈定核心人物，再给你看三档的成本估算，和你确认：要做哪些模块、**性别与关系**、额外禁区与敏感词、要不要打开隐私拦截、哪些群的原文可以公开、网站叫什么，然后写 `chronicle.config.json` 开工。

### 支持的输入

本 skill 只负责“拿到导出文件之后”的部分，不负责获取聊天记录；请使用平台官方导出功能，或自行选择工具导出为支持的格式，并确保只处理自己有权处理的记录。支持的格式（通用 JSON 数组、ChatLab、Telegram、QQ 消息管理器、txt、csv）、各平台怎么导出、手动整理的 txt 会丢什么，见 `references/00-export-guide.md`。

一次可以给多个文件或一个文件夹：几个群、同一个群的多次导出（时间重叠会去重）、混合格式都行，`init_project.py` 一次读入；读不了的文件不影响其他文件，最后会列出办法。

## 要花多少

数据页零 LLM 成本；其余按读的字数、要写的人数和档位估。下表是 `scripts/estimate.py` 的估算（子任务 cheap 按 Claude Sonnet、strong 按 Claude Opus 的 API 单价，用别家模型按各自单价，按缓存价算，±50%，仅供参考，价格以官方当前价格为准；用订阅额度跑的不按这个算）：

| 规模 | lite（只做大事记） | standard（+ 人物志） | deep（+ 人物模型与验证） |
|---|---|---|---|
| 两人私聊 1 年，约 2 万条 | 约 1200 万 token，$5–16（¥40–110） | 约 2400 万，$9–28（¥70–200） | 约 6600 万，$23–68（¥160–490） |
| 小群 3 年，约 5 万条，写 5 人 | 约 2600 万，$12–35（¥80–250） | 约 5500 万，$21–64（¥150–460） | 约 1.6 亿，$53–158（¥380–1100） |
| 大群 8 年，约 25 万条，写 9 人 | 约 2.4 亿，$84–253（¥610–1800） | 约 3.2 亿，$108–323（¥780–2300） | 约 5.4 亿，$169–507（¥1200–3700） |

绝大部分 token 是缓存读。导入后跑 `estimate.py --project <dir> --all-tiers` 可以按你的实际数据估一遍（还没选核心人物时写作部分不计，会提示）。

**最短上手路径**（先花最少的钱看到东西，再决定要不要往下做）：

1. 导入：`python3 scripts/init_project.py --project <项目目录> <导出文件或目录>`
2. 数据页（零 LLM 成本）：`python3 scripts/build_stats.py --project <项目目录>` → `out/stats.html`
3. lite 档大事记：config 里写 `"tier": "lite"`，让 AI 按 pipeline 跑 → `out/chronicle.html`
4. 看过再决定要不要 standard（人物志）/ deep（人物模型）。

## 目录

```
SKILL.md          主流程与模块选择
CONTRACT.md       数据格式、目录、配置约定
references/       00–15 各模块方法文档 + lessons.md（踩坑总结）
                  00 导出指南 01 导入 02 大事记 03 小剧场 04 人物志 05 人物模型 06 验证 07 发布
                  08 核心流水线 09 隐私闸门与本人确认（可选） 10 评测 11 分享形态与托管 12 规模/增量/月报年报 13 英文（实验性）
                  14 群聊戏与盲测 15 数据页
prompts/          子任务说明模板 00–19（并行子任务用）；prompts/en/ 英文版（部分模板没有英文版，见 13）
scripts/          导入、统一阅读汇总、pipeline 编排、成本估算、事件机检、冻结、修订、统计、引语核对、隐私闸门、
                  本人确认、页面构建（大事记/小剧场/人物志/数据页/卡片/年度报告/口令页）、站点打包、增量更新、群聊戏抽样（统一 --project <dir>）
assets/           页面模板、站点（Cloudflare Worker）模板、输入样例
evals/            评测：带标准答案的合成语料 + 自动评分（references/10-evaluation.md）
```

## 隐私与分寸

这套东西写的是真人，读者也是真人和他们的家属。skill 内置了分层禁区（公开页面 vs 本地私用的人物模型）、引语出处标注与机检、独立终审；构建时会列出疑似隐私问题供你过目，默认只提醒、开 `privacy.strict` 才拦（references/09-privacy.md 第二节），是否发布由你决定。另有可选的一对一本人确认页，想让被写的人先看看时用。开工前建议先问清性别、关系和不能写的事。

闸门只认逐字或近似命中（已删除素材、敏感词、真名、个人信息、金额住址这类能用规则认出的东西）；换了说法的机器认不出，要靠人看。

## 自测

```bash
bash scripts/test_ingest.sh                       # 6 种输入格式、txt 补充形态、非 UTF-8、config 校验、init_project 容错与跨格式合并、各数据脚本冒烟
bash scripts/test_roster.sh                       # 多份记录 → 人物名单：格式嗅探、重叠导出去重、跨群同账号合并、改名建议、apply 幂等、编号写法、core 联动
bash scripts/test_pipeline.sh                     # 统一阅读、补读剩余行、引语标注、pipeline、成本估算
bash scripts/test_privacy.sh                      # 隐私闸门（默认警告 / 严格模式拦）、标记已看过、金额住址、月报、本人确认（可选）与汇总提醒
bash scripts/test_scene.sh                        # 群聊戏节拍表与盲测打包
bash scripts/test_stats.sh                        # 数据页：统计口径、敏感词零命中、无时刻群、口头禅口径、英文、网站打包（有 playwright 时加浏览器检查）
bash scripts/test_share.sh <项目目录> [年份]        # 卡片、年度报告、口令页（需已做完大事记和 person_stats 的项目）
bash scripts/test_incremental.sh <项目目录>        # 增量更新、月报年报、核心人物（需已有 work/stable/、第一个群是 txt 的项目；init_project 建的即可）
bash scripts/test_incremental_groups.sh           # 多群增量：基线按群记、各群同步进度不同、中途新接入一个群、旧版基线换算
```

前六个自带数据、在临时目录里跑；后两个需要一个真实跑过的项目做源（只读，不改它）。

## 许可

MIT，见 `LICENSE`。字体不在仓库里，各自遵循 OFL。
