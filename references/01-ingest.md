# ① 导入与标准化

目标：把一个或多个群的导出文件，变成一份按时间排好、人名统一的 `work/all.json`（格式见 CONTRACT.md）。后面所有模块都只读它。

## 拿到导出文件

各平台怎么导出、支持哪些格式、手动整理的 txt 会丢什么，见 references/00-export-guide.md。提醒用户：图片/语音只保留占位符（这对文字类产出足够）。

## 步骤

推荐直接走下一节「多份记录与人物名单」（init_project → roster），它会写好 groups / aliases / members / core / me。手写 config 时：

1. 写 `chronicle.config.json`：groups（每群一个 key、显示名 label、文件、格式）、me、aliases、members（全体成员）、people（要写人物志/模型的人）、gender、relations、taboo_extra。
2. `python3 scripts/ingest.py --project <dir>` → work/all.json，并打印每群条数、时间范围、发言人列表。
3. **让用户核对发言人列表**：同一个人有多个昵称就补进 aliases，重跑。作者本人在 all.json 里统一记为 `me`；引用回复 `（回复 X: …）` 里的 X 也在这一步过 aliases（作者本人写成 config.me 的显示名），所有格式一致。没配 members 时 ingest 会打印按发言量推断的成员名单，让用户确认后写进 config.members。
4. 多群时：给每个群一个短 key（A/B…），事件里 groups 字段会标出出处；网页可以只展示某些群的原文（隐私考虑：核心小群的原文通常不展示）。

## 多份记录与人物名单

用户手里常常是好几份导出：几个群、同一个群换电脑前后各导出一次、一个群一部分是 txt 一部分是 json。用户心里也只有“核心人物”这一个概念。

### 1. init_project：识别格式、分群、合并重叠导出

```
python3 <skill>/scripts/init_project.py --project <dir> ~/exports/ ~/Downloads/old.txt [怪文件.log:txt]
```

- **格式嗅探**：.json 看结构（json-array 数组 / ChatLab 的 chatlab·meta·messages / Telegram 的 name·messages），.csv 看表头（time/时间、sender/发送者、content/内容，可选 id/消息ID，列名不是默认的就写进 `groups[].columns`），.txt 区分 QQ 消息管理器导出（`消息对象:` 头、`昵称(QQ号)` 行）和普通文本。文本不是 UTF-8 时自动试 GB18030、UTF-16 并提示。目录递归找 .json/.txt/.csv，识别不了的跳过并提示。
- **读不了的文件不拖累别的**：空文件、只有表头的 csv、没有日期的无时间 txt、直接点名却认不出格式的文件，都跳过；能读的先写进 config 并导入，最后列出“没导入的文件 + 办法”（没日期的 txt 写成 `文件:txt@2024-02-10` 重跑即可）。
- **分群**：每个群一个短 key（A、B…）、label 取导出里的群名（ChatLab meta.name、Telegram name、QQ 消息对象）；json-array/txt/csv 没有群名就用文件名，脚本会提示——这个名字会显示在页面上，让用户改成好认的（config.groups[].label；网站标题是 title / pages.name）。
- **同一个群的多次导出**：同格式、且群 ID/群名相同或重合 ≥ min(10, 较小一份的一半, 至少 3) 条消息，就认成同一个群，写成 `"file": ["旧", "新"]`。ingest 按平台消息 ID 去重（没有 ID 按 时间+发送者+内容），同一份导出里本来就重复的消息保留（多重集取最大）。时间不重叠的两段导出认不出来，手动把 file 改成列表即可。
- **同一个群、不同格式**（一份 json、一份手动 txt）：按 分钟+内容 比对，重合够多只提示“疑似同一个群”，附合并命令 `init_project.py --project <dir> --same B=A`（把 B 并进 A；信息少的格式并进信息多的）。合并后 A 的 file 里写成 `{"file", "format"}` 元素，ingest 按 分钟+内容 去重。
- **去掉整个群**：`init_project.py --project <dir> --drop-group C`（只改 config，导出文件不删）。
- config 已存在时只追加新群/新导出，不动用户写过的键；同一文件重复传入会跳过。最后自动跑 ingest。打印的后续命令路径已加引号，可直接复制。

### 2. roster build：跨群汇总人物、给编号表

```
python3 <skill>/scripts/roster.py --project <dir> build
```

ingest 另写一个旁路文件 `work/senders.json`（每条消息的发送者平台账号、原始昵称、被引用消息的稳定键），roster 用它把发言人并成“人”：

