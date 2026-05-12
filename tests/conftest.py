"""Put skill/scripts on sys.path so tests can `import session` and `import camclave`."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skill" / "scripts"))
