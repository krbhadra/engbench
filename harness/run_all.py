"""Run every model on both tracks, then print the leaderboard.

    python harness/run_all.py                              # OpenRouter models, 3 trials
    python harness/run_all.py --trials 1                   # cheap smoke run
    python harness/run_all.py --transport claude-cli       # Claude models on the subscription

Edit MODELS before an OpenRouter run. Ids drift: confirm each one at
https://openrouter.ai/models and pin a provider for open-weight models.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent

# (openrouter model id, pinned provider or None). VERIFY THESE IDS BEFORE SPENDING.
MODELS = [
    ("anthropic/claude-sonnet-4.5", None),
    ("openai/gpt-5", None),
    ("google/gemini-2.5-pro", None),
    ("deepseek/deepseek-v3.2", "DeepSeek"),
    ("qwen/qwen3-235b-a22b", "Fireworks"),
]
# Models the `claude` CLI answers for on a Claude subscription (checked 2026-09-06).
CLI_MODELS = [("haiku", None), ("sonnet", None), ("opus", None), ("claude-fable-5-1", None)]
TRACKS = ["single-shot", "agentic"]


def main():
    extra = sys.argv[1:]  # passed through to run_eval, e.g. --trials 1 --tasks mech_001
    models = CLI_MODELS if "claude-cli" in extra else MODELS
    for model, provider in models:
        for track in TRACKS:
            cmd = [sys.executable, str(HERE / "run_eval.py"), "--model", model, "--track", track, *extra]
            if provider:
                cmd += ["--provider", provider]
            print(f"\n=== {model} / {track} ===")
            subprocess.run(cmd, check=False)
    subprocess.run([sys.executable, str(HERE / "leaderboard.py")])


if __name__ == "__main__":
    main()
