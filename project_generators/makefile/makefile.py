import sys
import os
from enum import Enum

from qpc_args import args
import qpc_hash
from project_generators.shared.cmd_line_gen import get_compiler
from qpc_base import BaseProjectGenerator, Platform, Arch, is_arch_64bit
from qpc_project import ConfigType, Language, ProjectContainer, ProjectPass, Configuration
from qpc_parser import BaseInfo
from qpc_logging import warning, error, verbose, print_color, Color

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
        self._add_platforms(Platform.LINUX, Platform.MACOS)
        self._add_architectures(Arch.I386, Arch.AMD64, Arch.ARM, Arch.ARM64)
        self._set_generate_master_file(True)

    def create_project(self, project: ProjectContainer) -> None:
        project_passes = self._get_passes(project)
        if not project_passes:
            return
        
        print_color(Color.CYAN, "Creating: " + project.file_name + MAKEFILE_EXT)
        compiler = get_compiler(project_passes[0].cfg.general.compiler, project_passes[0].cfg.general.language)
        makefile = gen_defines(project, compiler, project.base_info.get_base_info(self._platforms[0]).configs)
        
        for p in project_passes:
            makefile += gen_project_config_definitions(p)
        
        with open(project.file_name + MAKEFILE_EXT, "w", encoding="utf-8") as f:
            f.write(makefile)

    def does_project_exist(self, project_out_dir: str) -> bool:
        return os.path.isfile(os.path.splitext(project_out_dir)[0] + MAKEFILE_EXT)

    def get_master_file_path(self, master_file_path: str) -> str:
        return master_file_path + MAKEFILE_EXT

    def create_master_file(self, info: BaseInfo, master_file_path: str) -> None:
        print_color(Color.CYAN, "Creating Master File: " + master_file_path)

        out_dir_dict = {}
        dependency_dict = {}
        wanted_projects = info.get_projects(Platform.LINUX, Platform.MACOS)
        for project_def in wanted_projects:
            out_dir = qpc_hash.get_out_dir(info.project_hashes[project_def.path])
            if out_dir:
                out_dir_dict[project_def.path] = os.path.relpath(out_dir)
                dependency_dict[project_def.path] = info.project_dependencies[project_def.path]

        # this chooses 64 bit architectures over 32 bit for a default arch
        architecture = None
        for arch in args.archs:
            if arch in self._architectures and not architecture or \
                    is_arch_64bit(arch) and architecture and not is_arch_64bit(architecture):
                architecture = arch

        master_file = f"""#!/usr/bin/make -f

SETTINGS = ARCH={architecture.name.lower()} CONFIG={info.get_configs()[0]}

all:
"""
        # sort dict by most dependencies to least dependencies, 100% a flawed way of doing this
        make_paths, make_files = self.order_dependencies(out_dir_dict, dependency_dict)

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


def make_ifeq(a: str, b: str, body: str) -> str:
    return f"\nifeq ({a},{b})\n{body}\nendif\n"


def make_ifndef(item: str, body: str) -> str:
    return f"\nifndef $({item})\n{body}\nendif\n"


# TODO: move to cmd line gen cleanly
def gen_cflags(conf: Configuration, libs: bool = True, defs: bool = True, includes: bool = True) -> str:
    mk = ""
    if conf.compile.options:
        mk += " " + " ".join(conf.compile.options)
    if conf.link.options:
        mk += " " + " ".join(conf.link.options)
    if conf.compile.defines and defs:
        mk += ' -D ' + ' -D '.join(conf.compile.defines)
    if conf.link.lib_dirs and libs:
        mk += ' -L' + ' -L'.join(conf.link.lib_dirs)
    if conf.link.libs and libs:
        mk += ' -l' + ' -l'.join([os.path.splitext(i)[0] for i in conf.link.libs])
    if conf.compile.inc_dirs and includes:
        mk += ' -I' + ' -I'.join(conf.compile.inc_dirs)


def gen_compile_exe(conf: Configuration) -> str:
    entry = f"-Wl,--entry={conf.link.entry_point}" if conf.link.entry_point != "" else ""
    return f"@$(COMPILER) $(SOURCES) {entry} {gen_cflags(conf)} -o $@"


def gen_compile_dyn(conf: Configuration) -> str:
    return f"@$(COMPILER) -shared -fPIC $(SOURCES) {gen_cflags(conf)} -o $@"


def gen_compile_stat() -> str:
    return f"@ar rcs $@ $(OBJECTS)"


