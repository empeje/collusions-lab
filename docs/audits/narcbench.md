# Audit: NARCBench

- **Paper:** Rose, Cullen, Abdelnabi, Torr, Kaplowitz, Schroeder de Witt.
  *Detecting Multi-Agent Collusion Through Multi-Agent Interpretability.*
  arXiv:2604.01151 (2026).
- **Repo:** https://github.com/aaronrose227/narcbench
- **Data:** https://huggingface.co/datasets/aaronrose227/narcbench
- **License:** MIT (declared in README; no separate LICENSE file via API).
- **Verified on:** 2026-10-19.

## What it is

A three-tier benchmark for detecting multi-agent collusion under environment
distribution shift. A **linear deception probe** is trained on committee-deliberation
**activations** (Core) and evaluated zero-shot on structurally novel scenarios
(Transfer) and steganographic signalling (Stego). Five probing methods are compared
(LR, LAT/PCA, difference-of-means, MLP, multi-head). Base model: **Qwen3-32B-AWQ**,
with a **Qwen3-32B activation oracle** LoRA for natural-language queries over
activations.

## Relevance to this project

- Demonstrates that collusion is detectable from **internal activations**, not just
  transcript text — a complementary detection modality to our behavioral signals.
- Its "Core → Transfer/Stego" design is the model for our **held-out task families**
  and **shared-context vs. communication** controls.
- The Verdict Decisions sub-experiment (emergent, non-instructed 2-agent collusion)
  parallels our tacit-coordination label.

## Hardware / access decision

The oracle and activation extraction require **~40GB+ VRAM** (Qwen3-32B). This
project's environment is a single **8GB laptop GPU**, so we **cannot** run the
extraction pipeline locally. Decision:

1. Use the **pre-extracted activation data** on HuggingFace for any probe work
   (no local 32B inference).
2. Treat NARCBench as **inspiration and a cited baseline**, not a vendored
   dependency. Its probe layer is a candidate future detection signal behind our
   `MonitorSignals` interface.

## Risks / notes

- Activation probing is a **different threat model** (white-box model access); our
  monitor is model-free and black-box by design. Keep the interfaces separate.
- MIT license; if any code were vendored, preserve the notice. Current status: not
  vendored.
