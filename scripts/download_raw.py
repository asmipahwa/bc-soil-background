"""Rebuild data/raw/ from config/raw_manifest.yaml. Skips files that already exist.

Usage: uv run python scripts/download_raw.py
"""

import zipfile

import requests
import yaml

from bc_soil_background.paths import CONFIG, RAW

USER_AGENT = "bc-soil-background/0.1 (independent student project)"


def main() -> None:
    manifest = yaml.safe_load((CONFIG / "raw_manifest.yaml").read_text())["files"]
    for item in manifest:
        dest = RAW / item["path"]
        if dest.exists():
            print(f"have  {item['path']}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"fetch {item['path']}")
            with requests.get(item["url"], headers={"User-Agent": USER_AGENT}, stream=True, timeout=300) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
                tmp.rename(dest)
        if "unzip_to" in item and not (RAW / item["unzip_to"]).exists():
            with zipfile.ZipFile(dest) as z:
                z.extractall(RAW / item["unzip_to"])


if __name__ == "__main__":
    main()
