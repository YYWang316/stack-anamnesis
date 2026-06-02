"""Derivations — PURE computations over already-extracted values.

A derivation takes a source envelope (or extracted values) the caller has already
loaded and computes a SECONDARY fact the raw fetch does not carry directly — e.g.
supply MOMENTUM (net change over a window) from a circulating-supply time series.

Unlike extractors (one envelope -> typed reads) and the aggregator (cross-source
reconciliation), a derivation can emit a ``ReconciledValue`` DIRECTLY when the fact
is single-source by nature: only DefiLlama carries the historical supply series, so
there is nothing to cross-check (see ``supply_change``; TD-035).
"""
