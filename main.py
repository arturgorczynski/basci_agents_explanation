import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent / "src" / "agentic_system"))

load_dotenv()

## Helps with encoding issues when printing polish chars
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def main() -> None:
    from runtime import build_default_runtime
    build_default_runtime().run()


if __name__ == "__main__":
    main()
