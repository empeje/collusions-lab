---
title: Collusions Lab — Static Demo
emoji: 🕵️
colorFrom: indigo
colorTo: red
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: Precomputed demo of the trusted-monitor collusion benchmark
---

# Collusions Lab — Static Demo

A **free, read-only** explorer for the precomputed benchmark episodes (markets +
software-engineering scenarios). No server, no GPU, no PRO subscription.

- Filters: scenario, condition, seed, monitor on/off
- Per-episode: ground-truth label, harm metrics, monitor decisions, and (for
  markets) the mean-price trajectory
- Data is baked into the page at build time — regenerate with
  `python scripts/build_static_site.py` after re-running experiments

For a **live interactive** run (LLM-driven sellers, ZeroGPU), the Gradio Space
requires an HF PRO subscription — see `space/`. Source and full experiment code:
[GitHub](https://github.com/munip/collusions-lab) ·
[Runs dataset](https://huggingface.co/datasets/munipu/collusions-lab-runs)
