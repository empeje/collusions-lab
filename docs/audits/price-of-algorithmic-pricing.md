# Audit: *By Fair Means or Foul* / PriceOfAlgorithmicPricing

- **Paper:** Schlechtinger, Kosack, Krause, Paulheim. *By Fair Means or Foul:
  Quantifying Collusion in a Market Simulation with Deep Reinforcement Learning.*
  IJCAI 2024 (pp. 485–493); arXiv:2406.02650 (CC BY 4.0).
- **Repo:** https://github.com/mschlechtinger/PriceOfAlgorithmicPricing
- **License:** MIT (verified via GitHub license API; © 2022 mschlechtinger).
- **Verified on:** 2026-10-19.

## What it is

A repeated Bertrand-oligopoly market simulation where deep RL agents (PPO/DQN)
learn pricing strategies. The paper's headline result: RL agents converge to a
collusive state with supra-competitive prices **without any inter-agent
communication**. It introduces a blended-demand framework and a collusion index to
quantify how far profits sit between the competitive and monopoly benchmarks. It also
studies constrained observation (agents cannot see competitors' prices).

## Relevance to this project

This is the basis for **Scenario A**. We reproduce the paper's core structure:

| Paper element | This project |
|---|---|
| Blended demand `d = mu·d_bertrand + (1-mu)·d_roulette` | `BertrandMarket.demand_shares` |
| m = 200 consumers, c = 1.0, p_hat_max = 2.0 | `MarketConfig` defaults |
| 7-action space `[-2,-0.14,-0.01,0,0.01,0.14,2]` | `DEFAULT_ACTION_SPACE` |
| Reference prices 1.01 (competitive) / 1.50 (monopoly) | `competitive_price`, `monopoly_price()` (verified by test) |
| Collusion index Δ | `BertrandMarket.collusion_index` |
| Constrained-observation scenario | `include_competitor_prices=False` |

## What we reuse vs. adapt

- **Reuse (license-permitted, MIT):** demand formulation, action-space shape,
  benchmark constants, collusion-index definition.
- **Adapt / document:** the paper's prices are learned by RL; our PoC uses scripted
  and LLM agents, so we add an explicit enforcement override (`set_forced_prices`).
- **Documented deviation:** the paper's softplus price update, used verbatim, drifts
  upward even at action `0` and gives degenerate deterministic dynamics. We default to
  an additive update and keep `softplus` available behind a config flag
  (see `docs/architecture.md`, "Market model notes"). Flagged for reviewer sign-off.

## Risks / notes

- MIT requires preserving the copyright/license notice in copies of substantial
  portions — relevant if code is copied rather than reimplemented. Current
  implementation is a clean reimplementation from the paper, not copied source.
- The paper has no defensive/monitor component; the trusted monitor and all
  intervention logic here are new.
