# 英文版（English mode，实验性）

> **实验性**：英文支持目前只承诺三件事——**事件抽取**（prompts/en/01、02 + check_events 的英文长度口径）、**统计**（metrics / turnmix 的英文词表与按词计长）、**数据页**（build_stats / stats.js 的英文界面与口径）。其余（大事记/人物志/小剧场页面的界面文字、人物志与人物模型的英文写作、月报年报）有英文模板或部分接入，但没有完整验证过，按“能用、要人工把关”对待。
>
> **档位**：英文群目前建议用 **lite** 档（01 抽事件 → 02 合并，都有英文版）。standard/deep 档的读原文用 00 统一阅读，00 没有英文版（见下面“没有英文版的模板”），人物志、人物模型也只是“能用”，选这两档要人工把关每一步的产出。

给英文群聊（或成品要给英文读者看）做年鉴时用。英文模板不是把中文模板直译：写作传统换成英文的，统计口径换成适合英文的，禁区与隐私规则一条不少。

## 一、怎么选语言

`chronicle.config.json` 加一个键：
```json
{"lang": "en"}
```
- `"zh"`（缺省）：全部行为照中文。
- `"en"`：子任务说明优先用 `prompts/en/` 下的英文模板，产出（事件、小传、模型、群报）用英文写。

**按读者选，不按聊天语言选。** 中文群要给英文读者看（例如留学生群给外国伴侣看）选 en；英文群但读者都读中文，也可以选 zh（子任务读英文原文、写中文产出，没问题）。中英混杂的群：按成品读者选，统计词表两套都要（见第三节 `metric_words`）。

lang 影响的地方：

| 地方 | zh | en | 现状 |
|---|---|---|---|
| 子任务模板 | prompts/ | prompts/en/（缺的退回中文模板并提示） | 已接入 fill_prompt |
| `{{author_title}}` 缺省 | 史官 | Chronicler | 已接入 fill_prompt |
| 事件长度上限 title/summary/month_summary | 14/80/30 字 | 48/240/90 字符 | 已接入 check_events |
| category | 四个中文码 | **仍用这四个中文码**（机器码） | 大事记页面上仍显示中文类别名（未做英文映射） |
| metrics / turnmix 词表与长度口径 | 中文 | 英文词表、按词计长度 | 已接入 |
| 数据页（⑮） | 中文 | 界面文案、数字格式、栏目名（Stats）、分词（按词）、短句长度（按词）、笑声/问句/敏感词表都换英文 | 已接入 build_stats / stats.js |
| 站点栏目名 | 大事记/小剧场/人物志/数据 | 英文栏目名 | 已接入 pagekit / package_site；可用 config.pages.tabs 覆盖 |
| 其他页面文案 | config.pages | config.pages 可全部写英文；大事记/人物志/小剧场模板里写死的中文界面文字**没有英文版** | 未做 |
| all.json 占位符 `[图片]` 等 | 中文 | **不变**（英文模板里解释了它们的意思） | 无需改 |

**英文模板**：`prompts/en/` 下有 01、02、07、08、11、12、13、14、15、16、17-monthly-digest、17b-yearly-digest，文件名与中文版相同，`{{…}}` 占位符集合与中文同名模板相同（fill_prompt 填的是同一套变量）。正文是按英文写作传统重写的，不是逐句对照：中文模板改了，英文版不会自动跟上（出过输入路径落后于中文版的情况），用之前对照中文同名模板核一下输入、输出和“何时用”。

**没有英文版的模板**（lang=en 时 fill_prompt 退回中文模板并在 stderr 提示；主控要在说明末尾加一句 “Write all output in English.”）：

| 模板 | 用途 |
|---|---|
| 00-unified-reader | 统一阅读（standard/deep 档的 read 阶段）——**所以 en 下 standard/deep 档的读原文用的是中文说明** |
| 03-person-profile、04-story-style、05-story-write、06-story-review | 小剧场 |
| 09-portrait-editor | 小传总编终审 |
| 10-portrait-factfix | 小传回修 |
| 18-scene-write、19-scene-blindtest | 群聊戏与盲测 |

## 二、写作传统怎么换（英文模板里的约定）

| 中文模板里 | 英文模板里 | 为什么 |
|---|---|---|
| 太史公·以事见人 | New Yorker profile 的 show-don't-tell：3–5 件带日期的真事 | 同一个原则，英文读者熟悉的形态 |
| Talese 特稿进入 | 不变（Gay Talese, "Frank Sinatra Has a Cold"：场景开头、旁人的话做侧写） | 本来就是英文传统 |
| 汪曾祺·白描与闲笔 | John McPhee：先画结构、抓一个准确的细节；讣闻/致敬体（NYT obituaries、"Portraits of Grief"）：每人至少一个只属于 TA 的具体细节、平实而温暖、不堆悼词式形容词 | 讣闻文体正好是“给真人写短传、读者是家属”的成熟传统 |
| 《世说新语》品藻（8–16 字） | epigraph / one-line characterization（8–16 词） | |
| 题眼 | key line（本人最传神的一句原话） | |
| 「史官曰」 | `## {{author_title}}'s note`（缺省 "Chronicler's note"），第一人称 | |
| 作者本人那篇：众人曰 + 史官自况 | "What the group says"（群友原话拼成）+ "{{author_title}}'s self-portrait" | |
| 正文首次提到作者：「X（即史官）」 | "X (that's me, the Chronicler)" | |
| 篇幅（字） | 篇幅（词），约为中文字数 × 0.6–0.65 | 08：<1000 条 1000–1600 词；1000–5000 条 1600–2300 词；更多 1600–2600 词。07 证据卡 1800–3500 词；11 模型约 4000–6500 词 |

