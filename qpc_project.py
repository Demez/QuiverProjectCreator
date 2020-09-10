# Parses Project Scripts, Base Scripts, Definition Files, and Hash Files

# TODO: figure out what is $CRCCHECK is
# may need to add a /checkfiles launch option to have this check if a file exists or not
# it would probably slow it down as well

import os
import glob
import qpc_hash
from qpc_reader import solve_condition, read_file, QPCBlock
from qpc_args import args, get_arg_macros
from qpc_base import posix_path, norm_path, Platform, Arch, PLATFORM_ARCHS, check_file_path_glob
from qpc_logging import warning, error, verbose, verbose_color, print_color, Color
from enum import EnumMeta, Enum, auto
from time import perf_counter
from typing import List, Dict
import re


# IDEA: be able to reference values from the configuration, like a macro
# so lets say you set output directory in the configuration,
# and you don't want to make that a macro just to use that somewhere else.
# so, you do something like this instead: @cfg.general.out_dir
# this would use the value of out_dir in the configuration
# if it's invalid, just return None, or an empty string


EXTS_C = {".cpp", ".cxx", ".c", ".cc"}
REMOVE_MACROS = re.compile(r"\$\w+\$")


# maybe move to qpc_base with the other Enums?
class ConfigType(Enum):
    STATIC_LIB = auto()
    DYNAMIC_LIB = auto()  # could be SHARED_LIBRARY
    APPLICATION = auto()  # IDEA: rename all application stuff to executable?


class PrecompiledHeader(Enum):
    NONE = auto()
    CREATE = auto()
    USE = auto()


class Language(Enum):
    CPP = auto()
    C = auto()


class Standard(Enum):
    CPP20 = auto()
    CPP17 = auto()
    CPP14 = auto()
    CPP11 = auto()
    CPP03 = auto()
    CPP98 = auto()
    
    C11 = auto()
    C99 = auto()
    C95 = auto()
    C90 = auto()
    C89 = auto()
    
    
class BaseInfoProject:
    # info is BaseInfo from qpc_parser.py
    def __init__(self, info, name: str):
        self.name = name
        self.info = info


class ProjectDefinition(BaseInfoProject):
    def __init__(self, info, project_name: str):
        super().__init__(info, project_name)
        self.path = ""  # path relative to the actual root directory
        self.path_real = ""  # original path in the base file
        self.platforms = set()


class ProjectGroup(BaseInfoProject):
    def __init__(self, info, group_name):
        super().__init__(info, group_name)
        # dict keeps order, set doesn't as of 3.8, both faster than lists
        self.projects = dict()
        self._contains = dict()

    def add_project(self, project_name: str, folder_list: List[str]) -> None:
        self.projects[project_name] = tuple(folder_list)

    # group: ProjectGroup
    def contains_group(self, group, folder_list: List[str]):
        self._contains[group] = folder_list.copy()
            
    def finished(self):
        for group, group_folder in self._contains.items():
            group.finished()
            for project, folder in group.projects.items():
                self.add_project(project, [*group_folder, *folder])


class SourceFile:
    def __init__(self, folder_list: list):
        self.folder = "/".join(folder_list)
        self.compiler = SourceFileCompile()