- **自动合并**：同一平台账号（json-array 的 sender_id / QQ 号 / ChatLab platformId / Telegram from_id）的所有昵称是同一个人，曾用名全收进别名；ingest 归一后同一个名字（含 config.aliases 已并的）也算同一人；json-array `is_self` / ChatLab `ownerId` 标记的都是作者本人。
- **只建议、不合并**（没有账号的 txt/csv 尤其需要）：引用回复里被引用的名字 ↔ 被引用消息的实际发送者（有引用 ID 按 ID，没有就在同群往前 300 条里找开头相同的消息）；名字包含或编辑距离 1；同一个群里一个名字不再说话、45 天内另一个名字开始说话（改名衔接，只在至少一方没有账号时算）；和作者本人用过的名字相同或相近。两人同期在同一个群都在说话的不建议合并（更可能是外号共用）。
- **可能是两个人**：一个名字下有两个以上账号、同群同期都在说话（同名不同人），提示用 `--split` 拆开。
- 每人：编号（跨多次 build 稳定，并掉的旧编号仍能用）、称呼（最近用的群名片；config 里已定的称呼优先）、曾用名、各群消息数、活跃月数与首末日期、被引用回复 / 被接话 / 被点名与综合分（select_core.py 口径）、是否作者本人、推荐等级——核心 = select_core 的 people 候选，成员 = select_core 的 members 建议 + ≤15 人的群里活跃（≥5 条且 ≥ 该群 1%）的人 + 作者本人，其余为路人。多群跨度不同时“全程”按消息最多的群算。
- 产出 `work/roster.md`（给用户看）和 `work/roster.json`。

### 3. 给用户看、一句话回复、apply

把编号表、自动合并结果、各条建议给用户看（多群时先说各群人数），请他一句话回复，例如「核心 1-3、5；3 和 7、8 是同一个人；2 叫大爷；我是 4；11 是机器人去掉」，换成：

```
python3 <skill>/scripts/roster.py --project <dir> apply --core 1,2,5 --merge 3=7,8 --rename 2=大爷 --me 4 --drop 11
```

- 几个人改称呼：`--rename 1=芳姐,2=小周`（逗号/顿号分隔多对）或每人写一个 `--rename`；新称呼里不能有逗号、顿号、分号、等号，格式不对直接报错、不写 config。几组合并：`--merge "3=7,8;4=9"`（逗号分隔同一组的成员，组与组之间用分号）或写多次 `--merge`。

- 写回 config：`core`（核心人物）、`members`（不写 `--members` 且 config 里没有时 = 核心 + 推荐为成员的人 + 作者本人；`--members auto` 强制按推荐重算；`--members 3,4` = 核心 + 这些人 + 作者本人）、`me`、`aliases`（全部曾用名和被引用时的称呼 → 称呼；一个名字几个人用过就改用账号做键）。`people` 不写，缺省 = core。
- `--rename` 会把 config 里 members/core/people/gender/nicknames/deep_read/stats.core 跟着改；`--split 9` 把同名的几个账号拆开，重名的加（2）；`--drop` 的人从名单去掉，以后 auto 也不收。
- 编号可以写 `1,2,5`、`1-3`、`1、2、5`、`"1 2 5"`，也可以直接写 roster.md 里的称呼（`--core 小鹿,大熊`）；认不出的会说哪个认不出。
- 写完自动重跑 ingest 和 build，汇总行给出当前已选的核心/成员人数。幂等：同样的参数再跑一次，config 不变。
- `--drop` 掉的人（机器人、广告号）数据页也整个不计。
- 推荐只是起点：外号被几个人共用、一个人在不同群用不同名字、作者本人在 txt 群里没有标记，这些都**以用户说的为准**。

## 增量更新

群还在聊、隔一段时间重新导出时，用 `incremental.py`：对比上次的基线，把月份分成 new / tail / changed，只为新增部分切分段、登记任务，已修订的月份不动。完整步骤见 references/12-scale-incremental.md 第六节。已冻结的事件引用的是稳定键 `k`（平台消息 ID），不受序号变化影响。

**没有消息 ID 的格式（txt / qq / 没有 id 列的 csv）**：稳定键是 `L<时间戳>_<同秒序号>`。重新导出时如果同一秒内的消息有增删（例如补导了之前漏掉的消息），同秒后面的序号会错位，冻结的引用就会指向邻居消息或失效。重跑 ingest 后先跑 build_chronicle 看“无效引用”数，再抽查几件事的原文片段；能选的话优先用带消息 ID 的导出格式。
