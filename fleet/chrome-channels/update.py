#!/usr/bin/env python3
"""Pin Google's native Linux channel artifacts for both fleet architectures."""
import argparse
import base64
import gzip
import json
from pathlib import Path
import urllib.request

CHANNELS = {"stable": "stable", "beta": "beta", "dev": "unstable", "canary": "canary"}

def read_packages(data):
    records = {}
    for paragraph in data.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in paragraph.splitlines()
                      if ": " in line and not line.startswith(" "))
        if "Package" in fields:
            records[fields["Package"]] = fields
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("sources.json"))
    args = parser.parse_args()
    sources = {channel: {"dist": dist, "platforms": {}} for channel, dist in CHANNELS.items()}
    for system, arch in [("x86_64-linux", "amd64"), ("aarch64-linux", "arm64")]:
        url = f"https://dl.google.com/linux/chrome/deb/dists/stable/main/binary-{arch}/Packages.gz"
        records = read_packages(gzip.decompress(urllib.request.urlopen(url).read()).decode())
        for channel, dist in CHANNELS.items():
            record = records[f"google-chrome-{dist}"]
            version = record["Version"].removesuffix("-1")
            sources[channel]["platforms"][system] = {
                "version": version,
                "url": "https://dl.google.com/linux/chrome/deb/" + record["Filename"],
                "hash": "sha256-" + base64.b64encode(bytes.fromhex(record["SHA256"])).decode(),
            }
    args.output.write_text(json.dumps(sources, indent=2) + "\n")

if __name__ == "__main__":
    main()
