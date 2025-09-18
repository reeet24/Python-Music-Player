import os
import sys
import requests
import zipfile
import tempfile
import shutil

# --- Config ---
REPO = "reeet24/Python-Music-Player" 
BRANCH = "main"
VERSION_FILE = "version.txt"

def get_local_version() -> str:
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "0.0.0"

def get_remote_version() -> str:
    url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{VERSION_FILE}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.text.strip()
    raise RuntimeError(f"Failed to fetch remote version: {r.status_code}")

def download_and_extract():
    url = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"
    print(f"Downloading {url}...")
    r = requests.get(url, stream=True)
    r.raise_for_status()

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "repo.zip")

    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    extracted_dir = next(
        os.path.join(temp_dir, d)
        for d in os.listdir(temp_dir)
        if os.path.isdir(os.path.join(temp_dir, d))
    )
    return extracted_dir, temp_dir

def update_files(new_dir: str):
    for item in os.listdir(new_dir):
        src = os.path.join(new_dir, item)
        dst = os.path.join(os.getcwd(), item)

        if os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

def Update():
    local = get_local_version()
    remote = get_remote_version()
    print(f"Local version: {local}")
    print(f"Remote version: {remote}")

    if local == remote:
        print("Already up-to-date.")
        return True

    print("Updating...")
    new_dir, temp_dir = download_and_extract()
    try:
        update_files(new_dir)
    finally:
        shutil.rmtree(temp_dir)

    print("Update complete! Please restart the program.")
    sys.exit(0)

if __name__ == "__main__":
    Update()
