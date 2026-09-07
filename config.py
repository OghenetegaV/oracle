# config.py
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent
INPUT_DIR = PROJECT_ROOT / "input_dwgs"
OUTPUT_DXF_DIR = PROJECT_ROOT / "output_dxf"
OUTPUT_JSON_DIR = PROJECT_ROOT / "output_json"
LOGS_DIR = PROJECT_ROOT / "logs"

# Create directories if they don't exist
for dir_path in [INPUT_DIR, OUTPUT_DXF_DIR, OUTPUT_JSON_DIR, LOGS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ODA File Converter path
ODA_PATHS = [
    r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
]

ODA_CONVERTER_PATH = None
for path in ODA_PATHS:
    if os.path.exists(path):
        ODA_CONVERTER_PATH = path
        print(f"✓ ODA found at: {path}")
        break

if ODA_CONVERTER_PATH is None:
    print("⚠️  ODA not found")
else:
    print("✓ Config loaded successfully")

# --- Anthropic API key: env var, falling back to a local .env file (never hardcoded) ---
ENV_FILE_PATH = PROJECT_ROOT / ".env"


def _read_env_file():
    values = {}
    if ENV_FILE_PATH.exists():
        for line in ENV_FILE_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_api_key():
    """ANTHROPIC_API_KEY from the environment, else the local .env file, else None."""
    return os.environ.get("ANTHROPIC_API_KEY") or _read_env_file().get("ANTHROPIC_API_KEY")


def save_api_key(key):
    """Persist the key to a local, gitignored .env file so it never needs to be hardcoded
    or typed into a terminal again."""
    values = _read_env_file()
    values["ANTHROPIC_API_KEY"] = key.strip()
    ENV_FILE_PATH.write_text("".join(f'{k}="{v}"\n' for k, v in values.items()))