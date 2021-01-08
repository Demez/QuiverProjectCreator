import os

from qpc_args import args
from qpc_base import BaseProjectGenerator, Platform, Arch, is_arch_64bit
from qpc_project import ConfigType, Language, ProjectContainer, ProjectPass, Standard
from qpc_parser import BaseInfo, BaseInfoPlatform
from qpc_logging import warning, error, verbose, print_color, Color
from ..shared import cmd_line_gen, msvc_tools
from typing import List


DICT_QT_ARCH = {
    Arch.AMD64:     "x86_64",
    Arch.I386:      "i386",
    Arch.ARM64:     "arm64",
    Arch.ARM:       "arm",
}


DICT_QT_PLAT = {
    Platform.WINDOWS:       "win32",
    Platform.LINUX:         "unix:!macx",
    Platform.MACOS:         "macx",
}

    
def gen_qpc_cond_ex(cfg: str, all_cfgs: list, plat: Platform, arch: Arch):
    # : is logical AND
    # CONFIG(debug, debug|release)
    return f"CONFIG({cfg.lower()}, {'|'.join(all_cfgs)}):{DICT_QT_PLAT[plat]}:equals(QT_ARCH, {DICT_QT_ARCH[arch]})"


def gen_qpc_cond(proj: ProjectPass):
    cfgs = [cfg.lower() for cfg in proj.container.get_cfgs()]
    return gen_qpc_cond_ex(proj.cfg_name, cfgs, proj.platform, proj.arch)


class QTGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("QT Generator")
        self._add_platforms(Platform.WINDOWS, Platform.LINUX, Platform.MACOS)
        self._set_generate_master_file(False)
        self._set_macro("GEN_QT")

        self.cmd_gen = cmd_line_gen.CommandLineGen()

    def does_project_exist(self, project_out_dir: str) -> bool:
        split_ext_path = os.path.splitext(project_out_dir)[0]
        if os.path.isfile(split_ext_path + ".pro"):
            verbose(f"File Exists: {split_ext_path}.pro")
            return True
        return False

    def create_project(self, project: ProjectContainer) -> None:
        # TODO: for some reason, qt creator doesn't want to make a new directory for out_dir/DESTDIR
        
        project_passes: List[ProjectPass] = self._get_passes(project)
        if not project_passes:
            return

        print_color(Color.CYAN, "QT Project Generator Running on " + project.file_name)

        proj_file = ""
                
        for i, proj in enumerate(project_passes):
            condition = gen_qpc_cond(proj)
            proj_file += f"{condition} {{\n\tmessage(type: {condition})\n\t\n"
            proj_file += self.handle_pass(proj)
            proj_file += "}\n\n"
        
        with open(project.file_name + ".pro", "w", encoding="utf8") as proj_io:
            proj_io.write(proj_file)
                
    def handle_pass(self, proj: ProjectPass) -> str:
        self.cmd_gen.set_mode(proj.cfg.general.compiler)
        
        qproj = ""
        
        qt_libs = []
        for lib in proj.cfg.link.libs:
            if get_qt_lib(lib):
                qt_libs.append(get_qt_lib(lib))
            
        qproj += gen_list("QT", *qt_libs)

        # also has staticlib on the wiki?
        if proj.cfg.general.config_type == ConfigType.APPLICATION:
            qproj += "\tTEMPLATE = app\n\n"
        elif proj.cfg.general.config_type == ConfigType.STATIC_LIB:
            qproj += "\tTEMPLATE = staticlib\n\n"
        else:
            qproj += "\tTEMPLATE = lib\n\n"

        qproj += "\t# Qt Creator doesn't want to make a new directory if this doesn't exist, fun\n"
        qproj += f"\t# DESTDIR = {proj.cfg.general.out_dir}\n\n"

        qproj += gen_list("SOURCES", *pathlist(list(proj.source_files)))
        qproj += gen_list("HEADERS", *pathlist(list(proj.get_headers())))

        qproj += gen_list("INCLUDEPATH", *pathlist(proj.cfg.compile.inc_dirs))
        qproj += gen_list("DEFINES", *proj.cfg.compile.defines)
        
        # little hack to remove UNICODE from this unless the user wants unicode
        if "_UNICODE" not in proj.cfg.compile.defines or "UNICODE" not in proj.cfg.compile.defines:
            qproj += gen_rm_list("DEFINES", "_UNICODE", "UNICODE")
        
        libs = []
        libs.extend(self.cmd_gen.lib_dirs(proj.cfg.link.lib_dirs))
        for lib in proj.cfg.link.libs:
            if get_qt_lib(lib) == "":
                libs.append(lib)
                
        qproj += gen_list("LIBS", *libs)
        
        if proj.cfg.general.language == Language.CPP:
            qproj += gen_list("QMAKE_CXXFLAGS", *proj.cfg.compile.options)
        else:
            qproj += gen_list("QMAKE_CFLAGS", *proj.cfg.compile.options)
        
        config = [
            get_c_ver(proj.cfg.general.standard),
        ]

        qproj += gen_list("CONFIG", *config)
        
        # another hack, cool
        # if proj.cfg.general.standard != Standard.CPP11:
        #     qproj += gen_rm_list("CONFIG", "c++11")
        
        # TODO:
        #  - linker options
        #  - import library
        #  - ignore libs
        #  - output path
        #  - output name
        #  - compiler (can i even do this without the pro.user file?)
        
        return qproj
    
    
def get_c_ver(lang: Standard) -> str:
    if lang.name.startswith("CPP"):
        return lang.name.replace("CPP", "c++")
    else:
        return lang.name.lower()
    

# TODO: unfinished
#  also is this even needed actually?
def get_qt_lib(lib: str) -> str:
    if "Qt5Widgets" in lib:
        return "widgets"
    elif "Qt5Core" in lib:
        return "core"
    elif "Qt5Gui" in lib:
        return "gui"
    elif "Qt5WinExtras" in lib:
        return "winextras"
    return ""


def gen_list(var: str, *args) -> str:
    return f"\t{var} += \\\n\t\t" + " \\\n\t\t".join(args) + "\n\n"


def gen_rm_list(var: str, *args) -> str:
    return f"\t{var} -= \\\n\t\t" + " \\\n\t\t".join(args) + "\n\n"
    
    
def q_path(path: str) -> str:
    return f"\"{path}\"".replace("\\", "/")
    
    
def pathlist(paths: list) -> list:
    return [q_path(path) for path in paths]

