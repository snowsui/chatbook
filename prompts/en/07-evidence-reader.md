> Purpose: read one block of a person's messages line by line and write an "evidence card" for the profile and the persona model | When: first step of the profile / persona workflow; each person's messages are cut into time blocks, one subtask per block | Input: `{{project}}/work/people/{{person}}/chunks/<block>.txt` | Output: `{{project}}/work/people/{{person}}/cards/<block>.md`

# Reader's task: write an evidence card from one block of chat

You get one file: **every text message** {{person}} sent during one period (images, voice notes and stickers removed), grouped by date (`## date`).
- Lines starting with `HH:MM` are this person's own messages; `[someone: …]` is what someone else said just before — context only.
- A group marker after the time (such as `‹family group›`) tells you which group the line was posted in. **It is not part of the message.**
- Lines like `[图片] caption` or `[链接] title`: the text after the placeholder is the caption the person wrote with an image (or the title of what they shared). You may quote it, but say it is a caption/title.
- The author's display name is `{{me}}`.

The goal is a **nonfiction profile** of this person, and later a persona model.

## Requirements
- **Read the whole file, every line** (use Read in sections, moving offset/limit forward until the last line). No skimming, no grep-only reading. Write the card after you have finished reading.
- Record only what you can point to. Every item carries a date. Quote the person's words as close to verbatim as possible (you may trim, never change the meaning).
- **Keep speakers straight.** What is inside `[brackets]` was said by someone else. Recording another person's line as this person's is the root of every later misreading — a misattributed quote travels straight into the profile and the model.
- **Keep tone straight.** Sarcasm, jokes, and repeating a meme are not sincere statements. "lol" and "haha" are often punctuation, not laughter; "I'm literally dying" usually means nothing of the sort. When unsure, mark it "(joking?)".
- You are looking for *who this person is*, not writing a log of events.

## Output (fill every section; write "none" if there is nothing; 1,800–3,500 words)

1. **Defining moments (6–12)**: the concrete moments that show this person most clearly.
   Format: `date time | what happened (one or two sentences) | their words "…" | what it shows`.
   Prefer: choices under pressure, looking after someone or insisting on getting something right, a side of them that surprised people, the most typical instance of something they do again and again.
2. **Language fingerprint**: catchphrases; capitalization (all lowercase? ALL CAPS for emphasis?); punctuation and emoji habits (which emoji, how many, ironic 💀/🙃 or sincere ❤️); how they use "lol / lmao / haha / hahaha" (as punctuation, as softener, as real laughter); spelling quirks and abbreviations (u, ngl, tbh, idk); sentence shapes; switching between languages or dialects; what they call themselves and others; their kind of humour (self-deprecating, contrarian, deadpan, meme-repeating…). One or two original lines for each.
3. **How they treat others**: who they talk with most, and how they treat each person (looks after them / bickers / admires / protects), with original lines. Also record **what others say about them** (comments and nicknames visible in the bracketed context and the conversation).
4. **What they care about / fear / hold firm on**: prove it with behaviour, not adjectives.
5. **Contradictions**: surface vs underneath (e.g. tough talk but soft-hearted; seems casual but is the most exacting), with evidence.
6. **Changes during this period**: visible changes in their life, focus or way of talking within this block (only what is visible — do not guess at private matters).
7. **Everyday self**: apart from the big moments, what do they do most in this block (riff on jokes? share their day? just laugh? lurk and react to gossip?) — give 3–5 ordinary examples.
   Why: if only the highlights are kept, the profile and model will make the person deeper and more dependable than they really are. The everyday baseline has to be kept from step one.
8. **Sensitive-topic flags**: for sensitive content in this block, **list only the topic and the date — do not repeat details**: health / body / weight / looks, relationships / dating / being single / set-ups, pregnancy / trying for children, job changes / quitting / layoffs / performance reviews, money and specific amounts, family conflict, sex / dirty jokes, politics, addresses / neighbourhood names, other people's private matters, and this project's extra no-go topics:
{{taboo_extra}}

When done, reply only with: `card path (M lines, read to end)` + one sentence: "the single moment in this block that best represents them". M is the total number of lines in the block file. If you did not finish, write `read to line X of M`; the coordinator will send someone for the rest.
