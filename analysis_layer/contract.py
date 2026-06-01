"""The extractor output contract.

Every extractor in `analysis_layer/extractors/` returns either an
``ExtractedValue`` (success) or ``None`` (a required envelope sub-field was
missing). The shape is deliberately small and immutable: it carries the typed
value plus everything the aggregator needs to reconcile it against other
sources without re-reading the raw envelope — units, source, subject, and the
timestamp the value reflects.

Design echoes ``tools/audit/_numerics.NumericToken``: a frozen dataclass with
``from __future__ import annotations`` so it stays Python 3.9 clean.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Union

# A typed value is numeric (supply, price), integer (count), or boolean
# (is_contract). The aggregator branches on ``unit`` to know how to compare.
Value = Union[float, int, bool]


@dataclass(frozen=True)
class ExtractedValue:
    """One reconcilable fact pulled from a single source's envelope.

    Attributes
    ----------
    metric:
        Canonical metric name, e.g. ``"total_supply"`` / ``"is_contract"``.
        The aggregator keys cross-source comparison on this.
    value:
        The typed value. Float for amounts, int for counts, bool for flags.
    unit:
        What ``value`` is measured in — e.g. ``"USDC"``, ``"USD"``,
        ``"count"``, ``"bool"``. Rule 2 (carry units): the aggregator must
        never compare two values whose units differ without converting.
    source:
        Source slug — ``"alchemy"``, ``"etherscan"``, ``"coingecko"``, …
        Feeds source-authority resolution.
    subject:
        The subject the value describes (the envelope's ``subject`` field,
        e.g. the USDC contract address). Lets the aggregator confirm two
        values are about the same thing (subject_ref resolver, later).
    as_of:
        ISO-8601 timestamp the value reflects — the envelope's ``fetched_at``.
        Critical for the supply-drift rule: contemporaneous on-chain reads
        reconcile tighter than reads days apart.
    provenance:
        Free-form trail of how the value was derived — endpoint, RPC method,
        decimals applied, raw hex, etc. Never used for reconciliation logic;
        it exists so a human (or audit layer) can retrace the number.
    """

    metric: str
    value: Value
    unit: str
    source: str
    subject: Optional[str] = None
    as_of: Optional[str] = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
