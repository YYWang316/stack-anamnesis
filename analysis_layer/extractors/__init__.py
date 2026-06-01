"""Per-source extractors. Each module is a set of PURE functions:
``envelope dict -> ExtractedValue | None``. No I/O, no fetching.

Built: alchemy. Roadmap (see ../README.md): sec_edgar, coingecko, etherscan,
coinmarketcap, defillama.
"""