class ProjectPass:
    # container is ProjectContainer, below this class
    def __init__(self, container, config: str, platform: Platform, arch: Arch, gen_macro: str, gen_id: int):
        self.cfg_name: str = config
        self.platform: Platform = platform
        self.arch: Arch = arch
        self.base_info = container.base_info.get_base_info(platform)
        
        self.container: ProjectContainer = container
        self.cfg: Configuration = Configuration(self)
        self.source_files: Dict[str, SourceFile] = {}
        self.files: Dict[str, str] = {}
        self.hash_list: Dict[str, str] = {}
        self._glob_files: set = set()
        self.build_events: Dict[str, BuildEvent] = {}

        self.macros: Dict[str, str] = {
            **container.macros,
            **self.base_info.macros,
            
            config.upper():   "1",  # this doesn't have to be uppercase, but it's mainly for consistency
            platform.name:    "1",
            arch.name:        "1",
            
            "CONFIG":              config,
            "PLATFORM":            platform.name,
            "ARCH":                arch.name,
        }
        
        self.generators = set()
        self.add_generator(gen_macro, gen_id)
        
    def check_pass(self, config: str, platform: Platform, arch: Arch, generator_macro: str, gen_id: int) -> bool:
        # is this even setup right?
        if self.cfg_name == config and self.platform == platform and self.arch == arch and gen_id in self.generators:
            self.add_generator(generator_macro, gen_id)
            return True
        return False
    
    def add_generator(self, gen_macro: str, gen_id: int):
        self.generators.add(gen_id)
        if gen_macro:
            self.macros.update({gen_macro: "1"})

    def _convert_dependency_path(self, key: str) -> str:
        return self.base_info.get_dependency_path(key)
    
    def add_macro(self, indent: str, macro_name: str, macro_value: str = "") -> None:
        if macro_value:
            self._set_macro(indent, macro_name, macro_value)
        elif macro_name not in self.macros:
            self._set_macro(indent, macro_name)
            
    def _set_macro(self, indent: str, macro_name: str, macro_value: str = ""):
        self.macros[macro_name] = macro_value
        verbose_color(Color.DGREEN, f"{indent}    Set Macro: {macro_name} = \"{self.macros[macro_name]}\"")
        self._replace_undefined_macros(indent)

    def _replace_undefined_macros(self, indent: str) -> None:
        # this could probably be sped up
        # TODO: add scanning of files and certain cfg info
        for macro, value in self.macros.items():
            if args.verbose:
                old_value = self.macros[macro]
                self.macros[macro] = replace_macros(value, self.macros)
                if old_value != self.macros[macro]:
                    verbose_color(Color.GREEN,
                                  f"{indent}    Updated Macro: {macro} - \"{old_value}\" -> \"{self.macros[macro]}\"")
            else:
                self.macros[macro] = replace_macros(value, self.macros)
            
    def replace_macros(self, string: str) -> str:
        return replace_macros(string, self.macros)
        
    def replace_macros_list(self, *values) -> list:
        return replace_macros_list(self.macros, *values)
    
    def add_file(self, folder_list: list, file_block: QPCBlock) -> None:
        for file_path in file_block.get_list():
            file_path = self.replace_macros(file_path)
            if check_file_path_glob(file_path):
                self._add_file_glob(folder_list, file_path, file_block)
            else:
                self._add_file_internal(folder_list, file_path, file_block)
    
    def remove_file(self, folder_list: list, file_block: QPCBlock) -> None:
        for file_path in file_block.values:
            file_path = self.replace_macros(file_path)

            if check_file_path_glob(file_path):
                self._remove_file_glob(folder_list, file_path, file_block)
            else:
                self._remove_file_internal(folder_list, file_path, file_block)

    def _add_file_glob(self, folder_list: list, file_path: str, file_block: QPCBlock) -> None:
        self._glob_files.add(file_path)
        [self._add_file_internal(folder_list, found_file, file_block) for found_file in glob.glob(file_path)]

    def _remove_file_glob(self, folder_list: list, file_path: str, file_block: QPCBlock) -> None:
        self._glob_files.add(file_path)
        [self._remove_file_internal(folder_list, found_file, file_block) for found_file in glob.glob(file_path)]

    def _add_file_internal(self, folder_list: list, file_path: str, file_block: QPCBlock):
        build = file_block.get_item("build")
        force_src_file = build and build.solve_condition(self.macros) and build.values and build.values[0] == "true"
        if force_src_file or os.path.splitext(file_path)[1] in EXTS_C:
            if not self._check_file_added(file_path, file_block, self.source_files):
                self.source_files[file_path] = SourceFile(folder_list)
        elif not self._check_file_added(file_path, file_block, self.files):
            self.files[file_path] = "/".join(folder_list)

    @staticmethod
    def _check_file_added(file_path: str, file_block: QPCBlock, file_dict: dict) -> bool:
        if file_path in file_dict:
            file_block.warning("File already added: " + file_path)
            return True
        else:
            return not check_if_file_exists(file_path, file_block.warning)
                
    def _remove_file_internal(self, folder_list: list, file_path: str, file_block: QPCBlock):
        if os.path.splitext(file_path)[1] in EXTS_C:
            if file_path in self.source_files:
                del self.source_files[file_path]
            else:
                file_block.warning(f"Trying to remove a file that isn't added: \"{file_path}\"")
        else:
            if file_path in self.files:
                del self.files[file_path]
            else:
                file_block.warning(f"Trying to remove a file that isn't added: \"{file_path}\"")

    def add_dependency(self, qpc_path: str) -> None:
        self.container.add_dependency(replace_macros(self._convert_dependency_path(qpc_path), self.macros))

    def remove_dependency(self, qpc_path: str) -> None:
        self.container.remove_dependency(replace_macros(self._convert_dependency_path(qpc_path), self.macros))

    def add_dependencies(self, *qpc_paths) -> None:
        [self.add_dependency(qpc_path) for qpc_path in qpc_paths]
    
    def remove_dependencies(self, *qpc_paths) -> None:
        [self.remove_dependency(qpc_path) for qpc_path in qpc_paths]

    # used in parsing
    def _parse_files(self, files_block: QPCBlock, folder_list: list) -> None:
        if files_block.solve_condition(self.macros):
            for block in files_block.items:
                if not block.solve_condition(self.macros):
                    continue
            
                if block.key == "folder":
                    folder_list.append(block.values[0])
                    self._parse_files(block, folder_list)
                    folder_list.remove(block.values[0])
                elif block.key == "-":
                    self.remove_file(folder_list, block)
                else:
                    self.add_file(folder_list, block)
                
                    if block.items:
                        for file_path in block.get_list():
                            if check_file_path_glob(file_path):
                                [self.parse_source_file(block, found_file) for found_file in glob.glob(file_path)]
                            else:
                                self.parse_source_file(block, file_path)

    def parse_source_file(self, files_block: QPCBlock, file_path: str):
        source_file = self.get_source_file(file_path)
        if not source_file:
            return
    
        for config_block in files_block.items:
            if config_block.solve_condition(self.macros):
            
                if config_block.key == "configuration":
                    for group_block in config_block.items:
                        if group_block.key != "compile":
                            group_block.error("Invalid Group, can only use compile")
                            continue
                    
                        if group_block.solve_condition(self.macros):
                            for option_block in group_block.items:
                                if option_block.solve_condition(self.macros):
                                    source_file.compiler.parse_option(self.macros, option_block)
                else:
                    # new, cleaner way, just assume it's compiler
                    source_file.compiler.parse_option(self.macros, config_block)
        
    def is_build_event_defined(self, name: str):
        return name in self.build_events
    
    # below is stuff for generators to use
    
    # Gets every single folder in the project, splitting each one as well
    # this function is awful
    def get_editor_folders(self, sep: str = "/") -> set:
        folder_paths = set()
        # TODO: is there a better way to do this?
        [folder_paths.add(file_path) for file_path in self.files.values()]
        [folder_paths.add(sf.folder) for sf in self.source_files.values()]
        
        full_folder_paths = set()
        # split every single folder because visual studio bad
        for folder_path in folder_paths:
            current_path = list(folder_path.split("/"))
            if not current_path or not current_path[0]:
                continue
            folder_list = [current_path[0]]
            del current_path[0]
            for folder in current_path:
                folder_list.append(folder_list[-1] + sep + folder)
            full_folder_paths.update(folder_list)
        
        return full_folder_paths
    
    def get_folders(self) -> set:
        folder_paths = split_folders(self.files)
        folder_paths.update(split_folders(self.source_files))
        return folder_paths
    
    def get_files_in_folder(self, folder_path: str) -> list:
        file_list = []
        
        # maybe change to startswith, so you can get stuff in nested folders as well?
        for file_path, file_folder in self.files.items():
            if file_folder == folder_path:
                file_list.append(file_path)
        
        for file_path, file_folder in self.source_files.items():
            if file_folder == folder_path:
                file_list.append(file_path)
        
        return file_list
    
    def get_file_folder(self, file_path) -> str:
        file_path = self.replace_macros(file_path)
        if file_path in self.files:
            return self.files[file_path]
        return ""
    
    def get_source_file(self, file_path) -> SourceFile:
        file_path = self.replace_macros(file_path)
        if file_path in self.source_files:
            return self.source_files[file_path]
        
    def get_glob_files(self) -> set:
        return self._glob_files
    
    def get_headers(self) -> list:
        headers = []
        for file in self.files:
            if os.path.splitext(file)[1] in {".h", ".hh", ".hxx", ".hpp"}:
                headers.append(file)
        return headers


