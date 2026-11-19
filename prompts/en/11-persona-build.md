> Purpose: build a "playable character model" of one person from the full chat history (local, private use; never published) | When: once the unified read is summarized (00 + collect_evidence), statistics (metrics/turnmix) and the everyday baseline (13) are ready; one subtask per person | Input: `{{project}}/work/people/{{person}}/evidence.md`, `work/metrics.md`, `work/turnmix.md`, `work/stats/{{person}}.md`, `work/base/{{person}}.md`, raw chunks, other people's evidence.md, deep-read cards if present | Output: `{{project}}/out/personas/{{person}}.md`

# Building a character model (required reading for the modeler)

## The goal
This is not a biography and not a recap of what happened. The goal is to distill, from the whole chat history, **a model of the person that can be run forward**: a novelist who reads this file should be able to drop the character into any situation that never happened (time-travel to a martial-arts epic, stuck in an elevator, winning the lottery, a friendship breaking up…) and have them choose and speak in a way that is unmistakably *them*.

Think of it as the character bible a TV writers' room keeps for a returning cast member — except every line of it has to be backed by the record.

Two uses:
1. **Checking against the real person.** The user will hold it up against the actual human and look for the gap between "the person in the chat log" and "the person in real life". So every claim needs evidence and a confidence level, and you must spell out the blind spots the chat log cannot see.
2. **A character bible for fiction.** Later creative work will use it directly as the setting document.

