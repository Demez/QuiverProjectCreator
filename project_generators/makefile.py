import sys
import os

# from qpc_args import args
from qpc_base import BaseProjectGenerator, Platform
from qpc_project import Compiler, ConfigType, Language, Project, ProjectPass, Configuration
from qpc_parser import BaseInfo

import qpc_c_parser as cp

header_extensions = [
    'h',
    'hh',
    'hpp',
    'h++',
    'hxx'
]


class MakefileGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("Makefile")
        self._add_platform(Platform.LINUX32)
        self._add_platform(Platform.LINUX64)
        self._add_platform(Platform.MACOS)

    def create_project(self, project: Project) -> None:
        print("Creating: " + project.file_name + ".mak")
        makefile = gen_defines(project.projects[0].config.general.compiler)
        
        for p in project.projects:
            makefile += gen_project_config_definitions(p)
        
        with open(project.file_name + ".mak", "w", encoding="utf-8") as f:
            f.write(makefile)

    def does_project_exist(self, project_out_dir: str) -> bool:
        return os.path.isfile(os.path.splitext(project_out_dir)[0] + ".mak")

    def create_master_file(self, info: BaseInfo, master_file_path: str) -> None:
        # do stuff with info.project_dependencies here
        pass


def make_ifeq(a, b, body) -> str:
    return f"\nifeq ({a},{b})\n{body}\nendif\n"


def gen_cflags(conf: Configuration, libs: bool = True, defs: bool = True, includes: bool = True) -> str:
    mk = ""
    if len(conf.compiler.preprocessor_definitions) > 0 and defs:
        mk += ' -D ' + ' -D '.join(conf.compiler.preprocessor_definitions)
    if len(conf.linker.libraries) > 0 and libs:
        mk += ' -l' + ' -l'.join(['.'.join(i.split('.')[:-1]) for i in conf.linker.libraries])
    if len(conf.general.library_directories) > 0 and libs:
        mk += ' -L' + ' -L'.join(conf.general.library_directories)
    if len(conf.general.include_directories) > 0 and includes:
        mk += ' -I' + ' -I'.join(conf.general.include_directories)
    return mk


# TODO: add a non-gnu flag option (/ instead of --, etc)
def gen_compile_exe(compiler, conf) -> str:
    return f"@{compiler} -o $@ $(SOURCES) {gen_cflags(conf)}"


def gen_compile_dyn(compiler, conf) -> str:
    return f"@{compiler} -shared -fPIC -o $@ $(SOURCES) {gen_cflags(conf)}"


def gen_compile_stat(compiler, conf) -> str:
    return f"@ar rcs $@ $(OBJECTS)"


def gen_project_targets(conf) -> str:
    makefile = "\n\n# TARGETS\n\n"
    target_name = ""
    # theres got to be a better way to do this but im tired
    if conf.linker.output_file:
        target_name = conf.linker.output_file
    else:
        target_name = "$(OUTNAME)"
    
    # compiler = "g++" if conf.general.language == Language.CPP else "gcc"
    sel_compiler = conf.general.compiler
    if sel_compiler in {Compiler.GCC_9, Compiler.GCC_8, Compiler.GCC_7, Compiler.GCC_6}:
        if conf.general.language == Language.CPP:
            compiler = "g++-" + str(sel_compiler.name[-1])
        else:  # assume conf.general.language == Language.C:
            compiler = "gcc-" + str(sel_compiler.name[-1])
    elif sel_compiler in {Compiler.CLANG_9, Compiler.CLANG_8}:
        compiler = "clang-" + str(sel_compiler.name[-1])
    else:
        compiler = "g++"
    
    if conf.general.configuration_type == ConfigType.APPLICATION:
        makefile += f"{target_name}: __PREBUILD $(OBJECTS) $(FILES) __PRELINK\n"
        makefile += f"\t@echo '$(GREEN)Compiling executable {target_name}$(NC)'\n"
        makefile += '\t' + '\n\t'.join(gen_compile_exe(compiler, conf).split('\n'))
    
    elif conf.general.configuration_type == ConfigType.DYNAMIC_LIBRARY:
        makefile += f"$(addsuffix .so,{target_name}): __PREBUILD $(OBJECTS) $(FILES) __PRELINK\n"
        makefile += f"\t@echo '$(CYAN)Compiling dynamic library {target_name + '.so'}$(NC)'\n"
        makefile += '\t' + '\n\t'.join(gen_compile_dyn(compiler, conf).split('\n'))
    
    elif conf.general.configuration_type == ConfigType.STATIC_LIBRARY:
        makefile += f"$(addsuffix .a,{target_name}): __PREBUILD $(OBJECTS) $(FILES) __PRELINK\n"
        makefile += f"\t@echo '$(CYAN)Compiling static library {target_name}.a$(NC)'\n"
        makefile += '\t' + '\n\t'.join(gen_compile_stat(compiler, conf).split('\n'))
    
    makefile += "\n\t" + "\n\t".join(conf.post_build)
    
    return makefile


