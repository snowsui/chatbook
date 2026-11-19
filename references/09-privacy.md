# ⑨ 隐私闸门与本人确认（可选）

skill 只负责生成；是否发布、发给谁，由创作者自己决定。这里有两样辅助工具：

- **隐私闸门**（`scripts/privacy_gate.py`）：机器扫描。构建公开页面时自动运行，**默认只提醒**——把疑似隐私问题列出来供你过目，构建照常继续；想让它拦住构建时再开严格模式（第二节）。
- **本人确认**（`scripts/build_review_pages.py` → `scripts/collect_reviews.py`）：可选。想让被写的人先看看时用，构建与发布不依赖它（第四节）。

**闸门只认逐字或近似命中**（已删除素材、敏感词、真名、正则能认出的个人信息和金额住址）。换了说法的——“那件事”“你懂的”、打个比方、只写结果不写事——机器认不出，要靠人看。

## 一、分层禁区

| 层 | 范围 | 处理 |
|---|---|---|
| 公开页面 | 大事记、小剧场、人物志、数据页、月报年报、登录版网站 | 健康、外貌体重、感情婚恋单身、生育孕育、孩子细节、工作变故（辞职、裸辞、被裁、失业、跳槽…）与单位、金额、家庭矛盾、醉酒、荤段子、时政争议、住址、他人真名、账号密码电话、两人暧昧/CP 都不写。**这张表是写作禁区清单的唯一出处**，其他文档和子任务模板都按它。 |
| 本地私用 | 人物模型 out/personas/、证据卡、统计 | 可以如实写行为的**频率和方式**，仍不写具体隐私事实。内容流进公开页面时闸门会重点提醒。 |
| 一对一私发 | 本人确认页 out/review/<人>.html | 只含 TA 自己的内容（含人物模型的对照清单），适合只发给本人，不发群、不放进 site/。 |

“近期私事”（某人有不愿公开的近期私事）要连联想也避开：换个说法、打个比方、写“好事将近”这类暗示都算。

**哪些规则在任何模式下都生效**：用户点名的禁区（config.taboo_extra）、本群敏感词（sensitive_words）、真名（real_names）——抽取说明（prompts/00、01）把它们写在“选什么”之前的硬约束里，不受 family_safe 影响；`family_safe` 只管恋爱暧昧、工作挫折这类分寸项。
**公开细节档位 `config.public_detail`**：缺省 standard——公开页面不写具体金额、住址、证件、健康诊断细节、他人隐私，只写概括（“拿到了 offer”“去看了医生”），闸门对大事记、人物志、月报年报里带数字的金额和门牌住址重点提醒；`full` 才照实记录，由用户显式选择（评测里出现过把用户点名的 offer 金额写进公开大事记的真实泄漏）。

写真人时，发布前可以考虑让本人看看（第四节的确认页就是为这个准备的）——这是建议，不是流程上的关卡。

## 二、闸门规则

**默认只提醒**：命中项全部作为警告打印（位置、上下文、id），照常写 work/privacy/last_scan.json，构建继续——构建时会列出疑似隐私问题供你过目，是否发布由你决定。

**严格模式**（需要时开）：config 写 `"privacy": {"strict": true}`，所有构建脚本里下表「重点」级的命中会中止构建；单独运行 `privacy_gate.py` 时加 `--strict` 效果相同（有重点命中就以退出码 1 结束）。

`build_chronicle.py` / `build_stories.py` / `build_portraits.py` / `package_site.py` 开头都会调用闸门；`build_stats.py` 先按闸门规则丢掉不安全的短句和词，写完 stats.json 后再对页面上的全部文字跑 `stats` 口径（references/15-stats-dashboard.md 第三节）；`build_share_cards.py`（人物志 + 大事记）、`build_wrapped.py`（大事记）在写文件前调用，并把脚本自拼的文字（口头禅、笑法、原话、卡片文案）一起扫；`build_locked.py` 加密前跑 site 口径，并把要加密的页面按重点类规则再查一遍。也可以单独跑：