## Mistakes earlier versions made (go straight to the final structure; don't repeat them)
In past projects the first-draft models scored 6–7/10 on accuracy in independent review, and 35–70% in blind tests. The systematic problems:
1. **Highlights only.** Evidence cards pick the memorable moments, so the model made the person deeper, more reliable and more tragic than they are. Most of a person's day in the group is riffing on jokes, "lol", watching drama unfold, bingeing shows, switching topics. → This structure puts **0.5 Everyday baseline and 0.6 Turn-type distribution** *before* the personality portrait.
2. **Over-sanitizing.** Gossip, swearing, dirty jokes, comments on looks, piling on someone were filtered out as "private", and the character came out too clean. → The local-only version records behavior honestly (rule 3).
3. **The framework forcing depth.** A "core fear" or "misbelief" got dug out of one or two jokes; sarcasm was read as sincerity; other people's lines were pinned on the subject. → Threshold for deep claims (rule 2), quote checking (rule 5).
4. **Counting single messages.** Bursts got split, so the model predicted "only ever replies with a word or two"; the correction then overshot into "always replies with a thoughtful sentence". → Always look at **turns** (one person's consecutive messages in the same group), describe the mix in proportions, never as a single rule.

## Materials
- `work/people/{{person}}/evidence.md`: the evidence readers picked out for this person after reading every line of the chat (in time order; each item has a stable key `k=`, the speaker and a kind — read all of it). Items under "to verify" (待核对) at the end have a speaker or text that doesn't match; don't use them directly.
- If present: `work/people/{{person}}/cards/*.md`: deep-read evidence cards (read all of them).
- `work/metrics.md`: behavior indicators comparable across all members (use it for relative claims: "highest question rate in the group" beats "asks a lot of questions").
- `work/turnmix.md`: turn-type distribution. The file is script-generated with Chinese column names: single-message share (单条占比), pure reaction (纯反应), image/voice only (只发图/语音), shares link (转链接), off-thread (跳线), talks about self (讲自己), follow-up question (追问), mentions others (点名他人), short comment / other (短评/其他).
- `work/base/{{person}}.md`: everyday baseline labels on a random 500 messages (if not produced yet, run `13-baseline-label.md` first).
- `work/stats/{{person}}.md`: message volume by year and by hour, catchphrases, distinctive words, who they interact with.
- `work/people/{{person}}/chunks/*.txt`: the raw text, **for verification and extra evidence** (grep for key situations: conflict, being snapped at, being praised, someone asking for help, plans falling through, late night, holidays, losing).
- `out/portraits/{{person}}.md` (if present): the profile already written. You may consult it; don't restate it.
- How others see them: the "others' view" (他评) items in evidence.md; then grep other people's `work/people/*/evidence.md` for this person's name/nicknames.
- To find the k of a quote: grep `work/all.json` (every message has `k`, `t`, `s`, `c`).
- Gender and relationships (authoritative):
{{gender_table}}
{{relations}}
- Nickname mapping and common misattribution types: see the end of `08-portrait-write.md`.

## Method (use these frameworks to triangulate; they are tools, the conclusions must land on this specific person)
- **Big Five** (Openness / Conscientiousness / Extraversion / Agreeableness / Emotional stability): 1–10 per trait + evidence + confidence. Note: group chat systematically overstates extraversion and understates conscientiousness. Everyone's scores will be calibrated jointly in the group overview (16); give a first estimate here.
- **Core motivation and core fear** (the Enneagram's "core desire / core fear" idea, without attaching a type number).
- **Want / Need / Misbelief** (Lisa Cron, Truby): what they visibly chase, what they actually need, and the possibly-wrong sentence they believe.
- **Characterization vs. true character** (McKee): who everyone thinks they are vs. who shows up in choices that cost something.
- **Contradictions** (Forster's round character): at least 3 pairs, each with evidence.
- **Conflict style** (Thomas–Kilmann: competing / avoiding / accommodating / compromising / collaborating) and **humor style** (Martin: affiliative / self-enhancing / aggressive / self-defeating).
- **How they show care**: words, actions, stuff, presence, remembering details… which ones they use and which they avoid.
- **Group role** (Belbin: coordinator / shaper / teamworker / plant / monitor-evaluator / implementer / completer-finisher / resource investigator…).
- **Voice model**: quantifiable traits (from metrics) plus syntax, punctuation, emoji, catchphrases, how they refer to themselves and to others, typical sentence templates — enough that you could "cover the name and still know who's talking".
- **Arc**: what changed and what didn't from the group's founding to now (yearly numbers + events), and what visibly drove it (only what is visible).

## Rules
1. **Everyday first, highlights second.** Section 0 sketch, section 3 behavior patterns and section 4 voice model must agree with 0.5/0.6 — any behavior with a high share in the baseline must have a place in the model.
2. **Threshold for deep claims.** Every core motivation / core fear / Misbelief / Need needs **≥3 mutually independent pieces of evidence, none of them in a joking context** (list the dates). If you can't, downgrade it to [low] and mark it "inferred", or rewrite as "no clear … is visible; on the surface …". It is fine to write "this person shows no obvious deep fear; mostly …". **Do not invent depth to complete the framework.**
3. **Truthful but not exposing.** This is the local, private version: **record behavior honestly** — how often and how they swear, how they gossip, how much they join in on dirty jokes (frequency and style only, no specific content), whether they comment directly on looks, how hard they pile on, topic-hopping / ignoring messages / replying hours later. But **no concrete private facts** (health details, romantic history, specific amounts of money, addresses, employer/rank/specific work incidents, details of family conflict, other people's private matters, any passwords/phone numbers that appeared in the chat) — in "Writing taboos" list only the topic heading. Extra taboos for this project:
{{taboo_extra}}
4. **Counterexamples go in.** After every [high] claim, add one "exception / counterexample" (a time in the record they did the opposite). People are inconsistent.
5. **Quotes.** Every quote must be the person's own words (or explicitly marked "X said to them"), correctly dated, verbatim (trimming allowed). **Put a source tag right after every quote** (keep the tags in the model file; reviewers and revisers check against them): their own words `"quote"<!--k:A:7000123-->`; several consecutive messages `<!--k:A:1,A:2-->`; someone else's words `<!--k:A:7000130@speaker-->`; quotation marks around something that is not a real quote (nickname, name of a running joke) `<!--k:none-->`. The tag goes right after the closing quotation mark.
   When done, run `{{run_verify_citations}} --person "{{person}}" --md "out/personas/{{person}}.md" --strict` and clear every "problem" and "untagged" item.
6. **No single rules.** Replace absolute "by default / usually / mostly they …" statements with proportional mixes (consistent with 0.6). Avoid stock answers like "teases first, helps later" or "tough on the outside, soft inside" — such lines are likely the whole group's common idiom (see "group-wide traits" in the overview), not this person's trait.
7. **No diagnosis.** No psychological or medical diagnoses, no condition names.
8. **No invention.** Mark inferences as "inferred".

## Output structure (fill every part; after each claim put the evidence dates or indicator in parentheses and end with a [high/medium/low] confidence tag)

```
# <name used in the group> · Character model
Version 1 · Blind-test hit rate: (to be filled by 15-blind-test)
> One-line essence (≤20 words)

## 0. Sketch
Three to five sentences, like a character note for an actor. Everyday self first, highlights second.

## 0.5 Everyday baseline
- From base/: "what this person does in the group 80% of the time": top five functions and their shares, distribution of linking/tone/swearing, change over periods.
- **Think in turns**: cite turnmix/turns to describe "what one turn from them typically looks like" (e.g. about half are a single short message; bursts often go one reply + one line about their own day). Do not imply "they mostly reply with a word or two", and do not write "they always reply with a thoughtful sentence".

## 0.6 Turn-type distribution (for sampling in fiction)
- Table: this person's turnmix row (turns | single-message share | pure reaction | image/voice only | shares link | off-thread | talks about self | follow-up question | mentions others | short comment/other), optionally with the group average for comparison.
- 3–5 sentences on how to use it: when writing a chat scene, **sample by proportion**; don't make them "reply thoughtfully" every time.
- **Private channels**: when they go off-thread, which topics do they jump to most (3–5 examples from base/ and the raw text: stocks, a fandom, food, games, the news…).

## 1. Personality portrait
### Big Five (table: trait | score | evidence | confidence)
### Core motivation / core fear (each ≥3 independent non-joking pieces of evidence, or downgraded)
### Want / Need / Misbelief (same threshold)
### Value ranking (when values collide, what do they protect first: face / fairness / friends / efficiency / safety / novelty / … — rank the top five with evidence; say which item in their ranking really sets them apart)

## 2. Surface and true character
### How everyone else sees them (quote other people)
### Who shows up under pressure (3–5 choices that cost something)
### Contradictions (≥3 pairs)

## 3. Behavior patterns (each: trigger → responses as a proportional mix → evidence → counterexample for [high])
Cover at least: everyday replies (proportional mix, consistent with 0.6), being praised, being snapped at / teased, a friend asking for help, a friend feeling low, plans falling through, making a mistake themselves, losing (a game / an argument), late night, someone organizing a meetup, the group going quiet, holidays and birthdays, new things / new tech, making decisions.
### Conflict style / humor style / ways of caring / group role (note: group role mostly describes them at highlight moments)

## 4. Voice model
### Quantified traits (compared with the group average)
### Syntax and punctuation habits, emoji, catchphrases (with counts or years)
### Naming system (what they call each person, how they refer to themselves)
### Typical sentence templates (5–8, **ordered by frequency**, most frequent first, one-word reaction templates last)
### Verbatim samples (10, covering happy / angry / caring / brushing off / nitpicking / self-mocking; verbatim, their own, dated)
### Things they would never say (3–5 lines: "they would never put it like this")

## 5. Relationship map
For each other person in turn: how they treat that person, the pattern of interaction (sparring partners / the one being looked after / admiration / rivals / quiet understanding), one representative quote. Add family members if any (nickname and how they show up, nothing more). Note: these are the patterns "when there's drama"; day to day it's mostly trading a line or a joke.

## 6. Arc (founding → now)
Use yearly numbers and events; for years where their volume collapses, write "reason not visible; not inferred". If the group's main venue moved (e.g. to a larger group with family members), note that a change of setting changes tone.

## 7. Scenario projections (for writers; 8 fictional scenarios)
For each scenario: **two or more possible reactions with rough probabilities** ("about half the time …, about a third …, occasionally …"), the first line they'd say in each branch, and why. In at least 2 scenarios the main branch should be "they don't care much / toss off a joke and move on".
Suggested: stuck in an elevator for two hours; an unexpected windfall (no amount); two people in the group fall out badly; time-travel to become an official in an ancient court; invited onto a reality show; a friend texts "you up?" late at night; the meetup they carefully organized gets one attendee; someone praises them in front of everyone.

## 8. Writing guide
- Archetype / function (what role they suit in an ensemble story; separate everyday scenes from highlight scenes)
- Comedy engine (where their funny comes from and how to set it up)
- Dramatic potential (the contradiction in them most likely to generate story)
- Writing taboos (topic headings only, no details)
- Common miswrites (where writers most often go wrong with this person, including "too deep / too efficient")

## 9. Blind spots and bias (for checking against the real person)
- What chat logs systematically can't see (offline, at work, alone, in front of family, private messages…)
- Traits this model may over- or underestimate and why (talkative ≠ extraverted; a silent year ≠ an empty life; splitting one sentence into several messages inflates volume)
- Claims with thin evidence that need the person to confirm

## 10. Checklist (15 verifiable claims for the user to check against the real person)
Table: # | claim (one falsifiable sentence) | confidence | basis | the person / your view (left blank)

## 11. Revision log
(Leave empty when building; 14-persona-revise appends each round: suggestions adopted, claims changed (old → new), what was deleted, what wasn't adopted and why)
```

Length about 4,000–6,500 words; accuracy matters more than completeness.

When done, reply with: file path, word count, one-line essence, the top five functions in 0.5, the 3 claims you're most sure of and the 3 you're least sure of.
