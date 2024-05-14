import concurrent.futures
import os
import functools

from io import BytesIO
from requests import Session
from zipfile import BadZipFile
from zipfile import ZipFile

MODS_LIST_FILE_NAME = "mods.txt"
TARGET_BASE_URL = "https://thunderstore.io/package/download"
OUT_DIR = "mods"

def _get_urls() -> tuple[str]:
    with open(MODS_LIST_FILE_NAME) as f:
        mods = f.readlines()

    urls = []
    for mod in mods:
        by, name, version = mod.rstrip().split("-")
        url = f"{TARGET_BASE_URL}/{by}/{name}/{version}"
        urls.append(url)
    return tuple(urls)

def _get_filename_from_url(url: str) -> str:
    by, name, version = url.lstrip(TARGET_BASE_URL).split("/")
    return f"{by}-{name}-{version}"

def _download(session: Session, url: str) -> None:
    try:
        filename = _get_filename_from_url(url)
        outpath = os.path.join(OUT_DIR, filename)
        if(os.path.exists(outpath)):
            print(f"Skipping mod {filename}. Already exists...")
            return None
        
        response = session.get(url)

        try:
            z = ZipFile(BytesIO(response.content))    
            z.extractall(outpath)
            print(f"Downloaded {filename}")
        except BadZipFile as ex:
            print('Error: {}'.format(ex))
    except Exception as e:
        print(f"Error downloading {filename} from {url}: {e}")

def main() -> int:
    if not os.path.exists(OUT_DIR):
        print(f"Target directory '{OUT_DIR}' does not exist.")
        return 1
    
    target_urls = _get_urls()

    with (
        concurrent.futures.ThreadPoolExecutor() as ex,
        Session() as session
    ):
        _func = functools.partial(_download, session)
        ex.map(_func, target_urls)

if __name__ == "__main__":
    raise SystemExit(main())