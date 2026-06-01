"""resolvers: analysis-layer trunk stage 2 (extractor -> resolver -> aggregator
-> filler). See ../README.md roadmap.

``subject_ref`` (TD-030) maps a canonical subject to the out-of-envelope
bindings the extractors take as manual args — decimals, per-source ids, on-chain
contract, issuer CIK. ``source_authority`` (per-metric priority) lands later.
"""
