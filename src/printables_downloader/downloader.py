import os
import re
import sys
import json
import time
import argparse
import requests
from typing import List


INVALID_WINDOWS_CHARS = '<>:"/\\|?*'


def make_session() -> requests.Session:
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PrintablesDownloader/1.0"
    }
    s = requests.Session()
    s.headers.update(headers)
    return s


SESSION = make_session()


def sanitize_filename(name: str) -> str:
    return "".join(c if c not in INVALID_WINDOWS_CHARS else "_" for c in name)


def extract_model_json_from_url(url: str, verbose: bool = False) -> dict:
    if not url.endswith("/files"):
        url = url.rstrip("/") + "/files"

    if verbose:
        print(f"📡 Fetching: {url}")
    res = SESSION.get(url)
    if not res.ok:
        raise RuntimeError(f"❌ Failed to fetch page: {res.status_code}")

    if verbose:
        print("✅ Page fetched.")

    match = re.search(
        r'<script[^>]*type="application/json"[^>]*>((?:(?!</script>).)*stls(?:(?!</script>).)*)</script>',
        res.text,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("❌ Couldn't find <script> block with 'stls'.")

    if verbose:
        print("🎯 Found the <script> block with 'stls'.")
    try:
        outer_json = json.loads(match.group(1))
        inner_json_str = outer_json.get("body")
        if not inner_json_str:
            raise ValueError("⚠️ No 'body' key found in outer JSON.")
        inner_json = json.loads(inner_json_str)
        if verbose:
            print("✅ Successfully extracted model JSON.")
        return inner_json
    except Exception as e:
        raise RuntimeError(f"❌ Failed to parse JSON: {e}")


def graphql_download_url(file_id, model_id) -> str:
    url = "https://api.printables.com/graphql/"
    payload = {
        "operationName": "GetDownloadLink",
        "query": """mutation GetDownloadLink($id: ID!, $modelId: ID!, $fileType: DownloadFileTypeEnum!, $source: DownloadSourceEnum!) {\n  getDownloadLink(\n    id: $id\n    printId: $modelId\n    fileType: $fileType\n    source: $source\n  ) {\n    ok\n    output {\n      link\n    }\n  }\n}""",
        "variables": {
            "fileType": "stl",
            "id": file_id,
            "modelId": model_id,
            "source": "model_detail",
        },
    }

    r = SESSION.post(url, json=payload)
    r.raise_for_status()
    data = r.json()
    if data["data"]["getDownloadLink"]["ok"]:
        return data["data"]["getDownloadLink"]["output"]["link"]
    return None


def download_file(url, save_path, file_name, dry_run=False, verbose=False) -> bool:
    if dry_run:
        print(f"🤖 Dry run: Would download {file_name} to {save_path}")
        return True

    for attempt in range(3):
        if verbose:
            print(f"⬇️ Attempt {attempt+1} to download {file_name}")
        try:
            resp = SESSION.get(url, stream=True)
            if resp.ok:
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"✅ Saved: {save_path}")
                return True
            else:
                print(f"❌ Failed with {resp.status_code} - {resp.reason}")
        except Exception as e:
            print(f"⚠️ Error: {e}")
        time.sleep(1.0)

    print(f"💀 Giving up on {file_name} after 3 attempts.")
    return False


def download_model_files(
    data: dict,
    output_root: str,
    extensions: List[str],
    dry_run: bool = False,
    verbose: bool = False,
):
    model_id = data["data"]["model"]["id"]
    stls = data["data"]["model"].get("stls", [])

    if ".3mf" in extensions and not any(f["name"].lower().endswith(".3mf") for f in stls):
        if ".stl" not in extensions:
            if verbose:
                print("ℹ️ No .3mf files found for this model, adding .stl to extensions.")
            extensions.append(".stl")

    files = [f for f in stls if f["name"].lower().endswith(tuple(extensions))]

    remaining = []
    for file in files:
        file_name = sanitize_filename(file["name"])
        folder = sanitize_filename(file.get("folder", ""))
        save_dir = os.path.join(output_root, folder)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, file_name)

        if os.path.exists(save_path) and not dry_run:
            print(f"✅ Already downloaded: {save_path}")
            continue

        remaining.append((file, save_path))

    for file, save_path in remaining:
        file_id = file["id"]
        file_name = file["name"]

        if verbose:
            print(f"🔗 Getting link for {file_name}...")
        url = graphql_download_url(file_id, model_id)

        if url:
            success = download_file(url, save_path, file_name, dry_run, verbose)
            if not success:
                print(f"❌ Could not download: {file_name}")
        else:
            print(f"⚠️ No link for {file_name}")

    print("🎉 Done!")


def main():
    parser = argparse.ArgumentParser(description="Download 3D model files from Printables.com by URL"
    )
    parser.add_argument("url", help="Printables.com model URL")
    parser.add_argument("-o", "--output", default=".", help="Output root folder (default: current directory)")
    parser.add_argument("-e", "--ext", nargs="+", default=[".3mf"], help="File extensions to download (default: .3mf)")
    parser.add_argument("--dry", "--dry-run", action="store_true", help="Dry run only")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    try:
        if args.url.isdigit():
            model_url = f"https://www.printables.com/model/{args.url}"
        else:
            model_url = args.url

        model_json = extract_model_json_from_url(model_url, verbose=args.verbose)
        download_model_files(
            data=model_json,
            output_root=args.output,
            extensions=[e if e.startswith(".") else f".{e}" for e in args.ext],
            dry_run=args.dry,
            verbose=args.verbose,
        )
    except KeyboardInterrupt:
        print("🛑 Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
