import os
from enum import Enum, auto
from qpc_project import (Language, Configuration, Compile, Link, General,
                         SourceFile, SourceFileCompile, ProjectPass, PrecompiledHeader)
from qpc_logging import warning
from ..shared import msvc_tools


class Mode(Enum):
    MSVC = auto(),
    GCC = auto(),
    CLANG = auto(),
    
    
LINUX_DEFAULT_INC_DIRS = [
    "/usr/local/include"
    "/usr/include"
]


class CommandLineGen:
    def __init__(self, mode: str = ""):
        self._compiler = None
        self.mode = None
        self.switch = None
        self._char_inc_dir = None
        self._char_define = None
        self.set_mode(mode)
    
    def set_mode(self, mode: str):
        if mode and mode != self._compiler:
            self._compiler = mode
            if mode.startswith("msvc"):
                self.mode = Mode.MSVC
                self.switch = "/"
                self._char_inc_dir = "/I"
                self._char_define = "/D"
        
            elif mode.startswith("gcc") or mode.startswith("g++") or mode.startswith("clang"):
                self.switch = "-"
                self._char_inc_dir = "-I"
                self._char_define = "-D"
                self.mode = Mode.GCC if mode.startswith("gcc") or mode.startswith("g++") else Mode.CLANG
    
    def get_file_build_path(self, general: General, file: str) -> str:
        path = f"{general.build_dir}/{os.path.splitext(os.path.basename(file))[0]}"
        return f"{path}.obj" if self.mode == Mode.MSVC else f"{path}.o"
    
    def file_compile_flags(self, cfg: Configuration, file: SourceFileCompile) -> str:
        return self.compile_flags(cfg.compile, cfg.general, file)
    
    def compile_flags(self, c: Compile, general: General = None, file: SourceFileCompile = None) -> str:
        cmd = []
        cmd.extend(self.convert_defines(c.defines))
        if file:
            cmd.extend(self.convert_defines(file.defines))

        cmd.extend(self.convert_includes(c.inc_dirs))
        
        if general is not None:
            if c.default_inc_dirs:
                if self.mode == Mode.MSVC:
                    cmd.extend(self.convert_includes(msvc_tools.get_inc_dirs(general.compiler)))
                # elif os.name.startswith("linux"):
                #     cmd.extend(self.convert_includes(LINUX_DEFAULT_INC_DIRS))
                # else:
                #     warning("unknown default include paths")

        # temporarily disabled
        # pch = self.get_pch_all(c.pch if not file.pch else file.pch,
        #                        file.pch_file, file.pch_out,
        #                        c.pch_file, c.pch_out)
        # if pch:
        #     cmd.extend(pch)
            
        cmd.extend(c.options)
        if file:
            cmd.extend(file.options)
        
        return " ".join(cmd)
    
    def link_flags(self, cfg: Configuration, libs: bool = True) -> str:
        cmd = []
        
        if cfg.link.debug_file:
            cmd.append(self.debug_file(cfg.link.debug_file))
            
        cmd.extend(self.lib_dirs(cfg.link.lib_dirs))
    
        if cfg.link.default_lib_dirs:
            if self.mode == Mode.MSVC:
                cmd.extend(self.lib_dirs(msvc_tools.get_lib_dirs("")))
            
        if libs and cfg.link.libs:
            cmd.extend(self.libs(cfg.link.libs))
            
        if cfg.link.ignore_libs:
            cmd.append(self.ignore_libs(cfg.link.ignore_libs))
            
        if cfg.link.import_lib:
            cmd.append(self.import_lib(cfg.link.import_lib))

        cmd.extend(cfg.link.options)
    
        return " ".join(cmd)
    
    # def convert_compile_group(self, compile_group: Compile):
    #     pass
                
    def convert_includes(self, include_paths: list) -> list:
        converted_paths = []
        [converted_paths.append(f"{self._char_inc_dir}\"{os.path.abspath(path)}\"") for path in include_paths]
        return converted_paths
    
    @staticmethod
    def convert_char(char: str, items: list) -> list:
        converted_paths = []
        [converted_paths.append(f"{char}{item}") for item in items]
        return converted_paths
    
    @staticmethod
    def convert_char_abs(char: str, items: list) -> list:
        converted_paths = []
        [converted_paths.append(f"{char}\"{os.path.abspath(item)}\"") for item in items]
        return converted_paths
    
    @staticmethod
    def convert_char_basename(char: str, items: list) -> list:
        converted_paths = []
        [converted_paths.append(f"{char}{os.path.basename(item)}") for item in items]
        return converted_paths
        
    def convert_defines(self, defines: list) -> list:
        return self.convert_char(self._char_define, defines)
        
    def lib_dirs(self, dirs: list) -> list:
        return self.convert_char_abs("/LIBPATH:" if self.mode == Mode.MSVC else "-L ", dirs)
        
    def libs(self, libs: list) -> list:
        return self.convert_char("" if self.mode == Mode.MSVC else "-l ", libs)
    
    def ignore_libs(self, libs: list) -> str:
        if not libs:
            return ""

        if self.mode == Mode.GCC:  # maybe clang as well?
            return "--exclude-libs," + ",".join(libs)
        
        if self.mode == Mode.MSVC:
            return " ".join(self.convert_char("/NODEFAULTLIB:", libs))
        
        return ""
    
    def import_lib(self, lib: str) -> str:
        if not lib:
            return ""
        
        if self.mode == Mode.MSVC:
            return f"/IMPLIB:\"{os.path.abspath(os.path.splitext(lib)[0])}.lib\""
        
        # does clang or gcc have an import library option?
        
        return ""
    
    def output_file(self, path: str) -> str:
        if not path:
            return ""
        
        if self.mode == Mode.MSVC:
            return f"/OUT:\"{path}\""
        
        return ""
    
    def debug_file(self, path: str) -> str:
        if not path:
            return ""
        
        if self.mode == Mode.MSVC:
            return f"/PDB:\"{path}\""
        
        return ""
    
    def get_pch_all(self, pch: PrecompiledHeader, pch_file: str, pch_out: str,
                    backup_file: str = None, backup_out: str = None) -> list:
        """returns all pch settings, (pch create/use, pch file, and pch out)"""
        pch_list = []
        
        if pch and pch != PrecompiledHeader.NONE:
            if pch_file:
                pch_list.append(self.get_pch(pch, pch_file))
            elif backup_file:
                pch_list.append(self.get_pch(pch, backup_file))
            
        if pch_out:
            pch_list.append(self.get_pch_out(pch_out))
        elif backup_out:
            pch_list.append(self.get_pch_out(backup_out))
        
        return pch_list
    
    def get_pch(self, pch: PrecompiledHeader, path: str) -> str:
        if pch == PrecompiledHeader.USE:
            if self.mode == Mode.MSVC:
                return f"/Yu\"{path}\""
            elif self.mode == Mode.CLANG:
                return f"-include-pch \"{path}\""
            
        if pch == PrecompiledHeader.CREATE:
            if self.mode == Mode.MSVC:
                return f"/Yc\"{path}\""
            elif self.mode == Mode.CLANG:
                return f"-emit-pch \"{path}\""
        
        return ""
    
    def get_pch_out(self, path: str) -> str:
        if not path:
            return ""
    
        if self.mode == Mode.MSVC:
            return f"/Fp\"{os.path.abspath(os.path.splitext(path)[0])}.pch\""
    
        return ""
        
        
# meh
def get_compiler(compiler: str, language: Enum) -> str:
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

