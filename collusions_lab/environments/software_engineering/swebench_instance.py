"""SWE-bench instance loader for Milestone 6B.

A *SWE-bench instance* is a reproducible starting point for a repository task:

    instance_id, repo, base_commit, problem_statement, patch, test_patch,
    FAIL_TO_PASS, PASS_TO_PASS

The published datasets live on Hugging Face (``SWE-bench/SWE-bench_Verified``,
``SWE-bench/SWE-bench_Lite``); the schema is documented at
<https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified>. Milestone 6B loads an
instance from a **local JSON file** with the same schema so runs stay offline and
deterministic; the same loader accepts an instance fetched from HF when a token/network
is available (``load_instance_from_hf``).

``FAIL_TO_PASS`` / ``PASS_TO_PASS`` are declared as JSON arrays in the dataset, but the
HF server sometimes returns them as Python-repr strings (single quotes). The loader
normalizes both representations.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _as_list(value: Any) -> list[str]:
    """Normalize a FAIL_TO_PASS / PASS_TO_PASS field.

    Accepts an already-parsed list, a JSON string, or a Python-repr string. The dataset
    ships JSON arrays; some HF mirrors/endpoints render them as Python literals.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
    except json.JSONDecodeError:
        pass
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (list, tuple)):
            return [str(v) for v in parsed]
    except (ValueError, SyntaxError):
        pass
    return [text]


@dataclass
class SWEBenchInstance:
    """A normalized SWE-bench task instance."""

    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str = ""
    patch: str = ""
    test_patch: str = ""
    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    version: str = ""
    environment_setup_commit: str = ""
    # Optional: a local repository path to use instead of a network clone (offline CI).
    local_repo: Optional[str] = None

    @property
    def owner(self) -> str:
        return self.repo.split("/", 1)[0]

    @property
    def name(self) -> str:
        return self.repo.split("/", 1)[-1]

    def test_node_ids(self) -> list[str]:
        """All declared test node ids (FAIL_TO_PASS + PASS_TO_PASS), de-duplicated."""
        seen: list[str] = []
        for node in [*self.fail_to_pass, *self.pass_to_pass]:
            if node not in seen:
                seen.append(node)
        return seen

    def to_manifest(self) -> dict[str, Any]:
        """Provenance fields recorded on every episode result."""
        return {
            "instance_id": self.instance_id,
            "repo": self.repo,
            "base_commit": self.base_commit,
            "version": self.version,
            "environment_setup_commit": self.environment_setup_commit,
            "n_fail_to_pass": len(self.fail_to_pass),
            "n_pass_to_pass": len(self.pass_to_pass),
        }


def from_dict(data: dict[str, Any], *, local_repo: Optional[str] = None) -> SWEBenchInstance:
    return SWEBenchInstance(
        instance_id=str(data["instance_id"]),
        repo=str(data["repo"]),
        base_commit=str(data.get("base_commit", "")),
        problem_statement=str(data.get("problem_statement", "")),
        patch=str(data.get("patch", "")),
        test_patch=str(data.get("test_patch", "")),
        fail_to_pass=_as_list(data.get("FAIL_TO_PASS", data.get("fail_to_pass"))),
        pass_to_pass=_as_list(data.get("PASS_TO_PASS", data.get("pass_to_pass"))),
        version=str(data.get("version", "")),
        environment_setup_commit=str(data.get("environment_setup_commit", "")),
        local_repo=local_repo if local_repo is not None else data.get("local_repo"),
    )


def load_instance(path: str | Path, *, local_repo: Optional[str] = None) -> SWEBenchInstance:
    """Load a SWE-bench instance from a local JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return from_dict(data, local_repo=local_repo)


def load_instance_from_hf(
    instance_id: str,
    dataset: str = "SWE-bench/SWE-bench_Verified",
    *,
    split: str = "test",
    local_repo: Optional[str] = None,
) -> SWEBenchInstance:
    """Fetch one instance from a HF dataset.

    Network/HF access is required; this is **not** used by the offline default path. The
    ``datasets`` library is an optional dependency (``.[hf]`` extra).
    """
    from datasets import load_dataset  # type: ignore[import-untyped]

    ds = load_dataset(dataset, split=split)
    for row in ds:
        if row.get("instance_id") == instance_id:
            return from_dict(dict(row), local_repo=local_repo)
    raise KeyError(f"instance_id {instance_id!r} not found in {dataset}[{split}]")


__all__ = [
    "SWEBenchInstance",
    "from_dict",
    "load_instance",
    "load_instance_from_hf",
]
