"""aggregators: the reconciliation / credibility layer (B.2.7, TD-032). Third
stage in the analysis-layer trunk (extractor -> resolver -> aggregator ->
filler). See ../README.md roadmap.

``reconcile.reconcile(values)`` groups same-fact ``ExtractedValue``s by
(metric, scope), picks the authority's ACTUAL number (never an average), and
records cross-source agreement as a confidence signal. The B.2.8 filler consumes
the resulting ``ReconciledValue``s.
"""