禁区与隐私：逐条等价保留（健康、外貌体重、感情婚恋、生育、孩子细节、工作变故与单位、金额、家庭矛盾、醉酒、荤段子、时政、住址、真名、暧昧感/shipping、他人隐私），另外补了英文群聊特有的误读：
- 反串称呼与泛称：bro / dude / sis / mom / "girl" 常不表示性别或亲属关系——性别仍只看 config.gender；
- `lol` / `lmao` / `💀` 常只是语气标点，不等于真的在笑，更不是嘲笑；
- 反讽句（"love that for me", "great, just great", "living my best life"）字面意思和真实意思相反；
- 英文熟人群里粗口常是亲昵（"you absolute bastard"），人物志里不引用，人物模型里只写频率和用法。

category 的英文叫法（仅供写页面文案、群报正文时用；大事记页面目前不做映射，仍显示中文类别名，见第一节表）：人生节点 = Milestone，聚会出行 = Meetups & trips，群内热议 = Hot topic，名场面 = Legendary moment。

## 三、英文群聊的统计差异

| 方面 | 中文 | 英文 | 现状 |
|---|---|---|---|
| 长度 | 按字 | 按词（字符数会让英文显得“很长”） | metrics 的长度列按词；“>50 字占比”改“>30 词占比”。turnmix 阈值：15 字 → 6 词，6 字 → 3 词 |
| 分词 / 跳线判断 | 二元字（bigram）重合 | 去掉停用词后、≥3 字母的单词重合（英文二元字母几乎处处重合，会把所有发言都判成“接上文”） | turnmix `words_en` |
| 独特用词（person_stats） | 2–4 字 n-gram | 应为 1–3 词 n-gram（字符 n-gram 在英文里全是词的碎片） | **未做**：person_stats 仍按字符 n-gram，英文下这一节参考价值低 |
| 笑声 | 哈哈/hhh/笑死/233 | lol / lmao / haha / hehe / rofl / xD / 😂 🤣 💀；`lol` 常是语气词，“笑”占比会远高于中文群，只能做组内相对比较 | metrics 词表 |
| 表情 | 多为 `[表情]`（贴纸）占位 | 多为正文里的 Unicode emoji；Telegram 贴纸才是 `[表情]` | “表情（占全部）”只计占位符；emoji 进“笑”“暖词”的正则。需要更细的话可加一行“含 emoji 的文字占比” |
| 提问 | ？/吗/啥/怎么… | `?` + what/why/how/when/where/who/which/anyone | metrics、turnmix 都换 |
| 喊话 | 感叹号 | 感叹号 + 全大写词（"WHAT", "NOOO"）——中文版的“英文占比”一项在英文群里没意义，换成“全大写” | metrics |
| 讲自己 | 「我」（不含「我们」） | I / I'm / my / me / myself（不含 we） | turnmix |
| 附和（纯反应） | 好的/确实/哈哈/666 | ok / lol / same / true / fr / bet / yes / nice / wow / +1 | turnmix `REACT_EN` |
| 粗口 | 卧槽/我靠/tmd… | fuck* / shit* / damn / wtf / ffs…（英文熟人群里常是亲昵或语气，A 宜人的“粗口率名次”要谨慎用，群像总览里注明） | metrics |
| 暖词 / 组局词 | 辛苦/抱抱 … 约/聚/火锅 | thanks/love you/take care/proud of you/❤️ … hang out/dinner/drinks/anyone free/who's in | metrics |
| 点名 | 称呼 ≥2 字 | 名字常很短（Al, Jo），子串匹配会误中（"Al" in "also"）——理想做法是加单词边界、不分大小写 | **未做**：点名统计在英文短名上会偏高，别把它当结论 |
| 时间格式 | 年-月-日 | WhatsApp 等导出是 `M/D/YY, h:mm AM` 且月日顺序随地区变 | **不支持** WhatsApp txt：先转成 csv（时间 / 发送者 / 内容三列，时间写成 `YYYY-MM-DD HH:MM`）再导入 |

词表都可以用 config 覆盖（现有机制）：
```json
"metric_words": {"笑": "(?i)\\b(lol|lmao|haha+)\\b|😂|💀", "组局词": "(?i)\\b(pub|footy|brunch)\\b"}
```
中英混杂的群：lang 选 zh，然后用 metric_words 把英文词并进中文正则（`哈哈|笑死|lol|lmao|😂`）。

## 四、英文模式的冒烟检查

在 config 里写 `"lang": "en"`，跑 ingest → split_chunks → `fill_prompt --prompt 01 --files …`，确认拿到的是英文模板、`{{author_title}}` 填成 Chronicler；子任务交回事件后跑 check_events，确认英文事件按 48/240/90 字符的口径检查；再跑 build_stats 看数据页是英文界面。