class ProjectContainer:
    # base_info is BaseInfo from qpc_parser.py
    def __init__(self, name: str, project_path: str, base_info, project_def: ProjectDefinition, generator_list: list):
        self.file_name = name  # the actual file name
        self.project_path = project_path  # should use the macro instead tbh, might remove
        self.out_dir = os.path.split(project_path)[0]
        self.hash_dict: Dict[str, str] = {}
        self.base_info = base_info
        
        # self.dependency_convert = dependency_dict
        self.dependencies = set()
        # shared across configs, used as a base for them
        root_dir = "/".join([".."] * len(self.out_dir.split("/")))
        
        self.macros = {
            "PROJECT_NAME": name,
            "PROJECT_DIR": self.out_dir,
            "PROJECT_SCRIPT_NAME": name,
            "ROOT_DIR_ABS": args.root_dir,
            "ROOT_DIR": root_dir,
            
            # changed whenever a script is included
            "SCRIPT_NAME": name,
            "SCRIPT_DIR": self.out_dir,
            
            **get_arg_macros()
        }
        
        self._passes: List[ProjectPass] = []
        generator_macros = {}
        for generator in generator_list:
            generator_macros[generator] = generator.get_macro()

        for generator, macro in generator_macros.items():
            generator_platforms = generator.get_supported_platforms()
            for platform in project_def.platforms:
                if platform in generator_platforms:
                    for config in base_info.get_base_info(platform).configs:
                        for arch in PLATFORM_ARCHS[platform]:
                            if arch in args.archs:
                                self.add_pass(config, platform, arch, macro, generator.id)
        
    def add_pass(self, config: str, plat: Platform, arch: Arch, macro: str, gen_id: int):
        # if not any existing passes without a generator macro
        if not any(proj_pass.check_pass(config, plat, arch, macro, gen_id) for proj_pass in self._passes):
            self._passes.append(ProjectPass(self, config, plat, arch, macro, gen_id))
            
    def get_all_passes(self) -> list:
        return self._passes
            
    def get_passes_platform(self, platforms) -> list:
        return [project_pass for project_pass in self._passes if project_pass.platform in platforms]
        
    def get_passes(self, gen_id: int) -> list:
        return [project_pass for project_pass in self._passes if gen_id in project_pass.generators]

    def get_platforms(self) -> list:
        platforms = set()
        [platforms.add(project_pass.platform) for project_pass in self._passes]
        return list(platforms)

    def get_archs(self) -> list:
        archs = set()
        [archs.add(project_pass.arch) for project_pass in self._passes]
        return list(archs)
    
    def get_hashes(self) -> dict:
        hash_dict = {}
        [hash_dict.update(**project_pass.hash_list) for project_pass in self._passes]
        return hash_dict
    
    def get_glob_files(self) -> list:
        glob_files = set()
        [glob_files.update(project.get_glob_files()) for project in self._passes]
        return list(glob_files)

    @staticmethod
    def _add_dependency_ext(qpc_path: str) -> str:
        if not qpc_path.endswith(".qpc"):
            qpc_path = os.path.splitext(qpc_path)[0] + ".qpc"
        return posix_path(qpc_path)

    def add_dependency(self, qpc_path: str) -> None:
        qpc_path = self._add_dependency_ext(qpc_path)
        if qpc_path != self.project_path:
            self.dependencies.add(qpc_path)

    def remove_dependency(self, qpc_path: str) -> None:
        qpc_path = self._add_dependency_ext(qpc_path)
        if qpc_path in self.dependencies:
            self.dependencies.remove(qpc_path)

    def add_dependencies(self, *qpc_paths) -> None:
        map(self.add_dependency, qpc_paths)
        # [self.add_dependency(qpc_path) for qpc_path in qpc_paths]

    def remove_dependencies(self, *qpc_paths) -> None:
        map(self.remove_dependency, qpc_paths)
        # [self.remove_dependency(qpc_path) for qpc_path in qpc_paths]
    
    def get_editor_folders(self, sep: str = "/") -> set:
        folder_paths = set()
        [folder_paths.update(project.get_editor_folders(sep)) for project in self._passes]
        return folder_paths
    
    def get_folders(self) -> set:
        folder_paths = set()
        [folder_paths.update(project.get_folders()) for project in self._passes]
        return folder_paths

    def get_display_name(self) -> str:
        return self._passes[0].macros["PROJECT_NAME"]

    def get_out_dir(self) -> str:
        out_dir = ""  # os.path.split(project.project_path)[0]
        # TODO: actually test this and see if it works just fine, it should
        '''
        if args.project_dir:
            try:
                out_dir = posix_path(self.projects[0].macros["PROJECT_DIR"])
                # if not out_dir.endswith("/"):
                #    out_dir += "/"
            except KeyError:
                pass
        '''
        return out_dir
    
    def get_all_source_files(self) -> set:
        all_files = set()
        [all_files.update(project.source_files) for project in self._passes]
        return all_files
    
    def get_all_files(self) -> set:
        all_files = set()
        [all_files.update(project.files) for project in self._passes]
        return all_files


