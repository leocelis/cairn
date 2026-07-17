"""Storage adapters — the boundary that keeps the core storage-agnostic.

The engine core depends only on these Protocols, never on a concrete store
(`storage_agnostic_core`). An in-memory / YAML / SQLite / graph backend all
implement the same interface; swapping scale changes the adapter, not call sites.
"""

from cairn_engine.adapters.base import AliasTableAdapter, GraphAdapter

__all__ = ["AliasTableAdapter", "GraphAdapter"]
