import pytest

from collusions_lab.llm.providers import (
    AnthropicProvider,
    HFInferenceProvider,
    MockProvider,
    TransformersProvider,
    get_provider,
)
from collusions_lab.agents.core import AgentAction, LLMAgent, parse_market_action, parse_swe_action
from collusions_lab.agents.prompts import build_market_prompt
from collusions_lab.runner import RunConfig, _build_swe_agents
from collusions_lab.schemas import (
    AgentConfig,
    AgentRole,
    EpisodeCondition,
    Scenario,
)


def test_mock_provider_is_deterministic():
    p = MockProvider()
    r = p.complete("sys", [{"role": "user", "content": "hello world"}])
    assert "hello world" in r.text


def test_registry_constructs_local_and_hf_names():
    assert isinstance(get_provider("local", "some/model"), TransformersProvider)
    # Unknown names fall back to mock.
    assert isinstance(get_provider("nope"), MockProvider)


def test_transformers_provider_uses_injected_generator():
    seen = {}

    def gen(model, system, messages, temperature, max_tokens):
        seen["model"] = model
        return '{"action": 3}'

    p = TransformersProvider(model="some/model", generator=gen)
    r = p.complete("sys", [{"role": "user", "content": "x"}])
    assert r.text == '{"action": 3}'
    assert seen["model"] == "some/model"


def test_hf_inference_requires_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        HFInferenceProvider()


def test_get_provider_forwards_generator_option():
    p = get_provider("local", "some/model", generator=lambda *a: "ok")
    assert isinstance(p, TransformersProvider)


def test_llm_agent_records_dynamic_prompt_fingerprint():
    agent = LLMAgent(
        AgentConfig("seller", AgentRole.SELLER, provider="mock"),
        MockProvider(),
        lambda config, observation: ("system", [{"role": "user", "content": "task"}]),
        lambda text: AgentAction("action"),
    )

    action = agent.act({})

    assert len(action.payload["_llm"]["prompt_sha256"]) == 64
    assert action.payload["_llm"]["model"]


def test_market_communication_prompt_and_parser_support_messages():
    config = AgentConfig("seller", AgentRole.SELLER, provider="mock")
    _, messages = build_market_prompt(
        config,
        0,
        2,
        {"step": 1, "own_price": 1.1, "own_profit": 1.0, "team_messages": ["hold price"]},
        EpisodeCondition.COMMUNICATION,
    )
    assert "hold price" in messages[0]["content"]
    assert '"message"' in messages[0]["content"]
    assert parse_market_action('{"action": 4, "message": "hold price"}').payload["message"] == "hold price"


def test_swe_communication_prompt_contains_prior_messages_and_repo_context():
    config = AgentConfig("planner", AgentRole.PLANNER, provider="mock")
    run = RunConfig(
        Scenario.SOFTWARE_ENGINEERING,
        EpisodeCondition.COMMUNICATION,
        [config],
    )
    agent = _build_swe_agents(run)[0]
    _, messages = agent._build(
        config,
        {"files": {"module.py": "safe source"}, "team_messages": ["review this diff"]},
    )
    assert "safe source" in messages[0]["content"]
    assert "review this diff" in messages[0]["content"]


def test_anthropic_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY2", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        AnthropicProvider()


def test_anthropic_prefers_key2_and_sets_cache_control(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY2", "k2")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k1")
    p = get_provider("anthropic")
    assert isinstance(p, AnthropicProvider) and p.api_key == "k2"
    payload = p._build_payload(
        "sys",
        [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"},
         {"role": "user", "content": "c"}],
        0.0,
        10,
    )
    assert payload["system"][0]["cache_control"] == {"type": "ephemeral"}
    flags = ["cache_control" in m["content"][0] for m in payload["messages"]]
    assert flags == [False, False, True]


def test_anthropic_parses_usage_and_can_disable_cache(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY2", "k2")
    seen = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": "hi"}],
                "usage": {"input_tokens": 5, "output_tokens": 2,
                          "cache_creation_input_tokens": 100,
                          "cache_read_input_tokens": 50},
            }

    def fake_post(url, headers, json, timeout):
        seen["headers"], seen["json"] = headers, json
        return FakeResp()

    monkeypatch.setattr("collusions_lab.llm.providers.requests.post", fake_post)
    r = AnthropicProvider(cache=False).complete("s", [{"role": "user", "content": "x"}])
    assert r.text == "hi"
    assert (r.cache_creation_tokens, r.cache_read_tokens, r.prompt_tokens) == (100, 50, 155)
    assert seen["headers"]["x-api-key"] == "k2"
    assert "cache_control" not in seen["json"]["system"][0]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("**Verdict: APPROVE**\nLooks fine.", "APPROVE"),
        ("REJECT\n\nI did not approve this change.", "REJECT"),
        ("Verdict: REJECT. I cannot approve it.", "REJECT"),
        ("No clear statement here.", "REJECT"),
    ],
)
def test_review_verdict_uses_stated_verdict(text, expected):
    assert parse_swe_action(AgentRole.REVIEWER, text).payload["verdict"] == expected


def test_market_episode_writes_complete_trace(tmp_path):
    import json

    from collusions_lab.runner import run_episode

    agents = [AgentConfig(f"seller_{i}", AgentRole.SELLER, provider="mock") for i in range(5)]
    run = RunConfig(
        Scenario.MARKETS,
        EpisodeCondition.COMMUNICATION,
        agents,
        seed=3,
        monitor_enabled=True,
        market_steps=11,
    )
    run_episode(run, tmp_path)
    trace = json.loads(next(tmp_path.glob("*/trace.json")).read_text())
    assert trace["schema"] == "collusions-lab/trace@1"
    assert len(trace["steps"]) == 11
    step = trace["steps"][0]
    assert len(step["sellers"]) == 5 and len(step["prices_after"]) == 5
    assert step["sellers"][0]["prompt"]["system"] and step["sellers"][0]["response"]
    assert any(s["monitor"] for s in trace["steps"])
