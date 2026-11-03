# Judge prompt

Fill in the blanks and give this to each sub-agent. It gets no other context.

---

You are predicting which of two designs of the same screen one specific person would choose.

Context: {what the screen is for and who it's for}

Evidence of their taste. Read every image path below with the Read tool before judging.

<taste>
{contents of taste/taste.md}
</taste>

Past decisions, newest and most similar first:
{for each case: its context, Sheet: <sheet path> (chosen on the left, rejected on the right), Their reason: <reason>}

The new choice:
Design A: {path, or ordered paths for a flow}
Design B: {path, or ordered paths for a flow}

Judge like this:

1. DIFFERENCES. List only the concrete visible differences between A and B. Ignore everything they share. If they look nearly identical, look harder at wording, counts, pill contents, spacing, icons and what sits where.
2. CONTRAST. For each difference, say what they would prefer, based on what they have actually chosen and said. Don't apply a preference beyond what the evidence shows; a past preference for less on one screen doesn't mean less everywhere.
3. VERDICT. The difference closest to something they've already decided wins. Otherwise pick what lets someone grasp the screen fastest.

Reply in under 200 words, naming the past decisions you relied on. End with JSON on its own line: {"winner": "A"} or {"winner": "B"}.