class Configuration:
    def __init__(self, project: ProjectPass):
        self._proj: ProjectPass = project
        self._name: str = project.cfg_name
        
        self.debug: Debug = Debug()
        self.general: General = General(self, project.container.file_name, project.platform)
        self.compile: Compile = Compile()
        self.link: Link = Link(self)
        self.pre_build: List[str] = []
        self.pre_link: List[str] = []
        self.post_build: List[str] = []
        
    def get_name(self) -> str:
        return self._name
        
    def add_build_event_options(self, group_block: QPCBlock, option_block: QPCBlock):
        value = replace_macros(option_block.key, self._proj.macros)
        if option_block.values:
            value += " " + replace_macros(" ".join(option_block.values), self._proj.macros)
        if value:
            # TODO: improve this, what if \\n is used in the file? it would just become \ and then new line, awful
            value = value.replace("\\n", "\n")
            self.__dict__[group_block.key].append(value)

    def parse_config_option(self, group: QPCBlock, option: QPCBlock):
        if self.check_build_step(group):
            self.parse_build_step(self.__dict__[group.key], option)
        elif group.key in self.__dict__ and group.key != "_proj":
            self.__dict__[group.key].parse_option(self._proj.macros, option)
        else:
            group.warning("Unknown Configuration Group: ")
            
    @staticmethod
    def check_build_step(group: QPCBlock):
        return group.key in {"pre_build", "pre_link", "post_build"}

    def _parse_build_step_glob(self, step: list, event: QPCBlock, item: QPCBlock, *arg_list):
        event_args = replace_macros_list(self._proj.macros, *arg_list)
        for index, event_macro in enumerate(event_args):
            if check_file_path_glob(event_macro):
                files = glob.glob(event_macro, recursive=True)
                [self._parse_build_step_call(step, event, file) for file in files]
            else:
                self._parse_build_step_call(step, event, event_macro)
            
    def _validate_build_step(self, event_name: str, warning_func: classmethod) -> bool:
        if event_name not in self._proj.build_events:
            warning_func("Undefined build event: " + event_name)
            return False
        return True
        
    def parse_build_step(self, step: list, event: QPCBlock):
        # this kind of sucks
        if event.key == "-":
            if not event.values:
                event.warning("Empty build event name!")
            elif not self._validate_build_step(event.values[0], event.warning):
                return
        else:
            if not self._validate_build_step(event.key, event.warning):
                return
            
        if event.items:
            for value in event.get_items_cond(self._proj.macros):
                self._parse_build_step_glob(step, event, value, *value.get_list())
        else:
            event_args = replace_macros_list(self._proj.macros, *event.values)
            self._parse_build_step_call(step, event, *event_args)
            
    def _parse_build_step_call(self, step: list, event: QPCBlock, *event_macros):
        if event.key != "-":
            self._proj.build_events[event.key].call_event(event.warning, step, *event_macros)
        else:  # this is checked before, don't worry about an exception
            self._proj.build_events[event.values[0]].remove_event(event.warning, step, *event_macros[1:])
            
            