```
python3 scripts/privacy_gate.py --project <dir>                       # 扫所有公开页面的全部输入（大事记/小剧场/人物志/数据页/月报年报）
python3 scripts/privacy_gate.py --project <dir> --target portraits    # 只扫一类：chronicle / stories / portraits / stats / digest
python3 scripts/privacy_gate.py --project <dir> --target digest       # 月报年报（out/digest/*.md），发群前建议跑一遍
python3 scripts/privacy_gate.py --project <dir> --scan 草稿.md         # 扫任意文件（交稿前自查、子任务回来的稿子）
python3 scripts/privacy_gate.py --project <dir> --strict              # 严格模式：有重点命中时退出码 1
python3 scripts/privacy_gate.py --project <dir> --list                # 看规则来源与忽略记录
```

扫什么：大事记 = work/stable/*.json 的标题/摘要/类别/月摘要 + work/top10.json 理由 + config.pages 文案 +（配了 show_chat_groups 时）会展示的聊天原文片段；小剧场 = out/stories/*.md（含 CAST.md）；人物志 = out/portraits/*.md；数据页 = work/stats.json 里会上页面的文字（人名、复读句、口头禅、笑法、词云）+ config.pages.stats；月报年报 = out/digest/*.md；`package_site` 另外把已生成的 out/*.html 再查一遍已删除素材和敏感词（手改过页面也能发现）。

| 规则 | 来源 | 级别 | 匹配方式 |
|---|---|---|---|
| money / address 具体金额与住址 | 内置（带数字的金额：28k、3万、500元、¥200；门牌：3号楼、2单元、501室、某某路12号） | 大事记、人物志、月报年报里为重点（config.public_detail 为 standard，缺省）；full 时只按下面的内置词表警告 | 宽松匹配；不作用在小剧场（虚构）和展示的聊天原文片段 |
| blocked 已删除素材 | config.blocked_snippets + work/privacy/blocked.txt | 重点 | 去掉空白、标点、Markdown 记号后子串匹配；≥8 字的片段另做近似匹配（片段的二字组有 ≥70% 落在同一句里），抓“改了几个字又加回来” |
| sensitive 本群敏感词 | config.sensitive_words | 重点 | 同上（宽松） |
| pii 个人信息 | 内置正则 | 重点 | 手机号（可夹空格/横线）、身份证号、银行卡号（Luhn 校验）、邮箱、微信号/QQ 号、“密码是…” |
| realname 真名 | config.real_names（列表或 {显示名: 真名}） | 小剧场里为重点，其他页面警告 | 宽松；CAST.md 的真名列不上页面，不查 |
| persona 人物模型 | 内置 | 重点 | 输入里出现 `out/personas/`、`personas/`，或人物模型的章节字样（人物模型、大五人格、Misbelief、发言类型分布、日常基线、私人频道、情境推演、盲区与偏差、对照清单、声音模型、价值排序、核心恐惧、表层与真性格…） |
| builtin 内置分层词表 | 内置 | 警告 | 健康/外貌体重/孕育/感情婚恋/家庭矛盾/金额/住址/证件账号/工作单位职级（含辞职、裸辞、被裁、失业等工作变故，和数据页的展示敏感词同一份）/醉酒，宽松匹配，附上下文 |

重点类在输出里单列（「警告·重点」）；普通警告大部分是正常用法（“流浪猫怀孕”“老板放了葱”），少数是真问题。构建时普通警告只列前 15 条，全部在 work/privacy/last_scan.json，或单独跑闸门看全量。

## 三、处理命中

1. 闸门输出每处命中的 **id**、位置（文件:行，或 `stable/月.json E:月-序号.字段`）、规则和上下文。
2. 觉得有问题的，改原文（删掉、换说法）后重跑；觉得没问题的，不用管。
3. 看过、确认无碍、不想每次都看到的，标记为已看过：
   `python3 scripts/privacy_gate.py --project <dir> --allow <id> [<id>…] --reason "误报"`
   记录写进 work/privacy/allowlist.json（id、规则、命中原文、位置、上下文、理由、时间），之后不再列出，严格模式下也不再拦。输出里给出的 id（含打包时页面复查、人物模型引用的命中）都能直接 --allow：各次构建的命中按“脚本:口径”分开存在 work/privacy/last_scan.json，中间跑过别的构建也找得到。
4. id 由“规则 + 命中原文 + 前后 15 字”算出：段落别处改动不影响；命中处附近改了会重新列出。已删除素材、敏感词、真名、个人信息、人物模型引用这几类按“规则 + 命中原文”认——标记过一次，同样的原文出现在别的页面或输入里也不再列出（想重新检查就从 allowlist.json 删掉那条）；金额、住址、内置词表这类泛词仍按 id 逐处认。

**已删除素材清单**：用户每删掉一句话/一段素材，可以 `--add-blocked "那句话"` 追加进 work/privacy/blocked.txt（或写进 config.blocked_snippets）。下游子任务（回修、终审、重写）再把它找回来，构建时闸门会重点提醒（严格模式下拦住）。真实项目里“删掉的素材又被加回来”发生过两次（lessons.md 第 9 条）。

## 四、本人确认（可选）：发送与回收

想让被写的人先看看时用；用不用、看完怎么处理，由创作者决定。构建和打包不看确认状态，回收过结果的，构建人物志 / 打包网站时只打一行汇总提醒（如“老周 有 2 条标了别公开”）。

1. 生成：`python3 scripts/build_review_pages.py --project <dir> [--person 小鹿]` → out/review/<人>.html。每页三部分：
   - 小传全文，逐段“可以公开 / 要改 / 别公开”+ 备注；
   - 人物模型第 10 节对照清单（out/personas/ 下文件名含该人名字的 md），逐条“对 / 不对 / 部分对”+ 备注；只展示“判断”一栏（“依据”里常有别人的话）；
   - 大事记里 people 含 TA 的事件，逐条“可以公开 / 别公开”+ 备注。
   页面纯静态、无外部请求、手机可用；进度存在对方浏览器里，关掉再开不丢。
2. 发送：一对一私发这个 html 文件（微信“文件”即可），附一句话说明“只发给你，看完点最下面生成确认码发回给我”。页面里有人物模型内容，别发群。
3. 对方填完点“生成确认码”，把那段 JSON 复制发回（夹在聊天文字里也行），或点“下载文件”发回 json。
4. 回收：把收到的内容存成 work/review/in/<人>.txt 或 .json，运行
   `python3 scripts/collect_reviews.py --project <dir>`
   → work/review/replies.md：逐人的「可以公开/对」条数、修改意见（要改/不对/部分对 + 备注）、标了别公开的条目、整体意见、未回收名单；对方看的是旧版页面时会标出。
5. 处理：
   - 修改意见 → 走修订（小传改 md；事件走 apply_fixes 修订清单；对照清单的回答写进人物模型第 10 节“本人”一栏，作为 ⑥ 的输入）。
   - “别公开” → 给用户看清单，用户想要的话运行 `collect_reviews.py --project <dir> --apply-blocked`，追加进已删除素材清单；要删的段落/事件从源文件删掉（清单里的内容再出现，闸门会提醒）。
6. 不想放某人的小传：把 out/portraits/<TA>.md 挪出去再重跑 build_portraits，人物志里就没有这一篇。

## 五、给主控的提示

- 开工时问用户要 sensitive_words / real_names，写进 config（SKILL.md“开工前”第 7 条）。
- 用户说“这句删掉”，可以同步 `--add-blocked`，防止下游再加回来。
- 子任务交回的稿子可以先 `--scan` 一遍再合入；月报年报发群前可以跑 `--target digest`。
- 开工时问用户要不要打开隐私拦截（SKILL.md“开工前”第 7 条），要就写 `privacy.strict`。
- 构建输出里的隐私提醒转述给用户，改不改、发不发由用户决定；用户中途想让闸门拦住构建时，帮他开 `privacy.strict`。
