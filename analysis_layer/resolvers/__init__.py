"""resolvers: analysis-layer trunk stage 2 (extractor -> resolver -> aggregator
-> filler). See ../README.md roadmap.

``subject_ref`` (TD-030) maps a canonical subject to the out-of-envelope
bindings the extractors take as manual args — decimals, per-source ids, on-chain
contract, issuer CIK. ``source_authority`` (TD-031) answers, per metric, which
source is primary and which cross-check — a lookup only; the reconciliation that
consumes it is the B.2.7 aggregator.
"""
