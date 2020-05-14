# Changelog

All notable changes to PatchWeave are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and PatchWeave adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The emitted
artifact schema (`patchweave/v1`) is versioned independently of the package: the
schema minor is bumped when fields are added and the major when fields are
removed or repurposed.

## [Unreleased]

## [1.0.1] - 2026-06-23

### Added
- `SUPPORT.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`,
  `ARCHITECTURE.md`, `DESIGN.md`, `ROADMAP.md`, and `RELEASE.md` describing the
  change-review workflow, the threat model, and the scoring rationale.
- `examples/manifest.json`, `examples/catalog.json`, and `examples/sample.diff`
  as the documented fixtures for every workflow recipe.

### Changed
- Queue scoring normalizes the four weights (`risk,surface,gap,blast`) before
  use, so `--weights` need not sum to one.

## [1.0.0] - 2025-09-16

### Added
- Stable CLI contract: the five verbs (`weave`, `queue`, `brief`, `gaps`,
  `metrics`) and the documented exit codes (`0` success, `1` input error,
  `2` gate tripped).
- Compile-only CI workflow and the `Makefile` targets for both language
  components.

## [0.9.0] - 2024-06-11

### Added
- Project scaffolding: `pyproject.toml`, `.gitignore`, `.editorconfig`, and
  `.env.example`.

### Changed
- Terminal brief reworked around the risk histogram and the top slice of the
  review queue.

## [0.7.0] - 2021-10-19

### Added
- `--weights r,s,g,b` on `weave`, `queue`, and `brief` to re-weight the scoring
  blend for a review.
- `--color` ANSI rendering for the terminal brief.

## [0.6.0] - 2020-11-10

### Added
- `queue` verb: emit only the ranked review queue, as text or `--format json`.

## [0.5.0] - 2019-09-24

### Added
- `brief` verb with `text`, `markdown`, and `json` renderers; the Markdown brief
  renders a governance-gaps table and a numbered review queue for pasting into a
  pull request body.
- JSON artifacts stamped with the `patchweave/v1` schema identifier.

## [0.4.0] - 2018-10-02

### Added
- `gaps` verb: prints every unanchored change, unmet requirement, and unknown
  reference and exits with code `2` when the total exceeds `--max-gaps`, making
  PatchWeave usable as a merge gate.

### Fixed
- Explicit anchors now correctly suppress implicit glob anchors so an authored
  requirement id is never second-guessed by glob inference.

## [0.3.0] - 2017-11-21

### Added
- Native C++17 metric engine (`core/patch_metrics.cpp`) with an on-demand
  compiling bridge (`patchweave/native.py`) and a behaviorally identical
  pure-Python fallback selectable with `--pure`.

## [0.2.0] - 2016-11-08

### Added
- `QueueBuilder` and the four-signal review-queue scoring model with
  deterministic score-descending, path-ascending ordering.

## [0.1.0] - 2015-11-17

### Added
- Initial release: manifest and catalog loaders, the `Weaver` anchoring engine
  (explicit + glob passes), requirement coverage states
  (`unmet`/`partial`/`reviewed`), and the terminal `weave` brief.

[Unreleased]: https://github.com/dhirpajr666/PatchWeave/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v1.0.1
[1.0.0]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v1.0.0
[0.9.0]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v0.9.0
[0.7.0]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v0.7.0
[0.6.0]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v0.6.0
[0.5.0]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v0.5.0
[0.4.0]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v0.4.0
[0.3.0]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v0.3.0
[0.2.0]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v0.2.0
[0.1.0]: https://github.com/dhirpajr666/PatchWeave/releases/tag/v0.1.0

<!-- draft note 330 -->
