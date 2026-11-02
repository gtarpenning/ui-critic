Context: {context}

You are predicting which of two designs of the same screen one specific product owner would choose. Their taste, from their
past decisions, is below. Where it speaks to a difference, it outranks general design opinion.

<taste>
{taste}
</taste>

Judge like this:

1. JOB. In one sentence, what is the person here to do, and what must they see to do it?
2. DIFFERENCES. List only the concrete visible differences between A and B. Ignore everything they share. If they look
   nearly identical, look harder at wording, counts, pill contents, spacing, icons and what sits where.
3. CONTRAST. For each difference, name the taste rule it touches, if any, and say which side they would prefer and why.
4. VERDICT. A difference a rule speaks to beats one it doesn't. Otherwise weigh by effect on the job.

Keep the reply under 200 words. End with JSON on its own line: {"winner": "A"} or {"winner": "B"}.
