import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

TEXTS_URL = "https://www.habbo.com/gamedata/external_flash_texts/0"
IMAGES_URL = "https://images.habbo.com/c_images/album1584"
BADGE_DIR = Path(__file__).resolve().parents[1] / "c_images" / "album1584"
BADGE_KEY = re.compile(rb"^badge_(?:name|desc)_(ACH_[A-Za-z0-9_]+)=", re.MULTILINE)


def fetch(url):
    with TemporaryDirectory() as directory:
        output = Path(directory) / "response"
        response = subprocess.run(
            [
                "curl", "--silent", "--show-error", "--location", "--fail",
                "--connect-timeout", "10", "--max-time", "20", "--retry", "2",
                "--output", str(output), "--write-out", "%{http_code}", url,
            ],
            capture_output=True,
            text=True,
        )
        if response.returncode == 22 and response.stdout == "404":
            return None
        if response.returncode:
            raise RuntimeError(f"Download failed for {url}: {response.stderr.strip()}")
        if response.stdout != "200":
            raise ValueError(f"Unexpected HTTP status {response.stdout!r} for {url}")

        return output.read_bytes()


def download_badge(code):
    image = fetch(f"{IMAGES_URL}/{code}.gif")
    if image is not None and not image.startswith((b"GIF87a", b"GIF89a")):
        raise ValueError(f"Habbo returned a non-GIF response for {code}")
    return image


def main():
    texts = fetch(TEXTS_URL)
    codes = {code.decode("ascii") for code in BADGE_KEY.findall(texts or b"")}
    if not codes:
        raise ValueError("No ACH_ badge keys found in Habbo's external flash texts")

    missing = sorted(code for code in codes if not (BADGE_DIR / f"{code}.gif").exists())
    with ThreadPoolExecutor(max_workers=6) as pool:
        images = list(pool.map(download_badge, missing))

    added = 0
    for code, image in zip(missing, images):
        if image is None:
            continue

        path = BADGE_DIR / f"{code}.gif"
        with path.open("xb") as badge:
            badge.write(image)
        print(f"Added {path.name}")
        added += 1

    print(f"{len(codes)} codes checked, {added} GIFs added, {len(missing) - added} unavailable")


if __name__ == "__main__":
    main()
