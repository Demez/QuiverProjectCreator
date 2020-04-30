import sys
import os
from platform import machine
from enum import Enum, auto, EnumMeta
from time import perf_counter

global args


QPC_DIR = os.path.dirname(os.path.realpath(__file__)).replace("\\", "/") + "/"
QPC_GENERATOR_DIR = QPC_DIR + "project_generators"


def timer_diff(start_time: float) -> str:
    return str(round(perf_counter() - start_time, 4))


# header files like c/c++ would really be nice right about now
# this is to avoid circular imports, but still be able to use arguments here
def post_args_init():
    global args
    from qpc_args import args
    
    
class Arch(Enum):
    AMD64 = auto(),
    I386 = auto(),
    ARM = auto(),
    ARM64 = auto(),
    # POWER10 = auto(),
    # POWER9 = auto(),


class Platform(Enum):
    WINDOWS = auto(),
    LINUX = auto(),
    MACOS = auto(),
    
    
# architectures the platform is on
PLATFORM_ARCHS = {
    Platform.WINDOWS:   {Arch.I386, Arch.AMD64, Arch.ARM, Arch.ARM64},
    Platform.LINUX:     {Arch.I386, Arch.AMD64, Arch.ARM, Arch.ARM64},
    Platform.MACOS:     {Arch.AMD64},
}


class BaseProjectGenerator:
    def __init__(self, name: str):
        self.name = name
        self.filename = None
        self.path = None
        self.id = None
        self._platforms = []
        self._architectures = []
        self._uses_folders = False
        self._uses_master_file = False
        self._macro = ""
        
        self._start_time = None
        self._current_build = None
        
    # use this for anything that needs to be set after arguments are parsed/initialized
    def post_args_init(self):
        pass
    
    # finished parsing all projects, override function
    def projects_finished(self):
        pass
    
    def _print_creating(self, output_name: str):
        if args.time:
            self._start_time = perf_counter()
        else:
            print("Creating: " + output_name)
        self._current_build = output_name
    
    def _print_finished(self):
        if args.time and self._current_build:
            print(timer_diff(self._start_time) + " - Created: " + self._current_build)
        self._current_build = None
        
    # ProjectContainer from qpc_project.py
    def _get_passes(self, project) -> list:
        return project.get_passes(self.id)
    
    def _add_platform(self, platform: Platform) -> None:
        if platform not in Platform:
            raise Exception(f"Generator \"{self.name}\" tried adding an invalid platform: {platform.name}")
        elif platform not in self._platforms:
            self._platforms.append(platform)
    
    def _add_architecture(self, architecture: Arch) -> None:
        if architecture not in Arch:
            raise Exception(f"Generator \"{self.name}\" tried adding an invalid platform: {architecture.name}")
        elif architecture not in self._architectures:
            self._architectures.append(architecture)
    
    def _add_architectures(self, *architectures) -> None:
        [self._add_architecture(arch) for arch in architectures]
    
    def _add_platforms(self, *platforms) -> None:
        [self._add_platform(platform) for platform in platforms]
        
    def _set_project_folders(self, uses_project_folders: bool) -> None:
        self._uses_folders = uses_project_folders if type(uses_project_folders) == bool else self._uses_folders
    
    def _set_generate_master_file(self, use_master_file: bool) -> None:
        self._uses_master_file = use_master_file if type(use_master_file) == bool else self._uses_master_file
    
    def _set_macro(self, macro: str) -> None:
        self._macro = macro

    def get_macro(self) -> str:
        # return {"$" + self._macro: "1"} if self._macro else {}
        return self._macro

    def uses_folders(self) -> bool:
        return self._uses_folders
    
    def generates_master_file(self) -> bool:
        return self._uses_master_file
    
    def get_supported_platforms(self) -> list:
        return self._platforms
    
    def create_project(self, project_list) -> None:
        pass

    def does_project_exist(self, project_out_dir: str) -> bool:
        return True

    @staticmethod
    def _get_base_path(project_out_dir: str) -> str:
        return os.path.split(project_out_dir)[0] + "/"
    
    def get_master_file_path(self, master_file_path: str) -> None:
        print(f'Warning: Generator "{self.name}" doesn\'t override get_master_file_path but has _set_generate_master_file set to True')
        return ""
    
    def create_master_file(self, settings, master_file_path: str) -> str:
        # return file name or abspath or whatever
        pass

    def does_master_file_exist(self, master_file_path: str) -> bool:
        return True
    

def get_default_platform() -> Platform:
    if sys.platform == "win32":
        return Platform.WINDOWS
    
    elif sys.platform.startswith("linux"):
        return Platform.LINUX
    
    elif sys.platform == "darwin":
        return Platform.MACOS
    

def get_default_archs() -> tuple:
    if machine() in {"AMD64", "x86_64"}:
        return (Arch.I386, Arch.AMD64)
    
    # very rare
    elif machine() == "i386":
        return (Arch.I386,)
    
    
def is_arch_64bit(arch: Arch) -> bool:
    return arch in {Arch.AMD64, Arch.ARM64}


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


def norm_path(path: str) -> str:
    return posix_path(os.path.normpath(path))


def join_path(*paths) -> str:
    paths = list(paths)
    if len(paths) > 1:
        if "" in paths:
            paths.remove("")
        return posix_path(os.path.normpath("/".join(paths)))
    return posix_path(paths[0])


def join_path_list(include_dir: str, *paths: str) -> list:
    if include_dir:
        return [norm_path(include_dir + "/" + path) for path in paths]
    return [posix_path(path) for path in paths]


def check_file_path_glob(file_path: str) -> bool:
    return "*" in file_path or "[" in file_path and "]" in file_path or "?" in file_path


def create_directory(directory: str):
    if not os.path.isdir(directory):
        os.makedirs(directory)
        if args.verbose:
            print("Created Directory: " + directory)


def get_all_dict_values(d: dict):
    found_values = []
    for k, v in d.items():
        if isinstance(v, dict):
            found_values.extend(get_all_dict_values(v))
        else:
            # return found_values
            found_values.append(v)
    return found_values


def debug_assert(result: bool):
    if result:
        print("put breakpoint here")
