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
from typing import Any, Mapping, Optional, Tuple, Union

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


@dataclass(frozen=True)
class SubjectRef:
    """The out-of-envelope bindings a canonical subject resolves to.

    The extractors take certain bindings as manual args because the envelopes
    do not carry them: Alchemy/Etherscan supply decodes need ``decimals`` (USDC
    = 6); CMC's ``quotes_latest.data`` is keyed by a CMC numeric id; each source
    addresses the same subject by its OWN id (CoinGecko slug, CMC id, DefiLlama
    stablecoin id), and on-chain reads need the contract address + chain. This
    is the data the ``subject_ref`` resolver supplies so callers stop
    hard-coding those values (see ``README`` "Why ``decimals`` is passed in").

    Pure data contract — like ``ExtractedValue``, a frozen dataclass with no
    behaviour. The resolver that produces it (analysis_layer/resolvers/
    subject_ref.py) is the pure lookup; this is just its shape.

    Attributes
    ----------
    subject:
        The canonical subject name, e.g. ``"USDC"``.
    subject_type:
        The subject's class, e.g. ``"stablecoin"``. (The on-chain / issuer
        envelopes tag the same asset ``"stablecoin_issuer"``; ``issuer`` below
        names that relationship.)
    decimals:
        ERC-20 token decimals (USDC = 6), or ``None`` for a subject that has no
        on-chain token. Satisfies the Alchemy/Etherscan ``decimals`` arg.
    issuer:
        Human name of the issuing entity (e.g. ``"Circle"``), or ``None``.
    identifiers:
        Per-source ids and on-chain/regulatory keys the extractors/fetchers
        address the subject by — e.g. ``{"coingecko": "usd-coin",
        "coinmarketcap": "3408", "defillama": "2", "eth_contract": "0x...",
        "eth_chain": "ethereum", "sec_cik": "0001876042"}``. Keys are stable
        slugs; a binding a subject lacks is simply absent.
    """

    subject: str
    subject_type: str
    decimals: Optional[int] = None
    issuer: Optional[str] = None
    identifiers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricAuthority:
    """Which source leads a metric, and in what order to cross-check it.

    When several sources report the SAME metric (price from CoinGecko & CMC;
    supply from on-chain reads and the multi-chain aggregators; …) the aggregator
    needs to know who is authoritative and who merely corroborates. This is the
    *answer* the ``source_authority`` resolver returns — a pure lookup, NOT the
    reconciliation itself (tolerance bands / divergence flagging are the B.2.7
    aggregator's job).

    Pure data contract — like ``ExtractedValue`` / ``SubjectRef``, a frozen
    dataclass with no behaviour.

    Attributes
    ----------
    metric:
        The canonical metric name, matching ``ExtractedValue.metric`` (e.g.
        ``"price"``, ``"total_supply"``).
    scope:
        The reconciliation scope this ranking applies in, matching
        ``ExtractedValue.provenance["scope"]`` EXACTLY (``"single-chain"`` /
        ``"multi_chain"``), or ``None`` for a metric with no scope split (price,
        market_cap, …). The README scope rule forbids reconciling a single-chain
        on-chain supply against a multi-chain aggregate — so ``total_supply``
        carries two distinct authorities keyed by ``scope`` and is NEVER
        collapsed into one ranking.
    primary:
        Source slug of the authoritative source — matches an extractor's
        ``SOURCE`` constant exactly (``"coingecko"``, ``"alchemy"``, …) so the
        aggregator joins authority to ``ExtractedValue.source`` with no
        translation.
    cross_checks:
        Ordered source slugs that corroborate ``primary`` (best cross-check
        first). Empty when the metric has a single authoritative source.
    """

    metric: str
    primary: str
    scope: Optional[str] = None
    cross_checks: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ReconciledValue:
    """One reconciled fact + its credibility signal — the aggregator's output.

    The aggregator (analysis_layer/aggregators/reconcile.py) turns a pile of
    same-fact ``ExtractedValue``s into this. The cardinal rule it encodes: the
    reported ``value`` is ALWAYS a real source's actual number (the authority's,
    via ``source_authority``) — never a blend or average. Cross-source agreement
    is recorded in ``audit``/``agreement`` as a CONFIDENCE SIGNAL, never used to
    synthesize a number. On divergence the value still stays the authority's
    number; it is flagged, not dropped or averaged.

    This is what the B.2.8 filler consumes to fill the markdown template.

    Pure data contract — frozen dataclass, no behaviour.

    Attributes
    ----------
    metric / scope:
        The group key. ``scope`` matches the extractors' ``provenance["scope"]``
        (``"single-chain"`` / ``"multi_chain"`` / ``None``). A single-chain
        on-chain supply and a multi-chain aggregate supply are DIFFERENT facts —
        two ReconciledValues, never reconciled across scopes.
    value / unit:
        The authoritative source's actual number and its unit. Not an average.
    source_used:
        Slug of the source the ``value`` came from — the metric's ``primary``
        when present, else the highest-authority available fallback
        (``audit["fallback"]`` records whether a fallback occurred).
    as_of:
        The chosen value's own ``as_of`` timestamp.
    agreement:
        ``"agree"`` (every available cross-check within band), ``"divergence"``
        (some cross-check outside band — value still kept), or
        ``"single_source"`` (no cross-check was available).
    inputs:
        Every ``ExtractedValue`` in the group, kept for the record.
    audit:
        The credibility trail — per cross-check: source, relative ``delta``,
        the ``band`` applied (widened by the ``as_of`` gap for single-chain),
        ``within_band``, ``contemporaneous`` + gap, and a note; PLUS the group
        ``spread`` (max−min, relative) and ``median`` across available values.
        ``delta``/``band``/``spread`` are RELATIVE FRACTIONS (``0.0026`` == 0.26%).
    """

    metric: str
    value: Value
    unit: str
    source_used: str
    scope: Optional[str] = None
    as_of: Optional[str] = None
    agreement: str = "single_source"
    inputs: Tuple[ExtractedValue, ...] = ()
    audit: Mapping[str, Any] = field(default_factory=dict)
