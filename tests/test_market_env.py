import math

from collusions_lab.environments.markets.bertrand import BertrandMarket, MarketConfig


def _firm(n=5, mu=1.0):
    return BertrandMarket(MarketConfig(n_sellers=n, mu=mu), seed=1)


def test_paper_benchmarks():
    m = _firm()
    assert abs(m.monopoly_price() - 1.5) < 0.01
    assert abs(m.config.competitive_price - 1.01) < 1e-9


def test_demand_shares_are_a_distribution():
    m = _firm(mu=0.5)
    shares = m.demand_shares([1.2, 1.1, 1.4, 1.3, 1.5])
    assert abs(sum(shares) - 1.0) < 1e-9
    assert all(s >= 0 for s in shares)


def test_forced_competitive_prices_give_near_zero_collusion():
    m = _firm()
    m.reset()
    m.set_forced_prices({i: m.config.competitive_price for i in range(5)})
    for _ in range(20):
        m.step([3] * 5)
    assert abs(m.mean_price() - 1.01) < 1e-6
    assert m.collusion_index() < 0.05


def test_forced_monopoly_prices_give_high_collusion():
    m = _firm()
    m.reset()
    m.set_forced_prices({i: 1.5 for i in range(5)})
    for _ in range(20):
        m.step([3] * 5)
    assert abs(m.mean_price() - 1.5) < 1e-6
    assert m.recent_delta() > 0.9


def test_forced_price_overrides_action():
    m = _firm()
    m.reset()
    m.set_forced_prices({0: 1.5})
    m.step([6, 3, 3, 3, 3])  # seller 0 forced to 1.5 despite the +2 action
    assert abs(m.state.prices[0] - 1.5) < 1e-9


def test_no_profit_history_index_is_zero():
    m = _firm()
    m.reset()
    assert m.collusion_index() == 0.0


def test_softplus_update_matches_equation():
    cfg = MarketConfig(price_update="softplus")
    m = BertrandMarket(cfg, seed=2)
    m.reset()
    p0 = m.state.prices[0]
    m.step([3] * 5)  # delta 0
    assert abs(m.state.prices[0] - math.log1p(math.exp(p0))) < 1e-9
