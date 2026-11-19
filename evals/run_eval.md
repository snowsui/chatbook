# 怎么跑评测

评测集 = 两份“答案已知”的合成聊天（evals/corpus/）+ 自动评分（evals/score.py）+ 3 个测试 prompt（evals/evals.json）。设计与指标解读见 references/10-evaluation.md。

## 0. 准备语料（一次性；改了 src/ 才需要重跑）

```bash
cd <skill 根目录>
python3 evals/corpus/build_corpus.py evals/corpus/roommates --measure   # → exports/roommates.json（ChatLab 格式），回填 speech_measured
python3 evals/corpus/build_corpus.py evals/corpus/bestie --measure      # → exports/bestie.txt
# 子集（例如只取 3 个月做快速冒烟）：
python3 evals/corpus/build_corpus.py evals/corpus/roommates --from 2023-09 --to 2023-11
```
脚本会打印条数、>8 字消息完全重复占比（应 <5%）、消息类型分布、每人条数。

语料目录结构：
```
evals/corpus/<名>/
  world.md            世界设定（给写作子任务）
  truth/              标准答案：persona_<人>.json  events.json  taboo.json  config.json（chronicle.config.json 范本）  corpus_stats.json
  plan/<YYYY-MM>.md   逐日写作计划（plan.py 生成）
  src/<YYYY-MM>.md    LLM 逐月亲手写的聊天（写作说明 evals/corpus/WRITER.md）
  exports/            build_corpus.py 拼出的导出文件（skill 的输入）
```
重新生成语料：改 truth/ → `python3 evals/corpus/plan.py <语料> --start … --end … --total …` → 按 WRITER.md 派写作子任务（每个子任务 3 个月）→ build_corpus.py。

## 1. 建工作区

每个测试、每种条件一个空项目目录，只放导出文件：
```
evals/workspace/iteration-<N>/eval-<id>/{with_skill,without_skill}/project/exports/<导出文件>
```
**不要**把 truth/ 里的任何东西（尤其 config.json、taboo.json、events.json）放进项目目录——那是答案。用户在 prompt 里口述的事实（成员、性别、改名、禁区）已经够 skill 写 config。

## 2. 跑：有 skill / 无 skill

同一轮里同时派两个子任务（别先跑完一边再跑另一边，环境漂移会混进差异）：

- **with_skill**：`先读 <skill 根目录>/SKILL.md 并按它做。项目目录：<…/with_skill/project>。用户请求：<evals.json 的 prompt>`
- **without_skill**：同样的用户请求与项目目录，**不给 skill 路径**。补一句产物约定（否则无法打分）：“网页写到 out/chronicle.html；人物小传写到 out/portraits/<人名>.md；人物模型写到 out/personas/<人名>.md”。
- 子任务没法向用户提问：prompt 里已含开工前要确认的事实；它若仍要问，让它按自己的最佳判断继续并在回报里列出假设。
- 想让基线也有中间产物（work/stable）不现实；基线的事件只能用 html_recall 比。

## 3. 记录 tokens / 时长

每个子任务结束的通知里有 `total_tokens` 和 `duration_ms`，立刻写进该条件目录的 `timing.json`：
```json
{"total_tokens": 84852, "duration_ms": 23332, "total_duration_seconds": 23.3, "subagents": 7}
```
skill 会再派子任务（抽取、写作、审稿），这些子任务的 tokens 要一并累加——让主控在回报里列出它派过的每个子任务的 tokens/时长，或在主会话里记。

## 4. 打分

```bash
python3 evals/score.py --project evals/workspace/iteration-1/eval-1/with_skill/project \
  --truth evals/corpus/roommates/truth --name it1-e1-with --evals evals/evals.json --eval-id 1
python3 evals/score.py --project evals/workspace/iteration-1/eval-1/without_skill/project \
  --truth evals/corpus/roommates/truth --name it1-e1-without --evals evals/evals.json --eval-id 1
```
输出 `evals/results/<名>-<时间>.json` 和 `.md`：汇总分、四组指标明细、逐件标准事件匹配表、计划外 heat≥2 事件、引语错例、禁区命中位置、每人人物模型指标、断言 PASS/FAIL。

只跑了一部分月份时加 `--from/--to`（不加时按 stable/ 里出现的月份算范围）。

## 5. 对比与记录

把每次的汇总分、断言通过数、tokens、时长记成一行（iteration × eval × 条件）。看对比时注意：

- with 与 without 都报 html_recall，它是唯一两边口径一致的事件指标；with_skill 另报基于 stable/ 的 recall。
- 隐私命中按“处”看：一个禁区在 3 个页面出现，算 3 次。
- 人物模型指标单人波动大（只有 2–6 人），看方向不追小数点；见 references/10-evaluation.md「怎么读分数」。
- 改 skill 后要重跑**同一份**语料和同样的 prompt；语料本身改了，历史分数就不可比了（results 里的 truth 路径 + corpus_stats.json 帮你核对）。
