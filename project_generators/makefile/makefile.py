import sys
import os
from enum import Enum

# from qpc_args import args
import qpc_hash
from qpc_base import BaseProjectGenerator, Platform
from qpc_project import Compiler, ConfigType, Language, ProjectContainer, ProjectPass, Configuration
from qpc_parser import BaseInfo

import qpc_c_parser as cp

header_extensions = {
    'h',
    'hh',
    'hpp',
    'h++',
    'hxx'
}


MAKEFILE_EXT = ".mak"


class MakefileGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("Makefile")
        self._add_platform(Platform.LINUX32)
        self._add_platform(Platform.LINUX64)
        self._add_platform(Platform.MACOS)
        self._set_generate_master_file(True)

    def create_project(self, project: ProjectContainer) -> None:
        project_passes = self._get_passes(project)
        if not project_passes:
            return
        
        print("Creating: " + project.file_name + MAKEFILE_EXT)
        compiler = get_compiler(project_passes[0].config.general.compiler,
                                project_passes[0].config.general.language)
        makefile = gen_defines(project, compiler, project.base_info.get_base_info(self._platforms[0]).configurations)
        
        for p in project_passes:
            makefile += gen_project_config_definitions(p)
        
        with open(project.file_name + MAKEFILE_EXT, "w", encoding="utf-8") as f:
            f.write(makefile)

    def does_project_exist(self, project_out_dir: str) -> bool:
        return os.path.isfile(os.path.splitext(project_out_dir)[0] + MAKEFILE_EXT)

    def get_master_file_path(self, master_file_path: str) -> str:
        return master_file_path + MAKEFILE_EXT

    def create_master_file(self, info: BaseInfo, master_file_path: str, platform_dict: dict) -> None:
        print("Creating Master File: " + master_file_path)

        out_dir_dict = {}
        for qpc_path, hash_path in info.project_hashes.items():
            out_dir_dict[qpc_path] = os.path.relpath(qpc_hash.get_out_dir(hash_path))

        # why
        platform = None
        for plat in [i for v in platform_dict.values() for i in v]:
            if plat in self._platforms and not platform or \
                    plat.name.endswith("64") and platform and platform.name.endswith("32"):
                platform = plat

        master_file = f"""#!/usr/bin/make -f

SETTINGS = PLATFORM={platform.name.lower()} CONFIG={info.get_configs()[0]}

all:
"""
        # sort dict by most dependencies to least dependencies, 100% a flawed way of doing this
        make_paths, make_files = self.order_dependencies(out_dir_dict, info.project_dependencies)

        for index, path in enumerate(make_paths):
            master_file += f"\tmake -C {path} -f {make_files[index]} $(SETTINGS)\n"

        with open(master_file_path, "w") as master_file_w:
            master_file_w.write(master_file + "\n")
    
    def does_master_file_exist(self, master_file_path: str) -> bool:
        return True

    def order_dependencies(self, out_dir_dict: dict, dependency_dict: dict) -> tuple:
        sorted_scripts = self.topological_sort(list(out_dir_dict.keys()), dependency_dict)
        # completely avoids removing duplicate paths or file names, like if it was in a dict, no duplicate keys
        make_paths, make_files = [], []
        for script_path in sorted_scripts:
            make_paths.append(out_dir_dict[script_path])
            make_files.append(os.path.splitext(os.path.basename(script_path))[0] + MAKEFILE_EXT)
        return (make_paths, make_files)

    # https://www.geeksforgeeks.org/python-program-for-topological-sorting/
    def topological_sort(self, script_list: list, dependency_dict: dict):
        # Mark all the vertices as not visited
        visited = {}
        [visited.update({script_path: False}) for script_path in script_list]
        stack = []

        # Call the recursive helper function to store Topological
        # Sort starting from all projects one by one
        for i in dependency_dict:
            if not visited[i]:
                self.topological_sort_util(dependency_dict, i, visited, stack)
        return stack

    def topological_sort_util(self, dependency_dict: dict, v, visited, stack):
        # Mark the current node as visited.
        visited[v] = True

        # Recur for all the projects adjacent to this project
        for i in dependency_dict[v]:
            try:
                if not visited[i]:
                    self.topological_sort_util(dependency_dict, i, visited, stack)
            except KeyError as F:
                pass  # project probably wasn't added to be generated

        # Push current project to stack which stores result
        stack.append(v)


def make_ifeq(a, b, body) -> str:
    return f"\nifeq ({a},{b})\n{body}\nendif\n"


def gen_cflags(conf: Configuration, libs: bool = True, defs: bool = True, includes: bool = True) -> str:
    mk = ""
    if conf.compiler.options:
        mk += " " + " ".join(conf.compiler.options)
    if conf.linker.options:
        mk += " " + " ".join(conf.linker.options)
    if conf.compiler.preprocessor_definitions and defs:
        mk += ' -D ' + ' -D '.join(conf.compiler.preprocessor_definitions)
    if conf.linker.libraries and libs:
        mk += ' -l' + ' -l'.join(['.'.join(i.split('.')[:-1]) for i in conf.linker.libraries])
    if conf.general.library_directories and libs:
        mk += ' -L' + ' -L'.join(conf.general.library_directories)
    if conf.general.include_directories and includes:
        mk += ' -I' + ' -I'.join(conf.general.include_directories)
    return mk


