> Purpose: label 500 random messages from one person, one by one, to measure what they actually do in the group day to day | When: before building the persona model (11) (or before revision 14), one subtask per person | Input: `{{project}}/work/base/{{person}}-sample.txt` (500 messages sampled by script with a fixed seed, each with the two preceding lines as context 〔…〕), `work/turnmix.md` | Output: `{{project}}/work/base/{{person}}-tags.tsv`, `{{project}}/work/base/{{person}}.md`

# Everyday baseline labelling

Purpose: correct the bias that comes from building a persona from highlights alone. Evidence cards pick out the big moments; this uses a random sample to see the everyday texture.

## Label every message (all 500 — no sampling)
Give each message three labels:
1. **Function** (pick the single main one):
   A riffing / joking along　B pure laughter or filler (lol / haha / lmao / ??? / omg / hmm / ah)　C gossip, people-watching (people they know or celebrities)　D entertainment (shows / reality TV / games / cards / books)　E sharing their own life / self-presentation　F complaining / venting (work, life, society)　G asking for information　H giving advice / explaining / answering　I organising / scheduling / logistics　J caring / comforting / congratulating　K roasting / egging on / teasing others　L arguing / nitpicking / correcting　M sharing links / news / info　N dirty jokes or innuendo　O other (including one-word acks like "ok / yeah / sure / k")
2. **Link**: reply (responds to what came before) / ignore (talks past it or starts their own thing) / open (starts a new topic after a lull, or explicitly)
3. **Tone**: positive / neutral / negative; plus whether it contains swearing (yes/no)

Write each message to `work/base/{{person}}-tags.tsv` (index\tfunction\tlink\ttone\tswearing), then compute the stats with a script — do not tally in your head.

## Note: one message ≠ one turn
The sample is drawn by **single message**. People split one thought into several messages ("wait" / "no" / "that's actually insane lol"), so one turn becomes three items, all labelled "riffing" or "one-word". The share of "pure laughter / one-word" here will therefore be higher than in per-turn statistics. When you write the "everyday portrait", compare with this person's row in `work/turnmix.md` (per turn). The two use different units: **do not subtract one from the other, and do not conclude from the per-message numbers that "they mostly reply with a word or two".**
Also, a high "reply" share here and a high "off-thread" share in turnmix do not contradict each other: people are responding to *some* thread, just often not the line immediately before.

## Output `work/base/{{person}}.md`
```
# <person> everyday baseline (500 random messages)
## Function distribution (table: function | count | share | 1–2 typical examples, private content as [redacted])
## Link distribution, tone distribution, swearing share
## By period (split the time since the group began into thirds; top five functions in each)
## Everyday portrait (about 200 words): what this person is usually like in the group — from the stats and sample only, not from prior impressions; describe what "one turn" looks like using turnmix
## Differences from the persona model (if out/personas/<person>.md exists, read sections 0–4 and compare): what the model overestimates, underestimates and misses, 3–5 each, with sample indices
```
Privacy: in examples, write [redacted] for health, relationships, money amounts, addresses, employers and similar details; dirty jokes are counted, never quoted. This project's extra no-go topics are likewise never quoted:
{{taboo_extra}}

When done, reply with: file path, the top five functions with their shares, and the model's single biggest overestimate and underestimate (write "none" if the model hasn't been built yet).
