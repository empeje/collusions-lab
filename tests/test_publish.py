from scripts.publish import parse_env


def test_parse_env_handles_comments_quotes_and_blanks():
    text = (
        "# comment line\n"
        "\n"
        "GH_TOKEN=abc123\n"
        'HF_TOKEN = "xyz"\n'
        "HF_USERNAME='me'\n"
        "not-a-pair\n"
    )
    env = parse_env(text)
    assert env == {"GH_TOKEN": "abc123", "HF_TOKEN": "xyz", "HF_USERNAME": "me"}


def test_parse_env_empty_value():
    assert parse_env("GH_TOKEN=\n")["GH_TOKEN"] == ""
