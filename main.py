import sys

from runtime import build_default_runtime

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency fallback
    def load_dotenv():
        return None

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def main() -> None:
    runtime = build_default_runtime()
    runtime.run()


if __name__ == "__main__":
    main()
