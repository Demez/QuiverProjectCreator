from enum import Enum, auto
from qpc_project import Compiler, Language


class Mode(Enum):
    MSVC = auto(),
    GCC = auto(),
    CLANG = auto(),


class CommandLineGen:
    def __init__(self, mode: Enum = None):
        self._compiler = None
        self._mode = None
        self.switch = None
        self._char_inc_dir = None
        self._char_define = None
        self.set_mode(mode)
    
    def set_mode(self, mode: Enum):
        if mode and mode != self._compiler and mode in Compiler:
            self._compiler = mode
            mode_name = mode.name.lower()
            if mode_name.startswith("msvc"):
                self._mode = Mode.MSVC
                self.switch = "/"
                self._char_inc_dir = "/I"
                self._char_define = "/D"
        
            elif mode_name.startswith("gcc") or mode_name.startswith("clang"):
                self.switch = "-"
                self._char_inc_dir = "-I"
                self._char_define = "-D"
                self._mode = Mode.GCC if mode_name.startswith("gcc") else Mode.CLANG
                
    def convert_includes(self, include_paths: list) -> list:
        converted_paths = []
        [converted_paths.append(f"{self._char_inc_dir}{path}") for path in include_paths]
        return converted_paths
        
    def convert_defines(self, defines: list) -> list:
        converted_paths = []
        [converted_paths.append(f"{self._char_define}{define}") for define in defines]
        return converted_paths
        
    # this is pretty bad, maybe i should consider adding a compiler_path option to qpc
    # hell, maybe even add just MSVC, GCC, and CLANG as options to default to latest
    def get_compiler_path(self, language: Enum) -> str:
        # idk how msvc handles versions yet
        if self._mode == Mode.MSVC:
            return "cl.exe"
        elif self._compiler in {Compiler.GCC_9, Compiler.GCC_8, Compiler.GCC_7, Compiler.GCC_6}:
            if language == Language.CPP:
                return "g++-" + str(self._compiler.name[-1])
            else:  # assuming language == Language.C:
                return "gcc-" + str(self._compiler.name[-1])
        elif self._compiler in {Compiler.CLANG_9, Compiler.CLANG_8}:
            return "clang-" + str(self._compiler.name[-1])
        return "g++"
        