class BaseConfigGroup:
    def remove_item(self, macros: dict, option_block: QPCBlock, item: QPCBlock, name: str):
        for item_to_rm in replace_macros_list(macros, *item.values):
            if item_to_rm in self.__dict__[option_block.key]:
                self.__dict__[option_block.key].remove(item_to_rm)
            else:
                item.warning(f"Trying to remove {name} that was never added: \"{item_to_rm}\"")


# for debug options in the editor used (if it can debug)
class Debug(BaseConfigGroup):
    def __init__(self):
        self.command = ""
        self.arguments = ""
        self.working_dir = ""
        
    def __bool__(self) -> bool:
        return any(self.__dict__.values())

    def parse_option(self, macros: dict, option_block: QPCBlock) -> None:
        if option_block.values:
            if option_block.key == "arguments":
                self.arguments = replace_macros(option_block.values[0], macros)
            elif option_block.key in self.__dict__:
                self.__dict__[option_block.key] = clean_path(option_block.values[0], macros)
            else:
                option_block.warning("Invalid Debug Option: ")


def clean_path(string: str, macros: dict) -> str:
    return posix_path(replace_macros(string, macros))


class General(BaseConfigGroup):
    def __init__(self, config: Configuration, file_name: str, platform: Platform):
        self._config: Configuration = config
        # add the arch here
        default_dir = f"{self._config.get_name()}/f{platform.name.lower()}"
        
        self.out_dir: str = f"out/{default_dir}"
        self.build_dir: str = f"build/{default_dir}"
        
        self.out_name: str = file_name

        # i want to make these configuration options unaffected by cfg and platform macros,
        # and have it run before it goes through each cfg/platform
        # except what if someone sets a macro with a cfg conditional and uses it in one of these?
        # won't work, so im just leaving it as it is for now, hopefully i can get something better later on
        self.config_type: ConfigType = None
        self.language: Language = Language.CPP
        self.standard: Standard = Standard.CPP17
        self.compiler: str = "msvc" if platform == Platform.WINDOWS else "gcc"

        self.options: List[str] = []

    def parse_option(self, macros: dict, option_block: QPCBlock) -> None:
        # notify of moved options
        if option_block.key in {"inc_dirs", "lib_dirs", "include_directories", "library_directories"}:
            if option_block.key in {"inc_dirs", "include_directories"}:
                key = "inc_dirs"
                group = "compile"
            else:
                key = "lib_dirs"
                group = "link"
            
            if option_block.key in {"include_directories", "library_directories"}:
                option_block.warning(f"Option \"{option_block.key}\" has been shortened to \"{key}\" instead")
            
            option_block.warning(f"Option \"{key}\" Moved to \"{group}\" group")
            return
            
        if option_block.key == "options":
            for item in option_block.get_items_cond(macros):
                self.options.extend(replace_macros_list(macros, *item.get_list()))

        if not option_block.values:
            return
        
        if option_block.key in {"out_dir", "build_dir"}:
            self.__dict__[option_block.key] = clean_path(option_block.values[0], macros)
            
        elif option_block.key == "out_name":
            self.out_name = replace_macros(option_block.values[0], macros)
            
        elif option_block.key == "config_type":
            self.set_type(option_block)
        elif option_block.key == "language":
            self.set_language(option_block)
        elif option_block.key == "compiler":
            self.compiler = replace_macros(option_block.values[0], macros)
            
        else:
            option_block.error("Unknown General Option: ")
            
    def set_type(self, option: QPCBlock) -> None:
        self.config_type = convert_enum_option(self.config_type, option, ConfigType)

    def set_language(self, option: QPCBlock) -> None:
        self.set_standard(option)

        value = option.values[0]
        for enum in Language:
            if value.startswith(enum.name.lower()):
                self.language = enum
                break
        else:
            option.invalid_option(
                value,
                *[enum.name.lower() for enum in Language],
                *[enum.name.lower() for enum in Standard]
            )

    def set_standard(self, option: QPCBlock) -> None:
        value = option.values[0]
        for enum in Standard:
            if value == enum.name.lower():
                self.standard = enum
                break


