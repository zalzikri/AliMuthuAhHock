"""Generate the Day One logo with Gemini nano-banana (gemini-2.5-flash-image).

Reads GEMINI_API_KEY from the project .env. Never pass the key on the command line.

    python scripts/make_logo.py            # all variants
    python scripts/make_logo.py 2          # just variant 2
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "brand"
# Preference order. The script asks your key which of these actually exist and
# uses the first available, so a renamed preview id cannot break it.
MODEL_PREFERENCE = (
    "gemini-3-pro-image-preview",     # Nano Banana Pro / "nano banana 2"
    "gemini-3-pro-image",
    "gemini-2.5-flash-image-preview",
    "gemini-2.5-flash-image",         # original nano banana
)

# Official Jalur Gemilang CMYK (Jabatan Penerangan), converted to sRGB through
# the ColorSync Generic CMYK profile: blue 100/75/0/0, red 0/95/100/0, yellow 0/9/100/0.
BLUE, RED, YELLOW = "#024B8F", "#DA332B", "#FEDD1B"

POSTER = (
    "Contemporary editorial gig-poster illustration, like risograph and screen-print "
    "posters: large flat cut-paper colour shapes with hard angular edges, soft airbrushed "
    "spray shading only on skin, visible paper grain, bold asymmetric composition with "
    "the main mass on one side and generous white space. "
    f"Palette strictly: navy blue {BLUE}, red {RED}, golden yellow {YELLOW}, white, "
    "and a warm peach for skin. White background. No text, no letters, no watermark."
)
CUBE = (
    "Surreal 3D design study: realistic human faces mapped onto clean geometric blocks, "
    "studio lighting, crisp edges, playful but respectful, no caricature. "
    f"Solid background in navy blue {BLUE}. Accents only in red {RED} and golden "
    f"yellow {YELLOW}. No text, no letters, no watermark."
)

VARIANTS = {
    1: ("three-heads-overlap", POSTER,
        "A logo mark: three human heads in side profile, overlapping like cut paper. "
        "One head is navy, one red, one golden yellow. Faces are simple and friendly. "
        "Off-centre composition. Iconic and readable at small size."),
    2: ("three-heads-stripes", POSTER,
        "A logo mark: three simplified heads clustered tightly, each head built from "
        "horizontal flag stripes in navy, red and yellow. A crescent and a fourteen-point "
        "star are hidden in the negative space between them."),
    3: ("three-faces-cubes", CUBE,
        "A logo: three friendly young adults of different backgrounds, each face mapped "
        "onto its own cube, the three cubes stacked asymmetrically like building blocks. "
        "Warm, confident expressions. Reads as one team."),
    4: ("hero-figure", POSTER,
        "A tall poster figure seen from the side, wearing an oversized angular navy jacket "
        "that fills the left half of the image and bleeds off the bottom edge. The airbrushed "
        "peach face looks up, eyes closed, calm. Two airbrushed hands hold out a golden "
        "yellow keycard. A white zig-zag cut runs through the navy jacket. A small red "
        "geometric block sits at the lower right."),
}


def load_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("GEMINI_API_KEY", "")


def pick_model(key: str) -> str:
    """Ask the API which image models this key can see, best first."""
    override = os.environ.get("GEMINI_IMAGE_MODEL")
    if override:
        return override
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
        headers={"x-goog-api-key": key})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=40))
    except Exception as e:
        print(f"  could not list models ({type(e).__name__}); "
              f"falling back to {MODEL_PREFERENCE[-1]}")
        return MODEL_PREFERENCE[-1]
    have = {m["name"].split("/")[-1] for m in data.get("models", [])}
    for candidate in MODEL_PREFERENCE:
        if candidate in have:
            return candidate
    image_models = sorted(n for n in have if "image" in n)
    if image_models:
        print(f"  none of the preferred models; using {image_models[0]}")
        return image_models[0]
    raise SystemExit(f"This key sees no image models. Available: {sorted(have)[:12]}")


def generate(key: str, model: str, name: str, prompt: str) -> Path | None:
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
    }).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=body, headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        res = json.load(urllib.request.urlopen(req, timeout=120))
    except Exception as e:
        detail = ""
        if isinstance(e, urllib.error.HTTPError):
            try:
                detail = json.load(e).get("error", {}).get("message", "")[:200]
            except Exception:
                pass
        print(f"  {name}: FAILED {type(e).__name__} {detail or str(e)[:160]}")
        return None

    for cand in res.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob and blob.get("data"):
                OUT.mkdir(parents=True, exist_ok=True)
                path = OUT / f"logo-{name}.png"
                path.write_bytes(base64.b64decode(blob["data"]))
                print(f"  {name}: {path}  ({path.stat().st_size // 1024} KB)")
                return path
    print(f"  {name}: no image in the response")
    return None


def main() -> None:
    key = load_key()
    if not key:
        raise SystemExit("No GEMINI_API_KEY. Add it to .env, one line: "
                         "GEMINI_API_KEY=your-key")
    model = pick_model(key)
    print(f"key loaded ({len(key)} chars), using model: {model}")
    wanted = [int(a) for a in sys.argv[1:]] or sorted(VARIANTS)
    for n in wanted:
        name, style, prompt = VARIANTS[n]
        print(f"variant {n} - {name}")
        generate(key, model, name, f"{prompt}\n\n{style}")


if __name__ == "__main__":
    main()
