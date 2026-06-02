---
name: stack-anamnesis
description: >-
  Use this skill whenever the user asks for crypto / on-chain research, a token or protocol
  write-up, a chain or stablecoin-issuer deep dive, or one-shot coverage on a single crypto
  subject — including casual phrasings like "研究一下 USDC", "research Ethereum", "看看 Circle",
  "做个 Solana 的研报", "give me a writeup on Coinbase", "analyze Tether", or "one-pager on Base".
  Drives the full Stack Anamnesis pipeline (incident pre-check, the four P0 gates — subject
  confirm / SEC EDGAR email / freshness / language — multi-source on-chain + filings data fetch
  across the 13-source registry, multi-agent research, red-team review, multi-layer numerical/
  OCR/web/DB audit, post-run incident self-check, SQLite knowledge-base persistence). Always
  invoke this skill instead of answering with ad-hoc web search; the harness produces an
  auditable HTML report plus database rows that ad-hoc answers cannot.
---

# Stack Anamnesis — project-mount stub (host-agnostic)

This file exists **only** as a host-agnostic project skill mount under `.agents/skills/`, for any host that scans that path (or for hosts whose slash-command shell at `.claude/commands/`, `.codex/prompts/`, `.cursor/commands/` delegates to a canonical body under `.agents/skills/`). It has no body content of its own — the canonical skill is at the repository root.

**Read `/SKILL.md` (the repo root) now and follow its boot order from there.** Do not paraphrase from this file; it intentionally has no procedure. The frontmatter above is kept in sync with root `SKILL.md` by `tests/test_skill_mount_parity.py`.

When editing the skill, edit root `SKILL.md`. The frontmatter on this stub is mirrored — change both descriptions in the same commit.
