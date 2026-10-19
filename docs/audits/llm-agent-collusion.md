# Audit: LLM Agent Collusion in Double Auctions

- **Paper:** *Evaluating LLM Agent Collusion in Double Auctions.* arXiv:2507.01413.
- **Repo:** https://github.com/andyjliu/llm-agent-collusion
- **License:** **None present** (GitHub license API returns 404). Treated as
  "all rights reserved".
- **Verified on:** 2026-10-19.

## What it is

A continuous double auction (CDA) market populated by LLM agents (OpenAI / Anthropic
/ OpenRouter models). CLI flags expose the levers relevant to us:

- `--seller_comms_enabled` / `--buyer_comms_enabled` — communication channel.
- `--oversight_enabled` — a seller-oversight mechanism.
- `--boss_pressure` — pressure to keep prices high (a collusion incentive).
- `--hide_num_rounds` — removes the horizon signal.

Code structure: `src/continuous_double_auction/{market,evaluation,experiments,
prompt_templates,resources}` with a unified `ModelWrapper`, plus a local `data/` and
`experiments/` directory. Repo is a **single commit** with `assets/`, `data/`,
`experiments/`, `src/`.

## Relevance to this project

- A **second market environment** (double auction vs. our Bertrand market) and the
  reference for **Milestone 6** (generalize the monitor interface to a double
  auction).
- Its flag set maps cleanly onto our conditions and monitor context: communication →
  `communication` condition; oversight → monitor-enabled; boss pressure → collusion
  incentive (`hidden_objective`).

## What we reuse vs. avoid

- **Idea reuse only.** Because there is **no license**, we must not copy code or
  data. We reimplement concepts (double-auction mechanics, oversight design) from the
  paper.
- If Milestone 6 needs this harness directly, obtain explicit permission from the
  authors first.

## Risks / notes

- The absence of a license is a hard blocker for vendoring; track as an open item.
- Uses paid API keys (OpenAI/Anthropic/OpenRouter); cost-bearing, unlike our scripted
  controls.
