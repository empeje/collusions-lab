"""Publish helpers: GitHub repo, Hugging Face Space, and HF Dataset.

Tokens are read from the environment or a local gitignored ``.env`` file
(``GH_TOKEN``, ``HF_TOKEN``). Nothing secret is ever written into the repo.

Usage:
    python scripts/publish.py github     # create repo (if needed) + commit + push
    python scripts/publish.py space      # build staging dir + upload to a HF Space
    python scripts/publish.py dataset     # upload runs/ to a HF Dataset
    python scripts/publish.py all
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "collusions-lab"
SPACE_SUBDIR = "space"


# ---------------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------------
def parse_env(text: str) -> dict[str, str]:
    """Minimal .env parser: KEY=VALUE lines, '#' comments, optional quotes."""
    env: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        env[key.strip()] = value
    return env


def load_config() -> dict[str, str]:
    cfg = dict(os.environ)
    env_file = ROOT / ".env"
    if env_file.exists():
        for key, value in parse_env(env_file.read_text(encoding="utf-8")).items():
            cfg.setdefault(key, value)
    return cfg


def _require(cfg: dict[str, str], key: str) -> str:
    value = cfg.get(key, "").strip()
    if not value:
        raise SystemExit(f"{key} is not set (put it in .env or the environment).")
    return value


# ---------------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------------
def _gh_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }


def _git(*args: str, token: str | None = None) -> None:
    env = os.environ.copy()
    if token:
        env["GIT_ASKPASS"] = "echo"
        env["GIT_TERMINAL_PROMPT"] = "0"
    subprocess.run(["git", *args], cwd=ROOT, check=True, env=env)


def publish_github(cfg: dict[str, str]) -> str:
    token = _require(cfg, "GH_TOKEN")
    who = requests.get("https://api.github.com/user", headers=_gh_headers(token), timeout=30)
    who.raise_for_status()
    login = cfg.get("GITHUB_USERNAME") or who.json()["login"]
    repo = cfg.get("GH_REPO", DEFAULT_REPO)

    create = requests.post(
        "https://api.github.com/user/repos",
        headers=_gh_headers(token),
        json={"name": repo, "private": False,
              "description": "Trusted-monitor benchmark for harmful multi-agent collusion"},
        timeout=30,
    )
    if create.status_code not in (201, 422):  # 422 = already exists
        create.raise_for_status()

    if not (ROOT / ".git").exists():
        _git("init")
    _git("add", "-A")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0:
        _git("commit", "-m", "Milestone 1: trusted-monitor PoC (markets + SWE)")
    _git("branch", "-M", "main")
    remote = f"https://{login}:{token}@github.com/{login}/{repo}.git"
    _git("push", remote, "HEAD:main", token=token)
    url = f"https://github.com/{login}/{repo}"
    print(f"GitHub: {url}")
    return url


# ---------------------------------------------------------------------------------
# Hugging Face
# ---------------------------------------------------------------------------------
def _stage_space() -> Path:
    stage = Path(tempfile.mkdtemp(prefix="collusions_space_"))
    shutil.copytree(ROOT / "collusions_lab", stage / "collusions_lab")
    if (ROOT / "experiments").exists():
        shutil.copytree(ROOT / "experiments", stage / "experiments")
    for name in ("app.py", "requirements.txt", "README.md"):
        shutil.copy2(ROOT / SPACE_SUBDIR / name, stage / name)
    return stage


def publish_space(cfg: dict[str, str]) -> str:
    token = _require(cfg, "HF_TOKEN")
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    user = cfg.get("HF_USERNAME") or api.whoami()["name"]
    repo_id = f"{user}/{cfg.get('HF_SPACE', DEFAULT_REPO)}"
    api.create_repo(repo_id, repo_type="space", space_sdk="gradio", exist_ok=True)
    stage = _stage_space()
    try:
        api.upload_folder(
            repo_id=repo_id, repo_type="space", folder_path=str(stage),
            commit_message="Milestone 1 demo",
        )
        api.add_space_secret(repo_id, "HF_TOKEN", token)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    url = f"https://huggingface.co/spaces/{repo_id}"
    print(f"Space:  {url}")
    return url


def publish_dataset(cfg: dict[str, str]) -> str:
    token = _require(cfg, "HF_TOKEN")
    from huggingface_hub import HfApi

    runs = ROOT / "runs"
    if not runs.exists():
        raise SystemExit("no runs/ directory; run the experiments first")
    api = HfApi(token=token)
    user = cfg.get("HF_USERNAME") or api.whoami()["name"]
    repo_id = f"{user}/{cfg.get('HF_DATASET', DEFAULT_REPO + '-runs')}"
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True)
    api.upload_folder(
        repo_id=repo_id, repo_type="dataset", folder_path=str(runs),
        commit_message="Milestone 1 experiment outputs",
    )
    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"Dataset: {url}")
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish collusions-lab artifacts.")
    parser.add_argument("target", choices=["github", "space", "dataset", "all"])
    args = parser.parse_args(argv)
    cfg = load_config()
    if args.target in ("github", "all"):
        publish_github(cfg)
    if args.target in ("space", "all"):
        publish_space(cfg)
    if args.target in ("dataset", "all"):
        publish_dataset(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
