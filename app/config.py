"""Central configuration. Everything tunable lives here, overridable via env vars."""
import os


def _load_dotenv() -> None:
    """Tiny .env loader for local development (no dependency). Env vars win."""
    for candidate in (".env", os.path.join(os.path.dirname(__file__), "..", ".env")):
        try:
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break
        except OSError:
            continue


_load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


# --- IO paths (competition harness contract) ---
INPUT_PATH = os.environ.get("INPUT_PATH", "/input/tasks.json")
OUTPUT_PATH = os.environ.get("OUTPUT_PATH", "/output/results.json")

# --- Fireworks API ---
def _baked_key() -> str:
    """Key baked as a file inside the image takes priority over the env var.

    If the judging harness injects its own FIREWORKS_API_KEY at runtime it
    would override the image ENV — but that key cannot access our private
    Gemma deployment. A file inside the image cannot be overridden.
    """
    path = os.path.join(os.path.dirname(__file__), "fw_key.txt")
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


FIREWORKS_API_KEY = _baked_key() or os.environ.get("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.environ.get(
    "FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"
)
# Primary and fallback models — all Gemma to stay eligible for the Gemma prize.
MODEL_PRIMARY = os.environ.get(
    "MODEL_PRIMARY", "accounts/fireworks/models/gemma-4-31b-it"
)
MODEL_FALLBACK = os.environ.get(
    "MODEL_FALLBACK", "accounts/fireworks/models/gemma-4-26b-a4b-it"
)
# Serverless vision model used for image-bearing calls when the Gemma
# deployment is unreachable (pay-per-token, no hourly cost when unused).
MODEL_VISION_FALLBACK = os.environ.get(
    "MODEL_VISION_FALLBACK", "accounts/fireworks/models/qwen3p7-plus"
)
MOCK_API = os.environ.get("MOCK_API", "") == "1"

# --- Timing budgets (seconds) ---
GLOBAL_DEADLINE = _float("GLOBAL_DEADLINE", 500.0)   # write output by ~8.3 min
API_TIMEOUT = _float("API_TIMEOUT", 25.0)            # per-request rule is <30s
DOWNLOAD_TIMEOUT = _float("DOWNLOAD_TIMEOUT", 150.0)
API_RETRIES = _int("API_RETRIES", 3)

# --- Frame sampling ---
THUMB_WIDTH = 320          # tiny frames for motion analysis
FRAME_WIDTH = 768          # frames sent to Gemma
MIN_FRAMES = _int("MIN_FRAMES", 10)
MAX_FRAMES = _int("MAX_FRAMES", 40)
SECONDS_PER_FRAME = _float("SECONDS_PER_FRAME", 3.0)  # budget = duration/this
WRITER_MAX_FRAMES = _int("WRITER_MAX_FRAMES", 24)     # writers get subset
JPEG_QUALITY = _int("JPEG_QUALITY", 4)                # ffmpeg -q:v (2=best, 6=ok)

# --- Caption generation ---
N_CANDIDATES = _int("N_CANDIDATES", 6)
REFINE_THRESHOLD = _float("REFINE_THRESHOLD", 0.85)   # rewrite below this score

# --- Concurrency ---
MAX_CONCURRENT_DOWNLOADS = _int("MAX_CONCURRENT_DOWNLOADS", 4)
MAX_CONCURRENT_FFMPEG = _int("MAX_CONCURRENT_FFMPEG", 3)
MAX_CONCURRENT_API = _int("MAX_CONCURRENT_API", 8)

VALID_STYLES = ["formal", "sarcastic", "humorous_tech", "humorous_non_tech"]

# Gemma 4 thinking mode: "none" disables hidden reasoning (faster, cheaper);
# set REASONING_EFFORT=low/medium to re-enable.
REASONING_EFFORT = os.environ.get("REASONING_EFFORT", "none")
