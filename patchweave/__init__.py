"""PatchWeave — Coding-Agent Change Review Lab.

PatchWeave consumes a *change manifest* (the files an agent or human touched in a
work session) together with a *requirement catalog* (the intended scope of work)
and weaves them into an auditable review artifact. It maps each changed file to
the requirements that authorize it, flags unanchored edits (changes with no
governing requirement), surfaces unreviewed requirements (requirements with no
supporting change), quantifies the patch surface, and assembles focused review
queues that a reviewer can burn down deterministically.
