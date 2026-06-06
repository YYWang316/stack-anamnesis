"""analysis_layer/qc/ — the content-honesty QC gates (⑤, TD-048).

DISTINCT from ``analysis_layer/render/validate.py`` (④.3 HTML integrity): the
``qc`` package never looks at the rendered document's structure — it checks the
TRUTHFULNESS of the agent-written report against the deterministic facts bundle.
``numbers`` (⑤.1) is the first piece: a fail-closed trace that every
machine-produced number survives unchanged into the final report.
"""