def gen_project_targets(cfg: Configuration) -> str:
    makefile = "\n\n# TARGETS\n\n"
    target_name = cfg.link.output_file if cfg.link.output_file else "$(OUTNAME)"

    # ADD IMPORT LIBRARY OPTION, MAKES A STATIC LIBRARY
    if cfg.link.import_lib and cfg.general.config_type != ConfigType.STATIC_LIB:
        import_library = f"{os.path.splitext(cfg.link.import_lib)[0]}.a"
    else:
        import_library = ""
    
    if cfg.general.config_type == ConfigType.APPLICATION:
        makefile += f"{target_name}: __PREBUILD $(OBJECTS) __PRELINK {import_library}\n"
        makefile += f"\t@echo '$(GREEN)Compiling executable {target_name}$(NC)'\n"
        makefile += '\t' + '\n\t'.join(gen_compile_exe(cfg).split('\n'))
    
    elif cfg.general.config_type == ConfigType.DYNAMIC_LIB:
        makefile += f"$(addsuffix .so,{target_name}): __PREBUILD $(OBJECTS) __PRELINK {import_library}\n"
        makefile += f"\t@echo '$(CYAN)Compiling dynamic library {target_name}.so$(NC)'\n"
        makefile += '\t' + '\n\t'.join(gen_compile_dyn(cfg).split('\n'))
    
    elif cfg.general.config_type == ConfigType.STATIC_LIB:
        makefile += f"$(addsuffix .a,{target_name}): __PREBUILD $(OBJECTS) __PRELINK\n"
        makefile += f"\t@echo '$(CYAN)Compiling static library {target_name}.a$(NC)'\n"
        makefile += '\t' + '\n\t'.join(gen_compile_stat().split('\n'))

    # must be after setting the target above
    if import_library:
        makefile += f"\n\n{import_library}: __PREBUILD $(OBJECTS) __PRELINK\n"
        makefile += f"\t@echo '$(CYAN)Creating import library {import_library}$(NC)'\n"
        makefile += '\t' + '\n\t'.join(gen_compile_stat().split('\n'))

    makefile += "\n\t" + "\n\t".join(cfg.post_build)
    
    return makefile


def gen_dependency_tree(objects, headers, conf: Configuration) -> str:
    makefile = "\n#DEPENDENCY TREE:\n\n"
    pic = "-fPIC"
        
    for obj, path in objects.items():
        makefile += f"\n{obj}: {path}\n"
        makefile += f"\t@echo '$(CYAN)Building Object {path}$(NC)'\n"
        makefile += f"\t@$(COMPILER) -c {pic} {gen_cflags(conf)} {path} -o $@\n"
        
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
    for i in project.source_files:
        objects[project.cfg.general.build_dir + "/" + os.path.splitext(os.path.basename(i))[0] + ".o"] = i
    
    headers = [i for i in project.files if os.path.splitext(i)[1] in header_extensions]

    create_dirs = []
    if project.cfg.link.output_file:
        create_dirs.append(os.path.split(project.cfg.link.output_file)[0])

    if project.cfg.link.output_file:
        makefile = f"\n# CREATE BIN DIR\n$(shell mkdir -p {os.path.split(project.cfg.link.output_file)[0]})\n"
    elif project.cfg.general.out_dir:
        makefile = f"\n# CREATE BIN DIR\n$(shell mkdir -p {project.cfg.general.out_dir})\n"
    else:
        makefile = ""

    makefile += f"\n# CREATE BUILD DIR\n$(shell mkdir -p {project.cfg.general.build_dir})\n"
    
    makefile += "\n# SOURCE FILES:\n\n"
    makefile += "SOURCES = " + '\t\\\n\t'.join(project.source_files) + "\n"
    
    makefile += "\n#OBJECTS:\n\n"
    makefile += "OBJECTS = " + '\t\\\n\t'.join(objects.keys()) + "\n"
    
    makefile += "\n# MACROS:\n\n"

    makefile += "OUTNAME = "
    makefile += project.cfg.general.out_name if project.cfg.general.out_name else project.container.file_name
    
    makefile += gen_project_targets(project.cfg)
    
    makefile += gen_clean_target()
    
    makefile += gen_dependency_tree(objects, headers, project.cfg)
    
    makefile += gen_script_targets(project.cfg)
    
    return make_ifeq(project.cfg_name, "$(CONFIG)", make_ifeq(project.arch.name.lower(), "$(ARCH)", makefile))


def get_default_platform(project: ProjectContainer) -> str:
    archs = project.get_archs()
    # prefer 64 bit archs over 32 bit
    if Arch.AMD64 in archs:
        return "amd64"
    if Arch.ARM64 in archs:
        return "arm64"
    else:
        return archs[0].name.lower()


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
<<<<<<< HEAD
ARCH = {get_default_platform(project)}
# change the cfg with CONFIG=[{','.join(configs)}] to make
CONFIG = {configs[0]}
=======
{make_ifndef("ARCH", 'ARCH = ' + get_default_platform(project))}
# change the config with CONFIG=[{','.join(configs)}] to make
{make_ifndef("CONFIG", 'CONFIG = ' + configs[0])}
>>>>>>> d555b7101e40f6dcdb99cf1716d0c4f462bfd7f4
# edit this in your QPC script configuration/general/compiler
{make_ifndef("COMPILER", 'COMPILER = ' + compiler)}


# COLORS!!!


RED     =\033[0;31m
CYAN    =\033[0;36m
GREEN   =\033[0;32m
NC      =\033[0m

############################
### BEGIN BUILD TARGETS ###
###########################
"""
