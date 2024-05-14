import concurrent.futures
import os
import functools
import glob
import json
from typing import NamedTuple

from io import BytesIO
from requests import Session
from zipfile import BadZipFile
from zipfile import ZipFile

MODS_LIST_FILE_NAME = "mods.txt"
SEP = "-"
TARGET_BASE_URL = "https://thunderstore.io/package/download"
OUT_DIR = "mods"
MOD_DIR_IGNORE = ("readme.md", "icon.png", "manifest.json", "changelog.md", "license")
BEPINEX = "BepInEx-BepInExPack-5.4.2100"

class Mod(NamedTuple):
    by: str
    name: str
    version: str

    @property
    def package_name(self) -> str:
        return f"{self.by}{SEP}{self.name}{SEP}{self.version}"

    @property
    def out_path(self) -> str:
        return os.path.abspath(os.path.join(OUT_DIR, self.package_name))
    
    @property
    def url(self) -> str:
        return f"{TARGET_BASE_URL}/{self.by}/{self.name}/{self.version}"

    @property
    def exists(self) -> bool:
        return os.path.exists(self.out_path)
    
    @property
    def manifest_file(self) -> str:
        return (os.path.join(self.out_path, "manifest.json"))
    
    @property
    def is_bepinex(self) -> str:
        return self.package_name == BEPINEX
    
    @property
    def bepinex_dir(self) -> str:
        return os.path.join(self.out_path, "BepInEx")
    
    @property
    def depends_on_bepinex(self) -> bool:
        if not os.path.exists(self.bepinex_dir):
            with open(self.manifest_file, encoding="utf-8-sig") as f:
                data = json.load(f)
            return BEPINEX in data["dependencies"]
        return True
    
def _read_mods() -> tuple[Mod]:
    with open(MODS_LIST_FILE_NAME) as f:
        mods = f.readlines()
    return tuple(Mod(*mod.rstrip().split(SEP)) for mod in mods)


def _download(session: Session, mod: Mod) -> int:
    if(mod.exists):
        return 0
    
    response = session.get(mod.url)
    response.raise_for_status()
    try:
        z = ZipFile(BytesIO(response.content))    
        z.extractall(mod.out_path)
        print(f"Downloaded {mod}")
        return 1
    except BadZipFile as ex:
        print(f"Error: {format(ex)}")
        return 0

def _install(mod: Mod) -> None:
    if not mod.depends_on_bepinex:
        print(f"Unable to install {mod.out_path} because it doesn't depend on BepInEx")

    all = tuple(
        f
        for f in glob.glob("**", root_dir=mod.out_path, recursive=True)
        if os.path.basename(f).lower() not in MOD_DIR_IGNORE 
        and not os.path.isdir(os.path.join(mod.out_path, f))
    )



def _download_and_install(session: Session, mod: Mod) -> int:
    ret = _download(session, mod)
    # BepInEx Should be installed first/manually
    # if ret > 0 and not mod.is_bepinex:
    _install(mod)
    return ret


def main() -> int:
    if not os.path.exists(OUT_DIR):
        print(f"Target directory '{OUT_DIR}' does not exist.")
        return 1
    
    mods = _read_mods()

    with (
        concurrent.futures.ThreadPoolExecutor() as ex,
        Session() as session
    ):
        _func = functools.partial(_download_and_install, session)
        results = ex.map(_func, mods)
        print(f"Downloaded and Installed {sum(results)} / {len(mods)} mods.")


if __name__ == "__main__":
    raise SystemExit(main())