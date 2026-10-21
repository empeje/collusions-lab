# NOTICE

This file records third-party code and licensing considerations for Collusions Lab.

## Milestone 6A -- double-auction reference (`andyjliu/llm-agent-collusion`)

The Milestone 6A continuous double auction (CDA) benchmark is inspired by the published
mechanics of:

* Paper: *Evaluating LLM Agent Collusion in Double Auctions*, arXiv:2507.01413.
* Repo: <https://github.com/andyjliu/llm-agent-collusion>

**License status: none declared.** The GitHub license API returns `404` and the repository
carries no `LICENSE` file, i.e. "all rights reserved" by default (verified 2026-10-19).
Because of this we do **not** reuse, vendor, copy, or redistribute any upstream source,
data, or configuration.

### What we rely on

Only the **idea / mechanism design**, re-derived from the paper's public description:

* each seller values a lot at **$80**, each buyer at **$100**;
* the competitive (Walrasian) equilibrium clearing price is **$90**;
* a market runs **30 discrete rounds**, each agent posting or withdrawing at most one
  order per round;
* the studied levers are seller/buyer communication, seller oversight, "boss pressure"
  to hold margins high, and hiding the round horizon.

### What we ship

`collusions_lab/environments/double_auction/` is an **independent reimplementation**
written from scratch for this project. It contains no upstream code. It is validated by
our own tests (`tests/test_double_auction.py`) against the published benchmarks
(competitive $90, seller cost $80, buyer value $100).

### Isolation of any local reference checkout

If a developer keeps a local checkout of the upstream repository for personal reference,
it must live only under `experiments/upstream/` (gitignored). That directory is never
imported by the package, never referenced by tests, and never committed.

### Reuse guidance

Anyone wishing to use the upstream engine directly must obtain permission from its
authors first. If the upstream repo later adopts a permissive license, this notice should
be updated and the adapter could be re-pointed at it without changing the monitor
contract.

## Milestone 1 -- Bertrand market adaptation

The Bertrand market environment is an adaptation of standard textbook mechanisms and
metrics, not a vendored implementation. See `docs/milestone-1-*.md` for the recorded
deviations.
