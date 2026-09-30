"""Safety net for sharing the project: no API key may be committed.

Scans every file that git would commit (skipping ignored folders) for strings shaped like real keys.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "__pycache__", ".pytest_cache", "data", ".claude"}
TEXT_SUFFIXES = {".py", ".js", ".jsx", ".json", ".md", ".yml", ".yaml", ".txt", ".html", ".css", ".ini", ".example", ""}

# Shapes of real keys: Anthropic, Groq, OpenRouter, OpenAI-style, Google.
KEY_SHAPES = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{30,}|sk-or-[A-Za-z0-9-]{20,}|sk-[A-Za-z0-9]{32,}|AIza[0-9A-Za-z_-]{30,}"
)


def tracked_text_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not (set(path.relative_to(ROOT).parts) & SKIP_DIRS) and path.suffix in TEXT_SUFFIXES:
            if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
                continue  # the real .env is git-ignored (checked below)
            yield path


def test_no_api_key_shaped_strings_in_committable_files():
    offenders = []
    for path in tracked_text_files():
        if path.name == Path(__file__).name:
            continue
        if KEY_SHAPES.search(path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"Possible API key committed in: {offenders}"


def test_env_files_are_git_ignored_but_the_example_is_kept():
    lines = {line.strip() for line in (ROOT / ".gitignore").read_text().splitlines()}
    assert ".env" in lines and ".env.*" in lines and "!.env.example" in lines


def test_env_example_contains_no_secret_values():
    text = (ROOT / ".env.example").read_text()
    for line in text.splitlines():
        if line.startswith(("LLM_API_KEY=", "ANTHROPIC_API_KEY=", "REAL_MODE_ACCESS_CODE=")):
            assert line.split("=", 1)[1].strip() == "", f"secret value in .env.example: {line.split('=')[0]}"
