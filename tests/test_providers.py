import pytest

from collusions_lab.llm.providers import (
    HFInferenceProvider,
    MockProvider,
    TransformersProvider,
    get_provider,
)
from collusions_lab.agents.core import AgentAction, LLMAgent, parse_market_action
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