class Compile(BaseConfigGroup):
    def __init__(self):
        self.default_inc_dirs: bool = True
        
        self.pch: PrecompiledHeader = None  # PrecompiledHeader.NONE
        self.pch_file: str = ""
        self.pch_out: str = ""

        self.defines: List[str] = []
        self.inc_dirs: List[str] = []
        self.options: List[str] = []

    def parse_option(self, macros: dict, option_block: QPCBlock) -> None:
        # TODO: allow removing values, surprised it doesn't already allow that
        if option_block.key in {"defines", "options", "inc_dirs"}:
            for item in option_block.get_items_cond(macros):
                if item.key == "-":
                    self.remove_item(macros, option_block, item, option_block.key[:-1])
                else:
                    self.__dict__[option_block.key].extend(replace_macros_list(macros, *item.get_list()))
        
        elif option_block.key == "default_inc_dirs":
            self.default_inc_dirs = convert_bool_option(self.default_inc_dirs, option_block)
    
        elif option_block.key == "pch":
            if option_block.values:
                self.pch = convert_enum_option(self.pch, option_block, PrecompiledHeader)
    
        elif option_block.key in {"pch_file", "pch_out"}:
            self.__dict__[option_block.key] = replace_macros(option_block.values[0], macros)
    
        else:
            option_block.warning("Unknown Compiler Option")
    
    
