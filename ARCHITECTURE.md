# PatchWeave Architecture

PatchWeave is a Coding-Agent Change Review Lab that connects change manifests with requirements to prioritize review work and explain patch surface. The repository uses a Python orchestration layer and a focused native companion so input normalization, deterministic analysis and report rendering remain easy to inspect.

## System flow

`	ext
fixtures or operator input -> parser -> normalized domain records -> analysis engine -> report model -> terminal / JSON / Markdown
` 

## Components

- **Python package** owns command handling, portable parsers, report assembly and example workflows.
- **Native companion** mirrors the central calculation for compact command-line use and implementation parity.
- **Fixtures and docs** define stable, readable examples that make each analysis result reproducible.
