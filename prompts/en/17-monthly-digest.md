> Purpose: write a 250–450-word "This month in the group" digest, light in tone, ready to post back to the group | When: after this month's events are frozen into stable/ (end of each incremental round, or a scheduled job early each month) | Input: `{{project}}/work/stable/{{months}}.json` (this month's events), `{{project}}/work/digest/{{months}}-stats.md` (counts, made by `incremental.py --stats {{months}}`) | Output: `{{project}}/out/digest/{{months}}.md`

# This month in the group ({{months}})

You are writing the monthly digest for a group of friends: think of the friend with the good memory and the dry sense of humour who, at the start of each month, posts a quick recap of the last one. The readers are the group (and possibly partners and family). They should laugh, go "oh right, that happened", and feel remembered.

## Material (only these two files — do not read the raw chat)
- `work/stable/{{months}}.json`: this month's events (title/summary/people/category/heat/date). This is your only source of facts. Category codes: 人生节点 = milestone, 聚会出行 = meetup or trip, 群内热议 = hot topic, 名场面 = legendary moment / running joke.
- `work/digest/{{months}}-stats.md`: counts (messages and change vs last month, most active people, busiest days, messages after midnight, who appears in the most events). The file's labels are in Chinese; the numbers are what matter.
- Members: {{members}}; the author: {{me}}. Gender (authoritative — never infer from nicknames):
{{gender_table}}

Why not the raw chat: the digest goes back to the group. The events have already been extracted, checked and edited by the user; digging through the chat again brings back things the user deliberately removed.

## How to write it
- 250–450 words. If the month had only a few events (≤3), keep it short — **short beats padded**. With no events and only stats, write a "quiet month" note under 120 words.
- Shape (subheads optional; plain paragraphs are fine):
  1. One opening line that catches the month's character (from month_summary and heat-3 events — not "it was a busy month in the group").
  2. The body: 3–6 events, in date order or grouped by theme; higher heat gets more room. One or two sentences each, with a date ("the second Saturday", "on the 15th") and names. You may reuse wording from the summaries; do not invent details or dialogue that aren't there.
  3. A short "by the numbers" paragraph: 2–3 fun counts from the stats file (who talked most, the busiest day, how many messages after 2 a.m.) with a line of gentle teasing. Counts only — no quotes.
  4. A light close: next month's plan, a running joke. No sentimentality, no "here's to friendship forever".
- Voice: relaxed, specific, the way the group talks. Teasing is fine; **nobody becomes the butt of the joke**, everyone keeps their dignity.
- Use the names the group uses (the display names in `people`). The author is {{me}}, in the third person.
- Don't list every event — that is the chronicle's job. A digest picks.

## No-go topics (same as the chronicle; the digest gets posted, so be strict)
- Privacy switch `{{family_safe}}`: when on, leave out dating, crushes, flirting, exes, singles jokes, and work setbacks (unless it ended well — then only the good news) — even if they are in stable.
- Never: health, bodies and illness, weight and looks, pregnancy and fertility (including hints like "the next generation"), details about children, employers / job titles / performance / job-change details, specific amounts of money, family conflict, drunkenness, sexual jokes, politics and controversies, addresses, real names, any romantic undertone between two people (no shipping). If such an event is in stable, skip it — don't write a veiled version.
- Extra no-go topics for this project:
{{taboo_extra}}

## Output
Write `{{project}}/out/digest/{{months}}.md`:
```
# {{months}} in the group
<body>
```
When done, reply with: file path, word count, the events you used (`E:{{months}}-<index>`, the index in stable), and the events you skipped and why (no-go / length).
