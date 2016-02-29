# PatchWeave Design Notes

## Product intent
PatchWeave makes connects change manifests with requirements to prioritize review work and explain patch surface practical in a reviewable developer workflow. It favors compact source data, deterministic scoring and reports that retain the evidence behind every result.

## Design principles
1. **Traceable results** — every score connects to normalized input records and named calculations.
2. **Portable artifacts** — JSON and Markdown reports travel cleanly through pull requests and release notes.
3. **Compositional analysis** — parsers, domain models, metrics and renderers can evolve independently.
