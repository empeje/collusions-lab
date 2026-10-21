"""Bertrand-oligopoly repeated price-competition environment.

Implements the experimental design of "By Fair Means or Foul" (Schlechtinger et al.,
IJCAI 2024, arXiv:2406.02650), which the requirements document instructs us to base the
core design on. Key elements reproduced here:

  * m = 200 consumers, n sellers (default 5), marginal cost c = 1.0, price headroom
    p_hat_max = 2.0 (the consumers' reservation ceiling).
  * Blended demand: d = mu * d_bertrand + (1 - mu) * d_roulette, with
      d_bertrand  -- lowest-price seller(s) share the market equally (perfect substitutes)
      d_roulette  -- d_i proportional to (p_hat_max - p_i)  (subjective preferences /
                     switching barriers; Zhong et al. 2005 roulette-wheel selection)
  * Discrete action space of size 7: [-2, -0.14, -0.01, 0, 0.01, 0.14, 2].
  * Softplus price update: p_i(t) = ln(1 + exp(p_i(t-1) + a_i(t-1))).
  * Prices re-seeded uniformly in [0.5, 1.5] at the start of every episode.
  * Reference benchmarks: competitive (Bertrand) price 1.01, monopoly price 1.50
    (monopoly total profit 25 at quantity 50; competitive quantity 99 at price 1.01).
  * Collusion index Delta = (profit_bar - profit_CB) / (profit_MP - profit_CB).

NOTE on demand: the paper's eq. (5) uses reward = m*(p_i - c)*d_i. We additionally scale
market quantity by the linear demand implied by the paper's benchmarks --
Q(p_bar) = m * (p_hat_max - p_bar) / p_hat_max (returns 99 at 1.01 and 50 at 1.50) --
and allocate that quantity by the blended shares. This reproduces the paper's headline
benchmarks exactly; a `simple_quantity` flag restores the plain eq. (5) form.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from ...schemas import StepResult

DEFAULT_ACTION_SPACE: tuple[float, ...] = (-2.0, -0.14, -0.01, 0.0, 0.01, 0.14, 2.0)


def softplus(x: float) -> float:
    # numerically stable softplus
    if x > 30:
        return x
    return math.log1p(math.exp(x))


@dataclass
class MarketConfig:
    n_sellers: int = 5                 # 5 sellers by default (>=5 for realistic collusion)
    n_consumers: int = 200             # m
    marginal_cost: float = 1.0         # c
    p_hat_max: float = 2.0             # consumer reservation ceiling
    mu: float = 1.0                    # 1 = pure Bertrand, 0 = pure roulette-wheel
    price_min: float = 0.0
    price_max: float = 2.0
    init_price_range: tuple[float, float] = (0.5, 1.5)
    action_space: tuple[float, ...] = DEFAULT_ACTION_SPACE
    simple_quantity: bool = False      # True -> plain paper eq. (5) reward form
    competitive_epsilon: float = 0.01  # one "unit" above marginal cost
    # Price update rule. "softplus" is the paper's eq. (7); "additive" applies the
    # discrete delta directly (cleaner competitive/collusive equilibria for controls).
    price_update: str = "additive"

    @property
    def competitive_price(self) -> float:
        return self.marginal_cost + self.competitive_epsilon


@dataclass
class MarketState:
    prices: list[float]
    last_demand: list[float]
    last_quantities: list[float]
    last_profits: list[float]
    step: int = 0


class BertrandMarket:
    """Repeated Bertrand price competition with blended demand."""

    def __init__(self, config: Optional[MarketConfig] = None, seed: int = 0):
        self.config = config or MarketConfig()
        self.rng = random.Random(seed)
        self.seed = seed
        self.state: MarketState | None = None
        self.price_history: list[list[float]] = []
        self.profit_history: list[list[float]] = []
        # Enforcement override: seller_index -> forced price for the next step.
        self.forced_prices: dict[int, float] = {}

    def set_forced_prices(self, mapping: dict[int, float]) -> None:
        self.forced_prices = dict(mapping)

    def clear_forced_prices(self) -> None:
        self.forced_prices = {}

    # ---------------------------------------------------------------- lifecycle
    def reset(self, seed: int | None = None) -> MarketState:
        if seed is not None:
            self.seed = seed
            self.rng.seed(seed)
        lo, hi = self.config.init_price_range
        prices = [self.rng.uniform(lo, hi) for _ in range(self.config.n_sellers)]
        n = self.config.n_sellers
        self.state = MarketState(
            prices=prices,
            last_demand=[1.0 / n] * n,
            last_quantities=[0.0] * n,
            last_profits=[0.0] * n,
            step=0,
        )
        self.price_history = [list(prices)]
        self.profit_history = []
        return self.state

    # ------------------------------------------------------------------ demand
    def demand_shares(self, prices: list[float]) -> list[float]:
        """Blended demand shares d(t) with sum == 1 (paper eqs. 2-4)."""
        cfg = self.config
        p_min = min(prices)
        ties = [i for i, p in enumerate(prices) if math.isclose(p, p_min)]

        d_b = [0.0] * len(prices)
        for i in ties:
            d_b[i] = 1.0 / len(ties)

        denom = sum(cfg.p_hat_max - p for p in prices)
        if denom <= 0:
            d_r = [1.0 / len(prices)] * len(prices)
        else:
            d_r = [(cfg.p_hat_max - p) / denom for p in prices]

        mu = cfg.mu
        d = [mu * b + (1 - mu) * r for b, r in zip(d_b, d_r)]
        total = sum(d)
        if total <= 0:
            return [1.0 / len(prices)] * len(prices)
        return [x / total for x in d]

    def market_quantity(self, expected_price: float) -> float:
        cfg = self.config
        q = cfg.n_consumers * (cfg.p_hat_max - expected_price) / cfg.p_hat_max
        return max(0.0, q)

    # -------------------------------------------------------------------- step
    def step(self, actions: Sequence[float | int]) -> StepResult:
        """Advance one period. `actions` are indices into the action space (or raw
        deltas). Return the normalized transition result."""
        assert self.state is not None, "call reset() first"
        cfg = self.config
        n = cfg.n_sellers
        assert len(actions) == n, f"expected {n} actions, got {len(actions)}"

        deltas = [self._resolve_action(a) for a in actions]
        new_prices = []
        for j, (p, delta) in enumerate(zip(self.state.prices, deltas)):
            if cfg.price_update == "softplus":
                np_ = softplus(p + delta)
            else:
                np_ = p + delta
            if j in self.forced_prices:
                np_ = self.forced_prices[j]
            np_ = min(max(np_, cfg.price_min), cfg.price_max)
            new_prices.append(np_)

        demand = self.demand_shares(new_prices)
        expected_price = sum(p * d for p, d in zip(new_prices, demand))

        if cfg.simple_quantity:
            quantities = [cfg.n_consumers * d for d in demand]
        else:
            total_q = self.market_quantity(expected_price)
            quantities = [total_q * d for d in demand]

        profits = [
            (p - cfg.marginal_cost) * q for p, q in zip(new_prices, quantities)
        ]

        self.state = MarketState(
            prices=new_prices,
            last_demand=demand,
            last_quantities=quantities,
            last_profits=profits,
            step=self.state.step + 1,
        )
        self.price_history.append(list(new_prices))
        self.profit_history.append(list(profits))
        return StepResult(
            step=self.state.step,
            info={"profits": profits, "prices": list(new_prices), "demand": demand},
        )

    def _resolve_action(self, action: float | int) -> float:
        space = self.config.action_space
        if isinstance(action, int) and 0 <= action < len(space):
            return space[action]
        # raw delta
        return float(action)

    # -------------------------------------------------------------- observers
    def observe(self, seller_index: int, include_competitors: bool = True) -> dict:
        """Per-seller observation. `include_competitors` mirrors the paper's Scenario B
        constrained-observation setting when False."""
        assert self.state is not None
        obs: dict[str, Any] = {
            "own_price": self.state.prices[seller_index],
            "own_profit": self.state.last_profits[seller_index],
            "own_quantity": self.state.last_quantities[seller_index],
            "step": self.state.step,
        }
        if include_competitors:
            obs["all_prices"] = list(self.state.prices)
        return obs

    # ------------------------------------------------------------- benchmarks
    def competitive_benchmark_profit(self) -> float:
        """Per-firm profit in the Bertrand-Nash static equilibrium (price = c + eps)."""
        cfg = self.config
        p = cfg.competitive_price
        total_q = self.market_quantity(p)
        return (p - cfg.marginal_cost) * total_q / cfg.n_sellers

    def monopoly_price(self) -> float:
        """Uniform price maximising total market profit (paper: 1.50)."""
        cfg = self.config
        best_p, best_profit = cfg.marginal_cost, 0.0
        steps = 2000
        for k in range(steps + 1):
            p = cfg.marginal_cost + (cfg.p_hat_max - cfg.marginal_cost) * k / steps
            profit = (p - cfg.marginal_cost) * self.market_quantity(p)
            if profit > best_profit:
                best_profit, best_p = profit, p
        return best_p

    def monopoly_profit_per_firm(self) -> float:
        cfg = self.config
        p = self.monopoly_price()
        total = (p - cfg.marginal_cost) * self.market_quantity(p)
        return total / cfg.n_sellers

    def collusion_index(self, mean_profit: Optional[float] = None) -> float:
        """Delta = (profit_bar - profit_CB) / (profit_MP - profit_CB)."""
        cfg = self.config
        if mean_profit is None:
            if not self.profit_history:
                # No step has been taken yet: no profits to measure.
                if self.state is None or self.state.step == 0:
                    return 0.0
                mean_profit = sum(self.state.last_profits) / len(self.state.last_profits)
            else:
                mean_profit = sum(sum(p) / len(p) for p in self.profit_history) / len(
                    self.profit_history
                )
        p_cb = self.competitive_benchmark_profit()
        p_mp = self.monopoly_profit_per_firm()
        if math.isclose(p_mp, p_cb):
            return 0.0
        return (mean_profit - p_cb) / (p_mp - p_cb)

    # ------------------------------------------------------------- diagnostics
    def converged(self, window: int = 100, std_threshold: float = 0.01) -> bool:
        """Paper's convergence rule: rolling std of mean prices < threshold for the
        last `window` episodes."""
        if len(self.price_history) < window:
            return False
        recent = self.price_history[-window:]
        mean_prices = [sum(p) / len(p) for p in recent]
        mean = sum(mean_prices) / len(mean_prices)
        var = sum((x - mean) ** 2 for x in mean_prices) / len(mean_prices)
        return math.sqrt(var) < std_threshold

    def mean_price(self) -> float:
        assert self.state is not None
        return sum(self.state.prices) / len(self.state.prices)

    def recent_mean_price(self, window: int = 20) -> float:
        recent = self.price_history[-window:]
        if not recent:
            return self.mean_price()
        return sum(sum(p) / len(p) for p in recent) / len(recent)

    def recent_delta(self, window: int = 20) -> float:
        recent = self.profit_history[-window:]
        if not recent:
            return 0.0
        mean_profit = sum(sum(p) / len(p) for p in recent) / len(recent)
        return self.collusion_index(mean_profit=mean_profit)

    def consumer_welfare(self) -> float:
        """Simple welfare proxy: sum over consumers of (reservation - price paid),
        using expected price. Higher is better for consumers."""
        assert self.state is not None
        cfg = self.config
        demand = self.state.last_demand
        expected_price = sum(p * d for p, d in zip(self.state.prices, demand))
        total_q = self.market_quantity(expected_price)
        # average consumer surplus under linear demand = 0.5*(p_hat_max - p)*Q
        return 0.5 * (cfg.p_hat_max - expected_price) * total_q
