import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src" / "agentic_system"))

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return None

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from ui.app import main

if __name__ == "__main__":
    main()
