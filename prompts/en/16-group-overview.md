> Purpose: pull all character models together into a "Group portrait overview": summary table, relationship matrix, how the chat really works, writing guide, joint Big Five calibration, group-wide traits, blind spots | When: after every person's model is final (14); one subtask (optionally paired with an independent reviewer following 12) | Input: `{{project}}/out/personas/*.md`, `work/metrics.md`, `work/turnmix.md`, `work/base/*.md`, `work/stats/*.md`, `work/all.json` (merged timeline, for script counts), raw chunks | Output: `{{project}}/out/personas/00-群像总览.md` (keep this exact file name; the document's English title is "Group portrait overview")

# Group portrait overview

This document lines up all the character models side by side, for checking and for fiction. Same rules as `11-persona-build.md`: no diagnosis, no concrete private facts, no invention. Extra taboos for this project:
{{taboo_extra}}
Gender and relationships (authoritative):
{{gender_table}}
{{relations}}

## Why this needs its own document
The models were written by different modelers, which produces three kinds of problems you can only see when they sit together:
1. **Different rulers.** Big Five scores bunch into two or three middle values (e.g. conscientiousness all 6–8), some with decimals — they can't be compared.
2. **Template clones.** "Lets themselves be looked after", "passes off effort as no big deal", "tough on the outside, soft inside" appear almost word for word in half the models — that's the group's shared idiom, not personality.
3. **Highlight and harmony bias.** The relationship matrix is all warm labels and every question gets answered; the equally common "nobody replied", "the topic got hijacked", "everyone talking past each other" are systematically missing.

## How to work
- Recompute the numbers yourself with scripts from `work/all.json` (member lines only; if family members' messages aren't in people, say so), `metrics.md`, `turnmix.md`, `base/`. **Don't copy numbers from the individual models.** Check every ranking claim in the models ("highest in the group", "the only one", "the most") one by one; record the wrong ones in section 8 and change them minimally.
- Character judgments come from each person's `out/personas/<person>.md`; cross-check direction between models (A says B is like X — does B's model say the opposite?).
- Give a date for every event you cite, so it can be found in the raw chunks.
- If "only / most / never" doesn't survive recomputation, change it to "one of the few / one of".