def gen_dependency_tree(objects, headers, conf: Configuration) -> str:
    makefile = "\n#DEPENDENCY TREE:\n\n"
    pic = ""
    if conf.general.configuration_type == "shared_library":  # shared library is a thing?
        pic = "-fPIC"
    for obj in objects.keys():
        makefile += f"\n{obj}: {objects[obj]} {' '.join(cp.get_includes(objects[obj]))}\n"
        makefile += f"\t@echo '$(CYAN)Building Object {objects[obj]}$(NC)'\n"
        makefile += f"\t@$(COMPILER) -c {pic} -o $@ {objects[obj]} {gen_cflags(conf, libs=False)}\n"
    
    for h in headers:
        makefile += f"\n{h}: {' '.join(cp.get_includes(h))}\n"
    
    return makefile


def gen_clean_target() -> str:
    return f"""
# CLEAN TARGET:

clean:
\t@echo "Cleaning objects, archives, shared objects, and dynamic libs"
\t@rm -f $(wildcard *.o *.a *.so *.dll *.dylib)

.PHONY: clean __PREBUILD __PRELINK __POSTBUILD


"""


def gen_script_targets(conf: Configuration) -> str:
    makefile = "\n\n__PREBUILD:\n"
    makefile += '\t' + '\n\t'.join(conf.pre_build) + "\n\n"
    
    makefile += "\n\n__PRELINK:\n"
    makefile += '\t' + '\n\t'.join(conf.pre_link) + "\n\n"
    
    return makefile


# TODO: less shit name
def gen_project_config_definitions(project: ProjectPass) -> str:
    objects = {}
    project_dir = os.path.split(project.project.project_path)[0]
    for i in project.source_files:
        objects['.'.join(i.split('.')[:-1])
                    .replace('/', '\\/')
                    .replace('..', ('\\.\\.')
                             .replace(' ', '\\ ')) + '.o'] = i
    
    headers = [i for i in project.files if i.split('.')[-1] in header_extensions]
    nonheader_files = [i for i in project.files if i not in headers]
    
    makefile = "\n# SOURCE FILES:\n\n"
    makefile += "SOURCES = " + '\t\\\n\t'.join(project.source_files) + "\n"
    
    makefile += "\n#OBJECTS:\n\n"
    makefile += "OBJECTS = " + '\t\\\n\t'.join(objects.keys()) + "\n"
    
    makefile += "\n# AUX FILES:\n\n"
    makefile += "FILES = " + '\t\\\n\t'.join(nonheader_files) + "\n"
    
    makefile += "\n# MACROS:\n\n"

    if project.config.general.out_name:
        makefile += "OUTNAME = " + project.config.general.out_name
    else:
        makefile += "OUTNAME = " + project.project.file_name
    
    makefile += gen_project_targets(project.config)
    
    makefile += gen_clean_target()
    
    makefile += gen_dependency_tree(objects, headers, project.config)
    # print(project.config)
    
    makefile += gen_script_targets(project.config)
    
    return make_ifeq(project.config_name, "$(CONFIG)",
                     make_ifeq(project.platform, "$(PLATFORM)", makefile))


def get_default_platform() -> str:
    p = sys.platform
    if sys.maxsize > 2 ** 32:
        p += "64"
    else:
        p += "32"
    
    return p


def gen_defines(toolset) -> str:
    if toolset:
        compiler = toolset
    else:
        compiler = "gcc"
    return f"""#!/usr/bin/make -f


# MAKEFILE GENERATED BY QPC
# IF YOU ARE READING THIS AND DID NOT GENERATE THIS FILE WITH QPC,
# IT PROBABLY WILL NOT WORK. DOWNLOAD QPC AND BUILD THE MAKEFILE
# YOURSELF.


# |￣￣￣￣￣￣￣￣|  
# |    make > *    |
# |＿＿＿＿＿＿＿＿|
# (\__/) || 
# (•ㅅ•) || 
# / 　 づ  

# don't mess with this, might break stuff
PLATFORM = {get_default_platform()}
# change the config with CONFIG=[Release,Debug] to make
CONFIG = Debug
# edit this in your QPC script configuration/general/compiler
COMPILER = {compiler}


# COLORS!!!


RED     =\033[0;31m
CYAN    =\033[0;36m
GREEN   =\033[0;32m
NC      =\033[0m

############################
### BEGIN BUILD TARGETS ###
###########################
"""
