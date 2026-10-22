"""End-to-end episode trace.

One self-contained JSON file per episode (``trace.json``) holding everything needed to
replay a market run step by step: configuration, the exact prompt each seller saw, its
raw reply, the parsed action, resulting prices and profits, messages, monitor decisions
and enforcement. The browser visualiser imports this file, and human games export the
same format, so human and AI episodes can be replayed side by side.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .schemas import jsonable

TRACE_SCHEMA = "collusions-lab/trace@1"


class MarketTraceBuilder:
    def __init__(self, run, market, agents, episode_id: str):
        cfg = market.config
        self.data: dict[str, Any] = {
            "schema": TRACE_SCHEMA,
            "episode_id": episode_id,
            "scenario": "markets",
            "condition": run.condition.value,
            "seed": run.seed,
            "monitor_enabled": run.monitor_enabled,
            "config": {
                "n_sellers": cfg.n_sellers,
                "n_consumers": cfg.n_consumers,
                "marginal_cost": cfg.marginal_cost,
                "price_min": cfg.price_min,
                "price_max": cfg.price_max,
                "price_update": cfg.price_update,
                "action_space": list(cfg.action_space),
                "competitive_price": cfg.competitive_price,
                "monopoly_price": market.monopoly_price(),
                "steps": run.market_steps,
                "monitor_interval": 10,
            },
            "agents": [
                {
                    "id": a.agent_id,
                    "model": a.config.model,
                    "provider": a.config.provider,
                    "hidden_objective": a.config.hidden_objective,
                    "human": False,
                }
                for a in agents
            ],
            "initial_prices": [round(p, 6) for p in market.state.prices],
            "steps": [],
            "final_monitor": [],
            "summary": {},
        }
        self._current: Optional[dict[str, Any]] = None

    def begin_step(self, step: int, prices_before: list[float]) -> None:
        self._current = {
            "t": step,
            "prices_before": [round(p, 6) for p in prices_before],
            "sellers": [],
            "monitor": [],
            "forced": None,
        }

    def seller(
        self,
        agent_id: str,
        quarantined: bool,
        action: int,
        reason: str = "",
        message: str = "",
        exchange: Optional[dict] = None,
    ) -> None:
        assert self._current is not None
        self._current["sellers"].append(
            {
                "agent": agent_id,
                "quarantined": quarantined,
                "action": action,
                "reason": reason,
                "message": message,
                "prompt": exchange.get("prompt") if exchange else None,
                "response": exchange.get("response") if exchange else None,
            }
        )

    def monitor(self, decisions: list, effect: Optional[dict] = None) -> None:
        assert self._current is not None
        self._current["monitor"] = [jsonable(d) for d in decisions]
        if effect and effect.get("forced_price") is not None:
            self._current["forced"] = {
                "price": effect["forced_price"],
                "agents": list(effect.get("constrained_agents", [])),
            }

    def end_step(self, market) -> None:
        assert self._current is not None and market.state is not None
        s = market.state
        self._current.update(
            prices_after=[round(p, 6) for p in s.prices],
            quantities=[round(q, 4) for q in s.last_quantities],
            profits=[round(p, 4) for p in s.last_profits],
            demand=[round(d, 4) for d in s.last_demand],
            mean_price=round(sum(s.prices) / len(s.prices), 4),
            delta_recent=round(market.recent_delta(), 4),
        )
        self.data["steps"].append(self._current)
        self._current = None

    def final_monitor(self, decisions: list) -> None:
        self.data["final_monitor"] = [jsonable(d) for d in decisions]

    def finish(self, result: dict, run_dir: Path) -> Path:
        self.data["summary"] = {
            k: result.get(k)
            for k in ("attempted_harm", "harmful_outcome", "harm_prevented")
        }
        self.data["summary"]["metrics"] = {
            k: v
            for k, v in result["metrics"].items()
            if k != "mean_price_history"
        }
        path = Path(run_dir) / "trace.json"
        path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        return path
