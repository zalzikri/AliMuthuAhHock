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

STYLE = (
    "Flat vector editorial poster illustration, in the style of contemporary "
    "silkscreen and risograph gig posters. Hard geometric edges, bold flat colour "
    "blocks, subtle paper grain, no gradients, no gloss, no 3D rendering, no "
    "photorealism. Strong asymmetric composition with generous negative space. "
    f"Palette strictly limited to Malaysian flag colours: blue {BLUE}, red {RED}, "
    f"yellow {YELLOW}, and white. Clean white background. No text, no lettering, "
    "no watermark."
)

VARIANTS = {
    1: ("three-heads-overlap",
        "A logo mark of three human heads in profile, overlapping, seen from the "
        "side. One head is solid blue, one solid red, one solid yellow. They "
        "interlock like cut paper shapes. The composition is deliberately "
        "off-centre. Simple, iconic, readable at small size."),
    2: ("three-heads-stripes",
        "A logo mark of three simplified human heads arranged in a tight cluster, "
        "each head built from horizontal stripes like a flag, in blue, red and "
        "yellow. A crescent and a star shape are hidden in the negative space "
        "between them. Bold, flat, poster-like."),
    3: ("doorway",
        "A logo mark of an open doorway cut as a geometric shape, with three "
        "simplified human figures in blue, red and yellow stepping through it "
        "together. Flat shapes, asymmetric, high contrast."),
    4: ("badge",
        "A square badge mark: a bold geometric letter shape suggesting a sunrise "
        "over fourteen horizontal stripes, with three small circular heads in "
        "blue, red and yellow sitting on the horizon. Flat, iconic, poster style."),
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
        "contents": [{"parts": [{"text": f"{prompt}\n\n{STYLE}"}]}],
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
        name, prompt = VARIANTS[n]
        print(f"variant {n} - {name}")
        generate(key, model, name, prompt)


if __name__ == "__main__":
    main()
