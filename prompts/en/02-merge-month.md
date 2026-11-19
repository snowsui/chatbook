> Purpose: merge the events extracted from several chunks of the same month into one month file | When: after extraction (01), for every month that was split into several chunks | Input: `{{project}}/work/part_events/<month>_p<i>.json` (your months: `{{months}}`) | Output: `{{project}}/work/events/<month>.json`

# Merging chunks (deduplicate only — never cut)

One month was split into several chunks and events were extracted from each. Merge each month's chunks into one file.

- Read only that month's JSON files under `work/part_events/`. **You do not need to read the chat itself.**
- **Merge only true duplicates**: the same event split into two or more entries because it crossed a chunk (or day) boundary → merge into one:
  - `date`: the earliest
  - `summary`: rewrite (≤240 characters) to cover what each entry said
  - `people`, `groups`: union
  - `heat`: the highest
  - `refs`: pick 2–6 from the entries, **only IDs that already exist**, in time order
- **Everything that is not a duplicate is kept as is — no cutting, no choosing, no rewriting** (copy it verbatim).
  Why: extraction deliberately errs on the side of too many. If merging also selects, that is a second filter applied by someone who has not read the chat and is in no position to judge what matters. Cutting is the user's job, on the finished site.
- "Similar" is not "duplicate". The definition of one event is the same as in extraction (prompts/01): one activity, or one continuous discussion with gaps of no more than about 3 days. A running joke that returns days or weeks later, or an argument at the start of the month and another at the end, are separate events (the kind whose summary says "once again"). **Do not merge them.** When unsure, keep both.
- Rewrite `month_summary` for the whole month (≤90 characters).
- Sort `events` by `date` (same day: keep the original order).
- Same format as the chunks: valid JSON, UTF-8, non-ASCII not escaped (`ensure_ascii=False`), 1-space indent; field order in each event is date, title, summary, people, category, heat, refs, groups. Keep `category` as the internal code (人生节点 / 聚会出行 / 群内热议 / 名场面).
- **Self-check before you report** (same script and rules as the coordinator's check stage): `{{check_cmd}}`. Fix until 0 unresolved warnings; name any legitimate exception and the reason in your reply.

When done, reply with one line: for each month `<month>: N before → M after`, separated by semicolons.
