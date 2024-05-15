import concurrent.futures
import os
import functools
import glob
import json
import shutil

from io import BytesIO
from requests import Session
from typing import NamedTuple
from zipfile import ZipFile

# GAME_DIR = "/Users/jamos/Library/Containers/com.isaacmarovitz.Whisky/Bottles/8360D9E1-9B3A-4951-A7D2-099CFE706B90/drive_c/Program Files (x86)/Steam/steamapps/common/Lethal Company/"
GAME_DIR = "game"
MODS_LIST_FILE_NAME = "mods.txt"
OUT_DIR = os.path.abspath("mods")

SEP = "-"
TARGET_BASE_URL = "https://thunderstore.io/package/download"
MOD_DIR_IGNORE = ("readme.md", "icon.png", "manifest.json", "changelog.md", "license")
BEPINEX_PACKAGE_NAME = "BepInExPack"
BEPINEX = "BepInEx"
GAME_BEPINEX_DIR = os.path.join(GAME_DIR, BEPINEX)
BEPINEX_PLUGINS_DIR = "plugins"
BEPINEX_PATCHERS_DIR = "patchers"
BEPINEX_CONFIG_DIR = "config"


class Mod(NamedTuple):
    by: str
    name: str
    version: str

    @property
    def package_name(self) -> str:
        return f"{self.by}{SEP}{self.name}{SEP}{self.version}"

    @property
    def download_path(self) -> str:
        return os.path.abspath(os.path.join(OUT_DIR, self.package_name))

    @property
    def url(self) -> str:
        return f"{TARGET_BASE_URL}/{self.by}/{self.name}/{self.version}"

    @property
    def exists(self) -> bool:
        return os.path.exists(self.download_path)

    @property
    def manifest_file(self) -> str:
        return os.path.join(self.download_path, "manifest.json")

    @property
    def is_bepinex(self) -> bool:
        return self.name.casefold() == BEPINEX_PACKAGE_NAME.casefold()

    @property
    def bepinex_dir(self) -> str:
        return os.path.join(self.download_path, BEPINEX)

    @property
    def depends_on_bepinex(self) -> bool:
        for _, dirs, _ in os.walk(self.download_path):
            for dir in dirs:
                if BEPINEX in dir:
                    return True
        with open(self.manifest_file, encoding="utf-8-sig") as f:
            data = json.load(f)

        return any(BEPINEX in dep for dep in data["dependencies"])


def _is_bepinex_installed() -> bool:
    return os.path.exists(GAME_BEPINEX_DIR)


def _read_mods() -> tuple[tuple[Mod, ...], Mod | None]:
    with open(MODS_LIST_FILE_NAME) as f:
        lines = f.readlines()
    mods = [Mod(*mod.rstrip().split(SEP)) for mod in lines]
    try:
        bepinex_mods = [m for m in mods if m.is_bepinex]
        if len(bepinex_mods) > 1:
            raise ValueError(
                f"Multiple {BEPINEX_PACKAGE_NAME} entries in '{MODS_LIST_FILE_NAME}' [{bepinex_mods}]"
            )
        bepinex_mod = mods.pop(mods.index(bepinex_mods.pop()))
    except IndexError:
        bepinex_mod = None
    return tuple(mods), bepinex_mod


def _download(session: Session, mod: Mod) -> int:
    if mod.exists:
        return 0

    response = session.get(mod.url)
    response.raise_for_status()

    z = ZipFile(BytesIO(response.content))
    z.extractall(mod.download_path)
    print(f"Downloaded {mod}")
    return 1


def _get_file_install_path(file: str, is_bepinex: bool) -> str:
    if is_bepinex:
        file = file.replace(f"{BEPINEX_PACKAGE_NAME}{os.sep}", "")
        return os.path.join(GAME_DIR, file)

    file = file.replace("\\", os.sep).replace(f"{BEPINEX}{os.sep}", "")
    try:
        _sub_dir = file[: file.index(os.sep)]
    except ValueError:
        file = os.path.join(BEPINEX_PLUGINS_DIR, file)
    else:
        if _sub_dir not in (
            BEPINEX_PLUGINS_DIR,
            BEPINEX_PATCHERS_DIR,
            BEPINEX_CONFIG_DIR,
        ):
            file = os.path.join(BEPINEX_PLUGINS_DIR, file)

    return os.path.join(GAME_BEPINEX_DIR, file)


def _install(mod: Mod) -> int:
    if not mod.depends_on_bepinex and not mod.is_bepinex:
        print(f"Unable to install {mod} as it doesn't depend on {BEPINEX}")
        return 0

    all_files = tuple(
        f
        for f in glob.glob("**", root_dir=mod.download_path, recursive=True)
        if os.path.basename(f).lower() not in MOD_DIR_IGNORE
        and not os.path.isdir(os.path.join(mod.download_path, f))
    )

    installed = False
    for file in all_files:
        file_install_path = _get_file_install_path(file, mod.is_bepinex)
        if os.path.exists(file_install_path):
            continue
        os.makedirs(os.path.dirname(file_install_path), exist_ok=True)
        shutil.copy(os.path.join(mod.download_path, file), file_install_path)
        installed = True
    action = "Installed" if installed else "Already Installed (Skipped)"
    print(f"{action} {mod}")
    return 1 if installed else 0


def _download_and_install_mod(session: Session, mod: Mod) -> tuple[int, int]:
    return _download(session, mod), _install(mod)


def main() -> int:
    if not os.path.isdir(OUT_DIR):
        print(f"Target directory '{OUT_DIR}' does not exist.")
        return 1

    if not os.path.isdir(GAME_DIR):
        print(f"Game directory '{GAME_DIR}' does not exist.")
        return 1

    mods, bepinex_mod = _read_mods()

    with Session() as session:
        if not _is_bepinex_installed():
            msg = f"{BEPINEX_PACKAGE_NAME} is not installed. "
            if bepinex_mod is not None:
                print(f"{msg}It will be installed first...")
                _download_and_install_mod(session, bepinex_mod)
            else:
                print(f"{msg}Add it to '{MODS_LIST_FILE_NAME}' or install it manually.")
                print("See https://thunderstore.io/package/bbepis/BepInExPack")
                return 1
        elif bepinex_mod is not None:
            print(f"{BEPINEX} is already installed. Skipping {bepinex_mod}...")

        with concurrent.futures.ThreadPoolExecutor() as ex:
            _func = functools.partial(_download_and_install_mod, session)
            results = ex.map(_func, mods)
        downloaded = 0
        installed = 0
        for result in results:
            downloaded += result[0]
            installed += result[1]
        tot = len(mods)
        print(f"Downloaded {downloaded}/{tot}. Installed {installed}/{tot}.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