class SourceFileCompile(Compile):
    def __init__(self):
        super().__init__()
        self.build = True
        
    def parse_option(self, macros: dict, option_block: QPCBlock) -> None:
        if option_block.key == "build":
            self.build = convert_bool_option(self.build, option_block)
        else:
            super().parse_option(macros, option_block)


class Link(BaseConfigGroup):
    def __init__(self, config: Configuration):
        self._parent = config
        self.output_file: str = ""
        self.debug_file: str = ""
        self.import_lib: str = ""
        self.entry_point: str = ""
        
        self.ignore_import_lib: bool = False  # idk what the default should be
        self.default_lib_dirs: bool = True
        
        self.lib_dirs: List[str] = []
        self.libs: List[str] = []
        self.ignore_libs: List[str] = []  # maybe change to ignored_libraries?
        self.options: List[str] = []

    def parse_option(self, macros: dict, option_block: QPCBlock) -> None:
        if option_block.key in {"options", "libs", "lib_dirs", "ignore_libs"}:
            for item in option_block.get_items_cond(macros):
                if item.key == "-":
                    self.remove_item(macros, option_block, item, option_block.key[:-1])
                else:
                    if option_block.key == "libs":
                        self.add_lib(macros, item)
                    else:
                        self.__dict__[option_block.key].extend(replace_macros_list(macros, *item.get_list()))
                    
        elif not option_block.values:
            return
        
        elif option_block.key in {"output_file", "debug_file"}:
            self.__dict__[option_block.key] = clean_path(option_block.values[0], macros)
            
        elif option_block.key in {"import_lib", "entry_point"}:
            # TODO: maybe split the extension for output_file, debug_file, or import_library?
            self.__dict__[option_block.key] = replace_macros(option_block.values[0], macros)
            
        elif option_block.key in {"ignore_import_lib", "default_lib_dirs"}:
            self.__dict__[option_block.key] = convert_bool_option(self.__dict__[option_block.key], option_block)
    
        else:
            option_block.error("Unknown Linker Option: ")
            
    def remove_item(self, macros: dict, option_block: QPCBlock, item: QPCBlock, name: str):
        if option_block.key == "libs":
            self.remove_lib(macros, item)
        else:
            super().remove_item(macros, option_block, item, name)

    def add_lib(self, macros: dict, lib_block: QPCBlock) -> None:
        for lib_path in (lib_block.key, *lib_block.values):
            lib_path = self._fix_lib_path(macros, lib_path)
            if lib_path not in self.libs:
                self.libs.append(lib_path)
            elif not args.hide_warnings:
                lib_block.warning(f"Library already added: \"{lib_path}\"")

    def remove_lib(self, macros: dict, lib_block: QPCBlock) -> None:
        for lib_path in lib_block.values:
            lib_path = self._fix_lib_path(macros, lib_path)
            if lib_path in self.libs:
                self.libs.remove(lib_path)
            elif not args.hide_warnings:
                lib_block.warning(f"Trying to remove a library that hasn't been added yet: \"{lib_path}\"")

    @staticmethod
    def _fix_lib_path(macros: dict, lib_path: str) -> str:
        return os.path.splitext(clean_path(lib_path, macros))[0]
    
    
