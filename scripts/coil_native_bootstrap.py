"""断点下载固定 CPF Native bundle，再交给原工具校验并解包。"""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def download(url, archive, expected_size, expected_sha):
    attempts = 0
    while not archive.exists() or archive.stat().st_size < expected_size:
        offset = archive.stat().st_size if archive.exists() else 0
        if offset > expected_size:
            raise RuntimeError("Native archive exceeds the pinned size")
        attempts += 1
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-", "Accept-Encoding": "identity",
                                                       "User-Agent": "cpf-coil-native-bootstrap"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status != 206:
                    raise RuntimeError("Native endpoint did not honor the Range request")
                range_header = response.headers.get("Content-Range", "")
                match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", range_header)
                if not match or int(match.group(1)) != offset or int(match.group(3)) != expected_size:
                    raise RuntimeError("Native endpoint returned an unexpected Content-Range")
                with archive.open("ab") as output:
                    while True:
                        try:
                            chunk = response.read(1024 * 1024)
                        except http.client.IncompleteRead as error:
                            output.write(error.partial)
                            raise ConnectionError("Native bundle response ended early") from error
                        if not chunk:
                            break
                        output.write(chunk)
                        if output.tell() > expected_size:
                            raise RuntimeError("Native archive exceeds the pinned size")
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504):
                raise
            print("Native bundle HTTP " + str(error.code) + "; resume from " + str(offset), flush=True)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            print("Native bundle connection failed; resume from " + str(offset) + ": " + type(error).__name__, flush=True)
        current = archive.stat().st_size if archive.exists() else 0
        if current < expected_size:
            print("Native bundle downloaded " + str(current) + "/" + str(expected_size) + "; retrying", flush=True)
            time.sleep(min(attempts * 2, 30))
    if archive.stat().st_size != expected_size or digest(archive) != expected_sha:
        raise RuntimeError("Native bundle size or SHA-256 differs from the pinned official archive")
    return attempts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--locked-tools", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    tool = args.locked_tools.resolve() / "toolchains/kotlin-native/2.4.20-0.1.0-08"
    manifest = json.loads((tool / "bootstrap-linux.json").read_text(encoding="utf-8"))
    bundle = manifest["nativeBundle"]
    if manifest["kotlinVersion"] != "2.4.20-0.1.0-08" or not bundle["url"].startswith(
            "https://maven.eazytec-cloud.com/nexus/repository/"):
        raise RuntimeError("Unexpected Native bundle lock")
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    archive = destination / (bundle["directory"] + ".tar.gz")
    attempts = download(bundle["url"], archive, bundle["bytes"], bundle["sha256"])
    receipt = {"url": bundle["url"], "bytes": bundle["bytes"], "sha256": bundle["sha256"], "attempts": attempts}
    with (destination / "download-receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    subprocess.run(["python", "-B", str(tool / "bootstrap-native.py"), "--destination", str(destination),
                    "--kotlin-version", "2.4.20-0.1.0-08"], check=True)


if __name__ == "__main__":
    main()
