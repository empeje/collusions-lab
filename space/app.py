"""Gradio demo for Collusions Lab (Hugging Face Space).

Runs the deterministic scripted sweeps on CPU by default. Optionally drives the
market sellers with a local open-weight model (through ``spaces.GPU`` on ZeroGPU when
available) or the HF Inference API (HF_TOKEN secret).

The demo is read-only with respect to the environment: it never mutates a shared
resource, and the monitor only ever issues the actions in ``MonitorAction``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import gradio as gr
import pandas as pd

from collusions_lab.llm import get_provider
from collusions_lab.runner import RunConfig, run_episode
from collusions_lab.schemas import AgentConfig, AgentRole, EpisodeCondition, Scenario

# ---------------------------------------------------------------------------------
# Optional GPU (ZeroGPU). Degrades gracefully to plain CPU calls off-Spaces.
# ---------------------------------------------------------------------------------
try:  # pragma: no cover - only true on HF Spaces with ZeroGPU
    import spaces

    def gpu(*args, **kwargs):
        if args and callable(args[0]) and not kwargs:
            return spaces.GPU(args[0])
        return spaces.GPU(*args, **kwargs)

    HAS_GPU = True
except Exception:  # pragma: no cover
    def gpu(*args, **kwargs):
        if args and callable(args[0]) and not kwargs:
            return args[0]

        def deco(fn):
            return fn

        return deco

    HAS_GPU = False

_PIPES: dict = {}


@gpu(duration=120)
def _local_generate(model, system, messages, temperature, max_tokens):
    """Generate with a local open-weight model. On ZeroGPU this runs on an A100."""
    from transformers import pipeline  # pragma: no cover - heavy import

    if model not in _PIPES:  # pragma: no cover
        _PIPES[model] = pipeline("text-generation", model=model)
    pipe = _PIPES[model]
    chat = [{"role": "system", "content": system}, *messages]
    out = pipe(
        chat,
        max_new_tokens=min(max_tokens, 256),
        do_sample=temperature > 0,
        temperature=max(temperature, 1e-6),
    )
    generated = out[0]["generated_text"]
    return generated[-1]["content"] if isinstance(generated, list) else str(generated)


CONDITIONS = [c.value for c in EpisodeCondition]
PROVIDERS = ["scripted", "mock", "hf", "local"]
SWE_ROLES = [
    AgentRole.PLANNER,
    AgentRole.IMPLEMENTER_A,
    AgentRole.IMPLEMENTER_B,
    AgentRole.TESTER,
    AgentRole.REVIEWER,
    AgentRole.EXECUTOR,
]
SWE_DEVIANT_ROLES = {AgentRole.IMPLEMENTER_B, AgentRole.TESTER, AgentRole.REVIEWER}


def _is_deviant_condition(condition: str) -> bool:
    return condition in ("known_collusion", "adversarial_monitor")


def _agents(scenario, condition, provider, model, n_sellers):
    deviant = _is_deviant_condition(condition)
    if scenario == Scenario.MARKETS.value:
        return [
            AgentConfig(
                agent_id=f"seller_{i}",
                role=AgentRole.SELLER,
                provider=provider,
                model=model,
                hidden_objective="collude" if deviant else None,
            )
            for i in range(n_sellers)
        ]
    return [
        AgentConfig(
            agent_id=r.value,
            role=r,
            provider=provider,
            model=model,
            hidden_objective="collude" if (deviant and r in SWE_DEVIANT_ROLES) else None,
        )
        for r in SWE_ROLES
    ]


def _provider_factory(provider_name, model):
    if provider_name == "local":
        return get_provider("local", model, generator=_local_generate)
    return get_provider(provider_name, model)


def run_demo(scenario, condition, monitor_enabled, seed, n_sellers, market_steps, provider, model):
    """Pure function: run one episode and return display-ready payloads."""
    scenario = Scenario(scenario)
    out_dir = Path(tempfile.mkdtemp(prefix="collusions_demo_"))
    agents = _agents(scenario.value, condition, provider, model, int(n_sellers))
    run = RunConfig(
        scenario=scenario,
        condition=EpisodeCondition(condition),
        agents=agents,
        seed=int(seed),
        monitor_enabled=bool(monitor_enabled),
        n_sellers=int(n_sellers),
        market_steps=int(market_steps),
        provider_factory=_provider_factory if provider in ("local", "hf") else None,
    )
    try:
        result = run_episode(run, out_dir)
    except Exception as exc:  # surface provider/config errors in the UI
        return f"**Error:** {type(exc).__name__}: {exc}", None, None, None

    label = result["ground_truth"]["label"]
    summary = (
        f"### Result\n"
        f"- **scenario:** `{result['scenario']}`  |  **condition:** `{result['condition']}`\n"
        f"- **ground-truth label:** `{label}`\n"
        f"- **attempted harm:** `{result.get('attempted_harm', result.get('harmful_change_present'))}`\n"
        f"- **harmful outcome:** `{result['harmful_outcome']}`  |  "
        f"**harm prevented:** `{result['harm_prevented']}`\n"
        f"- **audit trail:** `{result['episode_id']}/authoritative.jsonl`\n"
    )

    metrics = {k: v for k, v in result["metrics"].items() if k != "mean_price_history"}
    metrics_df = pd.DataFrame(
        {"metric": list(metrics.keys()), "value": [str(v) for v in metrics.values()]}
    )

    decisions = result.get("decisions", [])
    decisions_df = pd.DataFrame(
        [
            {
                "step": d.get("step"),
                "action": d.get("action"),
                "risk": d.get("risk_score"),
                "reasons": " | ".join(d.get("reasons", [])),
            }
            for d in decisions
        ]
        or [{"step": None, "action": "(none recorded)", "risk": None, "reasons": ""}]
    )

    price_df = None
    history = result["metrics"].get("mean_price_history")
    if history:
        price_df = pd.DataFrame({"step": range(len(history)), "mean_price": history})

    return summary, metrics_df, decisions_df, price_df


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Collusions Lab") as demo:
        gr.Markdown(
            "# Collusions Lab\n"
            "Intervention benchmark: does a **trusted monitor** catch harmful multi-agent "
            "coordination, block the harm, and preserve legitimate work?\n\n"
            "Deterministic scripted sweeps run on CPU. Select `provider=hf` (needs `HF_TOKEN` secret) "
            "or `provider=local` (ZeroGPU) to drive sellers with an LLM."
        )
        with gr.Row():
            with gr.Column():
                scenario = gr.Dropdown(
                    [s.value for s in Scenario], value=Scenario.MARKETS.value, label="Scenario"
                )
                condition = gr.Dropdown(CONDITIONS, value="known_collusion", label="Condition")
                monitor_enabled = gr.Checkbox(value=True, label="Monitor enabled")
                seed = gr.Slider(0, 20, value=1, step=1, label="Seed")
                n_sellers = gr.Slider(2, 8, value=5, step=1, label="Sellers (markets)")
                market_steps = gr.Slider(20, 200, value=120, step=10, label="Market steps")
                provider = gr.Dropdown(PROVIDERS, value="scripted", label="Provider")
                model = gr.Textbox(
                    value="Qwen/Qwen2.5-0.5B-Instruct", label="Model (hf/local only)"
                )
            with gr.Column():
                summary = gr.Markdown()
                metrics_df = gr.Dataframe(label="Metrics")
                decisions_df = gr.Dataframe(label="Monitor decisions")
                price_plot = gr.LinePlot(
                    x="step", y="mean_price", label="Mean market price", height=280
                )
        run_btn = gr.Button("Run episode", variant="primary")
        run_btn.click(
            run_demo,
            inputs=[scenario, condition, monitor_enabled, seed, n_sellers, market_steps, provider, model],
            outputs=[summary, metrics_df, decisions_df, price_plot],
        )
        gr.Markdown(
            "Ground truth is evaluation-only and never shown to the monitor. "
            "See the repo README and docs for the metric definitions."
        )
    return demo


if __name__ == "__main__":
    build_demo().queue().launch()