def convert_bool_option(old_value: bool, option_block: QPCBlock) -> bool:
    value = option_block.values[0]
    if value == "true":
        return True
    elif value == "false":
        return False
    else:
        option_block.invalid_option(value, "true", "false")
        return old_value
    
    
def convert_enum_option(old_value: Enum, option_block: QPCBlock, enum_list: EnumMeta) -> Enum:
    value = option_block.values[0]
    for enum in enum_list:
        if value == enum.name.lower():
            return enum
    else:
        option_block.invalid_option(value, *[enum.name.lower() for enum in enum_list])
        return old_value
    
    
class BuildEvent:
    def __init__(self, name: str, *event_macros):
        self.name = name
        self.macros = event_macros
        self.commands = []
        
    def _get_event_list(self, warning_func: classmethod, warning_start: str, *event_macros) -> list:
        macro_dict = {}
        for index, macro_value in enumerate(event_macros):
            if index < len(self.macros):
                macro_dict[self.macros[index]] = macro_value
            else:
                warning_func(f"{warning_start} build event \"{self.name}\" with extra arguments")
                break
    
        if len(macro_dict) < len(self.macros):
            warning_func(f"{warning_start} build event \"{self.name}\" with too few arguments")
    
        return [replace_macros_list(macro_dict, *line) for line in self.commands]
        
    def _remove_command(self, warning_func: classmethod, step: List[str], line: list):
        for event in line:
            if event in step:
                step.remove(event)
            else:
                warning_func(f"Attempting to remove command that doesn't exist in \"{self.name}\": {event}")
        
    def remove_event(self, warning_func: classmethod, step: List[str], *event_macros):
        event_list = self._get_event_list(warning_func, "Removing", *event_macros)
    
        for line in event_list:
            # no reason to remove this since it just removes a command already
            if line[0] != "-":
                self._remove_command(warning_func, step, line)
        
    def call_event(self, warning_func: classmethod, step: List[str], *event_macros):
        event_list = self._get_event_list(warning_func, "Calling", *event_macros)
        
        for line in event_list:
            if line[0] == "-":
                if len(line) > 1:
                    self._remove_command(warning_func, step, line)
                else:
                    warning_func(f"Attempting to remove nothing in \"{self.name}\": ")
            else:
                step.extend(line)
        
        
def check_if_file_exists(file_path: str, option_warning: classmethod) -> bool:
    if args.check_files:
        if not os.path.isfile(file_path):
            option_warning("File does not exist: ")
            return False
    return True


def split_folders(path_list):
    full_folder_paths = set()
    
    for folder_path in set(path_list):
        current_path = list(os.path.split(folder_path)[0].split("/"))
        if not current_path:
            continue
        folder_list = [current_path[0]]
        del current_path[0]
        for folder in current_path:
            folder_list.append(folder_list[-1] + "/" + folder)
        full_folder_paths.update(folder_list)
    
    return full_folder_paths


def replace_macros_list(macros, *value_list):
    value_list = list(value_list)
    for index, item in enumerate(value_list):
        value_list[index] = replace_macros(item, macros)
    return value_list


def replace_macros(string: str, macros: Dict[str, str]):
    count = string.count("$")
    # if count > 0 and count % 2 == 0:
    # maybe allow optional escaping? would use on vs macros - \$()
    # just so notepad++ doesn't shit itself with it's syntax highlighting
    if count > 0:
        potential_macros = [macro for macro in macros if macro in string]
        while potential_macros:
            # use the longest length macros to shortest
            best_macro = max(potential_macros, key=len)
            best_macro_token = f"${best_macro}{'$' if not args.legacy_macros else ''}"
            if best_macro_token in string:
                string = string.replace(best_macro_token, macros[best_macro])
            potential_macros.remove(best_macro)

    # actually don't do this, remember visual studio macros use $()
    # if "$" in string:
        # great, now i need to pass in the qpc block just for a good warning message here, there has to be a better way
        # warning(f"Macro in string \"{string}\" does not close!! (sorry for shitty warning, just use -v for now)")
    return string