## Output structure
```
# <group name> · Group portrait overview
> One epigraph line: what this group is really like (not what it looks like at its best).

Data sources and rules.
**Read this first**: the character models were mostly built from highlight events; what everyone actually does day to day is reply, post bits of their day, riff and laugh. For everyday scenes start with "3b"; use sections 1 and 2 for highlight scenes.

## 1. Summary table
Table: person | one-line essence | O | C | E | A | S (after joint calibration, see section 5) | group role (at highlights) | conflict style | humor style | way of caring | core motivation

## 2. N×N relationship matrix
- Row = A, column = B, cell = A's pattern toward B (two to four words). Note: cells describe the pattern "when there's drama"; day to day it's mostly a traded joke or an "lol".
- **Strength skeleton**: pairwise "spoke right next to each other" counts (symmetric), and the structure they reveal (e.g. "a hub-and-spoke around one person, with cross links between spokes an order of magnitude weaker"); normalize by each person's total volume.
- **Asymmetry**: A treats B as their number-one partner while B ranks A fourth — that's not a contradiction, it's story.
- **The 6–8 most dramatic pairs**: for each, the pattern, where the tension comes from, quotes (dated, speaker verified), and what onlookers said.

## 3. Group dynamics
### The real shape of the chat (read this first)
Use statistics to show how common each of these is in the record, with 1–2 dated examples each:
1. **Parallel threads**: each person's off-thread (跳线) share (turnmix); how often quoted replies reach back hours.
2. **Topic hijacking + echoing**: is hijacking the topic and repeating someone's line the group's default comic rhythm?
3. **Said it, nobody answered**: of the openers after 2+ hours of silence, what share get no reply within 2 hours, per person.
4. **Deflected with a joke**: when someone says they're tired or unhappy, is the next line another thread or a pun? Does real care move to private messages and the next time they meet?
5. **Only a few catch it**: when someone is low, does everyone respond or just a few while the rest carry on?
6. **"Getting it done" and "having the last word" are different things**: who makes plans actually happen vs. who most often sends the last line of a conversation (give counts and volume-normalized rates).
### Who usually does what in a conversation (statistics + checked against the raw text)
Morning opener (who says "morning"), restarter (first line after a silence; count and rate), first responder, cheerleader, closer (gets things done), last word, the one who steps in when it's quiet (count keywords like "so quiet / nobody's talking / someone say something"), late-night watch, birthdays (who posts at midnight, who's usually first). For each, describe the *pattern*, not just a name. Also include examples where **nobody** closed it out.
### Who stands where in a conflict
Who lights the fire, who most often gets surrounded, who cushions, who avoids.
### How the whole group changed (founding → now)
Yearly volume curve; for collapse years write "reason not visible; not inferred"; did the main venue move to another group (e.g. a bigger group with family members)? A change of setting changes tone — don't mistake it for a change of personality.

## 3b. Everyday baseline side by side
Table: person | top three functions (base, random 500, per message) | replies to context % | organizing/caring % | single-message share (单条占比) | pure reaction (纯反应) | off-thread (跳线) (turnmix, per turn). Note the two units differ; don't subtract one from the other.
One paragraph: what these people actually do day to day (how many percentage points are organizing and caring; "coordinator, carer, host" are highlights a few times a year, not the base layer).

## 4. Writing guide for the ensemble
### Story types that fit (e.g. ensemble sitcom, "someone is leaving" family drama, bottle episode, reunion story, genre transplant)
### Pairings (comic duos, rivals, protector relationships, mirror characters — for mirrors, spell out where the two differ)
### Each person's most natural function in a full-cast scene (table: person | function | one highlight move | the more common everyday move)
### Writing chat scenes
Give ready-to-use proportions from turnmix and the timeline:
- per 10 turns, roughly how many pure reactions, off-thread turns and updates about one's own life (and how this differs by person);
- at least two threads at once (one practical, one idle, optionally someone's own day); quoted replies can reach back half an hour to several hours;
- a bit over one in ten openers gets no reply — when it falls flat, don't rescue it and don't write the character as hurt;
- emotions get deflected with a joke, and only one or two people respond;
- it doesn't have to resolve; if it does, who resolves it and after how long;
- who usually has the last word and what kind of line it is; who gets to send bursts.
Add a **fictional** sample chat (labelled "fictional, not from the record"), a dozen or so lines, three threads in parallel, someone left unanswered.
### The most common mistakes when writing this group
At least: making everyone sound like one person (tell them apart by voice indicators: punctuation, emoji, catchphrases, how they break lines); treating talkative as extraverted and quiet as cold; getting gender wrong (ironic nicknames); letting anyone deliver a long lyrical speech; having the wrong person organize things; writing a quiet year as emptiness or crisis; only writing the main group; treating highlights as everyday — too harmonious, too efficient.
### Family members (this far and no further)
If family members' messages are outside the modeling scope: nicknames only; they can appear as people who riff, egg others on, or start sign-up lists; no individual voice, nothing about their work, family or real names.
### Shared taboos (topic headings only)

## 5. Joint Big Five calibration
### Scoring basis
- **Scores are relative rank within this group, not population norms**: 5 ≈ the group's median; 3 doesn't mean "very low", only "furthest back in this group".
- **Forced spread**: each trait uses the range 3–9; whole numbers only; no more than 2 tied pairs per trait; any two people share the same score on at most 1 of the five traits.
- **Ranking basis**: metrics.md cross-member indicators + behavioral evidence from the models (with checkable dates). Break ties first with secondary indicators, then with the amount and cost of behavioral evidence.
- **No volume**: nothing derived from message volume (absolute counts, lurking time, bursts) goes into E or A.
### Chat bias and the measure used (table: trait | how group chat misleads | what we rank by | what we don't use)
- **E Extraversion**: primary = **rate** of opening a topic after 2+ hours of silence (cold-start opener ratio), @ rate, meetup-word rate (组局词) — sum of the three ranks; secondary (ties only) = laughter/exclamation, evidence of offline socializing. Not used: volume, absolute count of cold-start openers, bursts, being online late. (A talker may only ever reply; a quiet one may be the life of the party offline; network centrality ≠ extraversion.)
- **C Conscientiousness**: planning (backups, lists, advance notice), punctuality, keeping promises, how much they procrastinate on their own business. Not used: "running errands for friends" (group-wide trait).
- **A Agreeableness**: primary = swear-rate (粗口) rank (lower = more agreeable) + warm-word-rate (暖词) rank (higher = more agreeable); behavioral evidence (conceding in wording, conflict style) only adjusts between two neighbors whose rank sums differ by ≤1. Not used: dropping things off for people (group-wide), volume; "avoiding criticism" is not agreeableness.
- **O Openness**: ideas and cross-domain interests, imagination, actively trying new tech/experiences. Not used: English-word rate, amount of TV watched.
- **S Emotional stability**: frequency and spill-over of negative emotion, defensiveness when called out, recovery speed; late-night messages and ellipses are secondary evidence only. Not used: a single emotional outburst (ellipses and "I'm losing it" can just be style).
### Calibrated summary table (table: person | O | C | E | A | S | original self-scores O/C/E/A/S) + the biggest changes and why
### Ranking table per trait (rank | person | score | each primary indicator's value and rank | rank sum | supporting evidence)
Note that people with small samples have the least reliable ranks; for keyword indicators (warm words etc.) that undercount, go by rank and ignore decimals.
After calibration, remind the main agent to sync the Big Five in section 1 of each person's model.

## 6. Group-wide traits (don't write them as individual traits)
- Table 1 (**traits shared across models** — a de-cloning tool): shared trait | originally written for whom | what is genuinely different about each person. Anything that appears almost word for word in 3+ models is the group's idiom; rewrite each person's version as an individual one backed by the record. Watch for this: if several people's evidence comes from **the same conversation on the same day**, that's one group topic, not several individual traits.
- **Group behavioral habits** (more useful for writing scenes): e.g. sharing a link with a two-word comment, parallel threads, deflecting emotion with a joke, topic hijacking and echoing, posting birthday wishes at midnight.
- Table 2 (judged to be individual traits, kept only on the 1–2 people with the strongest evidence): trait | kept on | removed from / rewritten for.
### Identification test: one-line essence + core fear + Misbelief (table)
With everyone side by side, no two rows should be swappable; if they are, go back and fix them.

## 7. Shared blind spots and biases of this set of models
### Measurement
Splitting one sentence into several messages inflates volume; "who they reply to most" is structurally dominated by whoever talks most (use symmetric, normalized counts for relationships); cold-start openers have both a count and a rate; keyword indicators undercount; small samples; the merged timeline excludes family messages, and ordering within the same minute is unreliable.
### Systematic bias
Highlight bias; harmony bias; group chat overstating extraversion and understating conscientiousness (each model corrected by a different amount); weak Big Five discrimination (handled in section 5); template clones (handled in section 6); years where volume collapses break the arc; a change of main venue changes the setting; private messages and offline life are invisible; **point-of-view bias** — the raw record comes from the client, {{me}}; be especially careful with judgments involving the client (especially their criticisms of others), and apply the same standard of evidence for and against them as for everyone else.

## 8. Verification log
### Corrected (minimal change; which model, old wording → new wording, the recomputation behind it)
### Checked and consistent
### Still to confirm (list for the user)

## Revision log
Version, date, basis (each review suggestion: adopted / partly adopted / not adopted + note).
```

No hard length cap, but every section gives the conclusion first and the evidence second; prefer tables.

When done, reply with: file path, the strength skeleton in one sentence, the overall "nobody replied" share and its per-person range, the three biggest changes in the Big Five calibration, and the number of items still to confirm.
