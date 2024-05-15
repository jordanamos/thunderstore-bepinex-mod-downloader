import concurrent.futures
import os
import functools
import glob
import json
import shutil

from io import BytesIO
from requests import Session
from typing import NamedTuple
from zipfile import BadZipFile
from zipfile import ZipFile

GAME_DIR = "/Users/jamos/Library/Containers/com.isaacmarovitz.Whisky/Bottles/8360D9E1-9B3A-4951-A7D2-099CFE706B90/drive_c/Program Files (x86)/Steam/steamapps/common/Lethal Company/"
BEPINEX_PACKAGE_NAME = "BepInEx-BepInExPack-5.4.2100"
MODS_LIST_FILE_NAME = "mods.txt"
OUT_DIR = os.path.abspath("mods")

SEP = "-"
TARGET_BASE_URL = "https://thunderstore.io/package/download"
MOD_DIR_IGNORE = ("readme.md", "icon.png", "manifest.json", "changelog.md", "license")
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
        return os.path.join(self.out_path, "manifest.json")

    @property
    def is_bepinex(self) -> bool:
        return self.package_name.casefold() == BEPINEX_PACKAGE_NAME.casefold()

    @property
    def bepinex_dir(self) -> str:
        return os.path.join(self.out_path, BEPINEX)

    @property
    def depends_on_bepinex(self) -> bool:
        for _, dirs, _ in os.walk(self.out_path):
            for dir in dirs:
                if BEPINEX in dir:
                    return True
        with open(self.manifest_file, encoding="utf-8-sig") as f:
            data = json.load(f)
        return BEPINEX_PACKAGE_NAME in data["dependencies"]


def _is_bepinex_installed() -> bool:
    return os.path.exists(GAME_BEPINEX_DIR)


def _read_mods() -> tuple[Mod, ...]:
    with open(MODS_LIST_FILE_NAME) as f:
        mods = f.readlines()
    return tuple(Mod(*mod.rstrip().split(SEP)) for mod in mods)


def _download(session: Session, mod: Mod) -> int:
    if mod.exists:
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


def _get_out_file_path(file_to_copy: str) -> str:
    file_to_copy = file_to_copy.replace("\\", os.sep).replace(f"{BEPINEX}{os.sep}", "")
    try:
        _sub_dir = file_to_copy[: file_to_copy.index(os.sep)]
    except ValueError:
        file_to_copy = os.path.join(BEPINEX_PLUGINS_DIR, file_to_copy)
    else:
        if _sub_dir not in (
            BEPINEX_PLUGINS_DIR,
            BEPINEX_PATCHERS_DIR,
            BEPINEX_CONFIG_DIR,
        ):
            file_to_copy = os.path.join(BEPINEX_PLUGINS_DIR, file_to_copy)
    return os.path.join(GAME_BEPINEX_DIR, file_to_copy)


def _install(mod: Mod) -> None:
    if not mod.depends_on_bepinex:
        print(
            f"Unable to install {mod.out_path} because it doesn't depend on {BEPINEX}"
        )
        return

    all = tuple(
        f
        for f in glob.glob("**", root_dir=mod.out_path, recursive=True)
        if os.path.basename(f).lower() not in MOD_DIR_IGNORE
        and not os.path.isdir(os.path.join(mod.out_path, f))
    )

    installed = False
    for file_to_copy in all:
        out_file = _get_out_file_path(file_to_copy)
        if os.path.exists(out_file):
            continue
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        shutil.copy(os.path.join(mod.out_path, file_to_copy), out_file)
        installed = True

    action = "Installed" if installed else "Already Installed (Skipped)"
    print(f"{action} {mod.by} / {mod.name}")


def _download_and_install(session: Session, mod: Mod) -> int:
    ret = _download(session, mod)
    # BepInEx Should be installed manually first
    if not mod.is_bepinex:
        _install(mod)
    return ret


def main() -> int:
    if not os.path.isdir(OUT_DIR):
        print(f"Target directory '{OUT_DIR}' does not exist.")
        return 1

    if not _is_bepinex_installed():
        print(
            f"{BEPINEX_PACKAGE_NAME} is not installed. Check '{GAME_BEPINEX_DIR}' exists."
        )
        return 1

    mods = _read_mods()

    with concurrent.futures.ThreadPoolExecutor() as ex, Session() as session:
        _func = functools.partial(_download_and_install, session)
        results = ex.map(_func, mods)
        print(f"Downloaded and Installed {sum(results)} / {len(mods)} mods.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
