import sys
import os
from enum import Enum, auto, EnumMeta


class BaseProjectGenerator:
    def __init__(self, name: str):
        self.name = name
        self._platforms = []
        self._compilers = []
    
    def _add_platform(self, platform: Enum) -> None:
        if platform not in Platform:
            raise Exception(f"Generator \"{self.name}\" tried adding an invalid platform: {platform.name}")
        elif platform not in self._platforms:
            self._platforms.append(platform)
    
    # will need to move Compiler enum class here
    def _add_compiler(self, compiler: Enum) -> None:
        pass
    
    def get_supported_platforms(self) -> list:
        return self._platforms
    
    # unused currently
    def get_supported_compilers(self) -> list:
        return self._compilers
    
    def create_project(self, project_list) -> None:
        pass

    def does_project_exist(self, project_out_dir: str) -> bool:
        return True

    @staticmethod
    def _get_base_path(project_out_dir: str) -> str:
        return os.path.split(project_out_dir)[0] + "/"
    
    def create_master_file(self, settings, master_file_path: str) -> None:
        pass


class Platform(Enum):
    WIN32 = auto(),
    WIN64 = auto(),
    LINUX32 = auto(),
    LINUX64 = auto(),
    MACOS = auto()


# really ugly and awful
class PlatformName(Enum):
    WINDOWS = auto(),
    POSIX = auto(),
    LINUX = auto(),
    MACOS = auto()


# BAD
PLATFORM_DICT = {
    PlatformName.WINDOWS:          {Platform.WIN32, Platform.WIN64},
    PlatformName.LINUX:            {Platform.LINUX32, Platform.LINUX64},
    PlatformName.MACOS:            {Platform.MACOS},
}


def get_platform_name(platform: Enum) -> Enum:
    for platform_name in PLATFORM_DICT:
        if platform in PLATFORM_DICT:
            return platform_name


def get_default_platforms() -> tuple:
    if sys.platform == "win32":
        return Platform.WIN32, Platform.WIN64
    
    elif sys.platform.startswith("linux"):
        return Platform.LINUX32, Platform.LINUX64
    
    elif sys.platform == "darwin":
        return Platform.MACOS,


# os.path.normpath is not doing this on linux for me, fun
'''
def fix_path_separator(string: str) -> str:
    if os.name == "nt":
        return string  # .replace("/", "\\")
    else:
        return string.replace("\\", "/")
'''


# just use this for everything probably, works just fine on windows
def posix_path(string: str) -> str:
    return string.replace("\\", "/")


def add_dict_value(dictionary: dict, key, value_type: type):
    try:
        dictionary[key]
    except KeyError:
        dictionary[key] = value_type()


def get_all_dict_values(d: dict):
    found_values = []
    for k, v in d.items():
        if isinstance(v, dict):
            found_values.extend(get_all_dict_values(v))
        else:
            # return found_values
            found_values.append(v)
    return found_values
