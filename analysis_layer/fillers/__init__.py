"""fillers (B.2.8) — tag-aware markdown-template filler.

FINAL stage of the analysis-layer trunk (extractor -> resolver -> aggregator ->
filler). ``fill`` is a PURE function: it takes the aggregator's reconciled values
+ a SubjectRef and returns a filled research markdown, auto-filling only ``[AUTO]``
slots and leaving ``[SEMI-AUTO]`` / ``[MANUAL]`` flagged for a human. See
``fill.py`` for the faithfulness / scope / unit rules and ``../README.md`` roadmap.
"""
from analysis_layer.fillers.fill import (
    SLOTS,
    SlotSpec,
    build_evidence_table,
    fill,
    fill_template_file,
    render_value,
)

__all__ = [
    "SLOTS",
    "SlotSpec",
    "build_evidence_table",
    "fill",
    "fill_template_file",
    "render_value",
]
