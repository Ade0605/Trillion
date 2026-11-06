"""
board — Trillion's visual board: a small, closed set of blocks the page can
draw, strict server-side validators, and (in later layers) widgets that expand
into those blocks, tools the model uses, packs, and a style guide.

Layer 1 exports the block layer only.
"""
from __future__ import annotations

from .blocks import validate_block, validate_blocks, BlockError, BLOCK_TYPES
from .samples import sample_blocks

__all__ = [
    "validate_block", "validate_blocks", "BlockError", "BLOCK_TYPES",
    "sample_blocks",
]