# TODO: add a non-gnu flag option (/ instead of --, etc)
def gen_compile_exe(compiler: str, conf: Configuration) -> str:
    entry = f"-Wl,--entry={conf.linker.entry_point}" if conf.linker.entry_point != "" else ""
    return f"@{compiler} -o $@ $(SOURCES) {entry} {gen_cflags(conf)}"


def gen_compile_dyn(compiler: str, conf: Configuration) -> str:
    return f"@{compiler} -shared -fPIC -o $@ $(SOURCES) {gen_cflags(conf)}"


def gen_compile_stat(compiler: str, conf: Configuration) -> str:
    return f"@ar rcs $@ $(OBJECTS)"


def gen_project_targets(conf) -> str:
    makefile = "\n\n# TARGETS\n\n"
    target_name = conf.linker.output_file if conf.linker.output_file else "$(OUTNAME)"
    
    # compiler = "g++" if conf.general.language == Language.CPP else "gcc"
    compiler = get_compiler(conf.general.compiler, conf.general.language)
    
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
        
    for obj, path in objects.items():
        makefile += f"\n{obj}: {path} {' '.join(cp.get_includes(path, conf.general.include_directories, headers))}\n"
        makefile += f"\t@echo '$(CYAN)Building Object {path}$(NC)'\n"
        makefile += f"\t@$(COMPILER) -c {pic} -o $@ {path} {gen_cflags(conf, libs=False)}\n"
    
    for h in headers:
        makefile += f"\n{h}: {' '.join(cp.get_includes(h, conf.general.include_directories, headers))}\n"
    
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
    build_dir = project.config.general.build_dir if project.config.general.build_dir else "build"
    for i in project.source_files:
        objects[build_dir + "/" + '.'.join(
            i.split('.')[:-1]).replace('/', '\\/').replace('..', ('\\.\\.').replace(' ', '\\ ')) + '.o'] = i
    
    headers = [i for i in project.files if i.split('.')[-1] in header_extensions]
    nonheader_files = [i for i in project.files if i not in headers]

    create_dirs = []
    if project.config.linker.output_file:
        create_dirs.append(os.path.split(project.config.linker.output_file)[0])

    if project.config.linker.output_file:
        makefile = f"\n# CREATE BIN DIR\n$(shell mkdir -p {os.path.split(project.config.linker.output_file)[0]})\n"
    elif project.config.general.out_dir:
        makefile = f"\n# CREATE BIN DIR\n$(shell mkdir -p {project.config.general.out_dir})\n"
    else:
        makefile = ""

    if build_dir:
        makefile += f"\n# CREATE BUILD DIR\n$(shell mkdir -p {build_dir})\n"
    
    makefile += "\n# SOURCE FILES:\n\n"
    makefile += "SOURCES = " + '\t\\\n\t'.join(project.source_files) + "\n"
    
    makefile += "\n#OBJECTS:\n\n"
    makefile += "OBJECTS = " + '\t\\\n\t'.join(objects.keys()) + "\n"
    
    makefile += "\n# AUX FILES:\n\n"
    makefile += "FILES = " + '\t\\\n\t'.join(nonheader_files) + "\n"
    
    makefile += "\n# MACROS:\n\n"

    makefile += "OUTNAME = "
    makefile += project.config.general.out_name if project.config.general.out_name else project.project.file_name
    
    makefile += gen_project_targets(project.config)
    
    makefile += gen_clean_target()
    
    makefile += gen_dependency_tree(objects, headers, project.config)
    # print(project.config)
    
    makefile += gen_script_targets(project.config)
    
    return make_ifeq(project.config_name, "$(CONFIG)",
                     make_ifeq(project.platform.name.lower(), "$(PLATFORM)", makefile))


def get_default_platform(project: ProjectContainer) -> str:
    platforms = project.get_platforms()
    if Platform.LINUX64 in platforms:
        return "linux64"
    else:
        return platforms[0].name.lower()


def get_compiler(compiler: Enum, language: Enum) -> str:
    if compiler in {Compiler.GCC_9, Compiler.GCC_8, Compiler.GCC_7, Compiler.GCC_6}:
        if language == Language.CPP:
            return "g++-" + str(compiler.name[-1])
        else:  # assuming language == Language.C:
            return "gcc-" + str(compiler.name[-1])
    elif compiler in {Compiler.CLANG_9, Compiler.CLANG_8}:
        return "clang-" + str(compiler.name[-1])
    return "g++"


def gen_defines(project: ProjectContainer, compiler: str, configs: list) -> str:
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
PLATFORM = {get_default_platform(project)}
# change the config with CONFIG=[{','.join(configs)}] to make
CONFIG = {configs[0]}
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
