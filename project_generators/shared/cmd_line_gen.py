from enum import Enum, auto
from qpc_project import Language


class Mode(Enum):
    MSVC = auto(),
    GCC = auto(),
    CLANG = auto(),


class CommandLineGen:
    def __init__(self, mode: str = ""):
        self._compiler = None
        self._mode = None
        self.switch = None
        self._char_inc_dir = None
        self._char_define = None
        self.set_mode(mode)
    
    def set_mode(self, mode: str):
        if mode and mode != self._compiler:
            self._compiler = mode
            if mode.startswith("msvc"):
                self._mode = Mode.MSVC
                self.switch = "/"
                self._char_inc_dir = "/I"
                self._char_define = "/D"
        
            elif mode.startswith("gcc") or mode.startswith("clang"):
                self.switch = "-"
                self._char_inc_dir = "-I"
                self._char_define = "-D"
                self._mode = Mode.GCC if mode.startswith("gcc") else Mode.CLANG
                
    def convert_includes(self, include_paths: list) -> list:
        converted_paths = []
        [converted_paths.append(f"{self._char_inc_dir}{path}") for path in include_paths]
        return converted_paths
        
    def convert_defines(self, defines: list) -> list:
        converted_paths = []
        [converted_paths.append(f"{self._char_define}{define}") for define in defines]
        return converted_paths
        
        
# meh
def get_compiler(compiler: str, language: Enum) -> str:
    # idk how msvc handles versions yet
    if compiler.startswith("msvc"):
        return "cl.exe"
    elif compiler.startswith("gcc_"):
        if language == Language.CPP:
            return "g++-" + str(compiler[4:])
        else:  # assuming language == Language.C:
            return "gcc-" + str(compiler[4:])
    elif compiler.startswith("clang_") and compiler != "clang_cl":
        return "clang-" + str(compiler[6:])
    else:
        return compiler
        

