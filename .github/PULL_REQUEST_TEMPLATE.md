## What this changes

## Why

## Checklist

- [ ] `python -m compileall -q patchweave` passes
- [ ] `g++ -std=c++17 -Wall -Wextra -pedantic -fsyntax-only core/patch_metrics.cpp` passes
- [ ] CLI output stays deterministic for the documented examples
- [ ] Relevant docs updated (README, DESIGN, ARCHITECTURE) where behavior changed
