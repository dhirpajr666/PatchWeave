"""The weaving engine: map changes to requirements and score coverage.

The :class:`Weaver` is the analytical heart of PatchWeave. Given a
:class:`~patchweave.model.Manifest` and :class:`~patchweave.model.Catalog`, it
produces a :class:`WeaveReport` that answers four questions a reviewer always
asks:

1. **Which requirement authorizes each change?** — the *anchor map*.
2. **Which changes are unanchored?** — edits that cite no requirement, or cite a
   requirement that does not exist in the catalog.
3. **Which requirements are unreviewed / unmet?** — requirements with no
   supporting change, or with changes but no reviewer sign-off.
4. **How large is the patch surface, and where is the risk concentrated?**

Anchoring resolution
--------------------
A change is anchored to a requirement when *either* of these holds:

- The change explicitly lists the requirement id in ``requirements`` (an
  *explicit* anchor), or
- The change's path matches one of the requirement's ``globs`` (an *implicit*
  anchor).

Explicit anchors always win and are reported with ``via="explicit"``. Implicit
anchors are reported with ``via="glob"`` and only apply when no explicit anchor
was declared. A change that satisfies neither is *unanchored*.
"""

from __future__ import annotations
