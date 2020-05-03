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
from enum import EnumMeta, Enum, auto
from time import perf_counter


# IDEA: be able to reference values from the configuration, like a macro
# so lets say you set output directory in the configuration,
# and you don't want to make that a macro just to use that somewhere else.
# so, you do something like this instead: @config.general.out_dir
# this would use the value of out_dir in the configuration
# if it's invalid, just return None, or an empty string


EXTS_C = {".cpp", ".cxx", ".c", ".cc"}


# maybe move to qpc_base with the other Enums?
class ConfigType(Enum):
    STATIC_LIBRARY = auto(),
    # SHARED_LIBRARY = auto(),
    DYNAMIC_LIBRARY = auto(),
    APPLICATION = auto()  # IDEA: rename all application stuff to executable?


class PrecompiledHeader(Enum):
    NONE = auto(),
    CREATE = auto(),
    USE = auto()


class Language(Enum):
    CPP = auto(),
    C = auto()


class ProjectDefinition:
    def __init__(self, project_name: str, *folder_list):
        self.name = project_name
        self.script_list = dict()  # dict keeps order set doesn't
        self.platforms = set()
        self.groups = set()  # could be a list, depends on which is faster here, x in set? or for x in list?
        
        # this is just so it stops changing this outside of the function
        self.folder_list = folder_list
        
    # group is ProjectGroup, right below
    def add_group(self, group) -> None:
        self.groups.add(group)
        
    def update_groups(self) -> None:
        # list would be faster here
        [group.project_defined(self) for group in self.groups]
    
    def add_script(self, script_path: str) -> bool:
        if os.path.isfile(script_path):
            self.script_list[posix_path(script_path)] = None
            return True
        return False
    
    def add_script_list(self, script_list) -> bool:
        return all([self.add_script(script_path) for script_path in script_list])


class ProjectGroup:
    def __init__(self, group_name):
        self.name = group_name
        # dict keeps order, set doesn't as of 3.8, both faster than lists
        self.projects = dict()
    
    def project_defined(self, project_def: ProjectDefinition) -> None:
        self.projects[project_def] = None
    
    def add_project(self, project_name: str, folder_list: list, unsorted_projects: dict) -> None:
        if project_name in unsorted_projects:
            project_def = unsorted_projects[project_name]
            if not project_def.folder_list:
                project_def.folder_list = tuple(folder_list)
            self.project_defined(project_def)
        else:
            project_def = ProjectDefinition(project_name, *folder_list)
            unsorted_projects[project_name] = project_def
        project_def.add_group(self)


class SourceFile:
    def __init__(self, folder_list: list):
        self.folder = "/".join(folder_list)
        self.compiler = ConfigCompiler()


class ProjectPass:
    # container is ProjectContainer, below this class
    def __init__(self, container, config: str, platform: Platform, arch: Arch, gen_macro: str, gen_id: int):
        self.config_name = config
        self.platform = platform
        self.arch = arch
        self.base_info = container.base_info.get_base_info(platform)
        
        self.container = container
        self.config = Configuration(self)
        self.source_files = {}
        self.files = {}
        self.hash_list = {}
        self._glob_files = set()
        self.build_events = {}

        self.macros = {
            **container.macros,
            **self.base_info.macros,
            
            "$" + config.upper():   "1",  # this doesn't have to be uppercase, but it's mainly for consistency
            "$" + platform.name:    "1",
            "$" + arch.name:        "1",
            
            "$QPC_CONFIG":          config,
            "$QPC_PLATFORM":        platform.name,
            "$QPC_ARCH":            arch.name,
        }
        
        self.generators = set()
        self.add_generator(gen_macro, gen_id)
        
    def check_pass(self, config: str, platform: Platform, arch: Arch, generator_macro: str, gen_id: int) -> bool:
        # is this even setup right?
        if self.config_name == config and self.platform == platform and self.arch == arch and gen_id in self.generators:
            self.add_generator(generator_macro, gen_id)
            return True
        return False
    
    def add_generator(self, gen_macro: str, gen_id: int):
        self.generators.add(gen_id)
        if gen_macro:
            self.macros.update({gen_macro: "1"})

    def _convert_dependency_path(self, key: str) -> str:
        return self.base_info.get_dependency_path(key)
    
    def add_macro(self, macro_name: str, macro_value: str = "") -> None:
        key_name = "$" + macro_name.upper()
        
        if macro_value:
            self.macros[key_name] = macro_value
        else:
            if key_name not in self.macros:
                self.macros[key_name] = ''

        self._replace_undefined_macros()
    
    def _replace_undefined_macros(self) -> None:
        # this could probably be sped up
        # TODO: add scanning of files and certain config info
        for macro, value in self.macros.items():
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
        if os.path.splitext(file_path)[1] in EXTS_C:
            if file_path in self.source_files:
                if not args.hide_warnings:
                    file_block.warning("File already added: " + file_path)
            else:
                check_if_file_exists(file_path, file_block.warning)
                self.source_files[file_path] = SourceFile(folder_list)
        else:
            if file_path in self.files:
                if not args.hide_warnings:
                    file_block.warning("File already added: " + file_path)
            else:
                check_if_file_exists(file_path, file_block.warning)
                self.files[file_path] = "/".join(folder_list)

    def _remove_file_internal(self, folder_list: list, file_path: str, file_block: QPCBlock):
        if os.path.splitext(file_path)[1] in EXTS_C:
            if file_path in self.source_files:
                # if self.source_files[file_path].folder == "/".join(folder_list):
                del self.source_files[file_path]
            elif not args.hide_warnings:
                file_block.warning("Trying to remove a file that hasn't been added yet: " + file_path)
        else:
            if file_path in self.files:
                # is this even a good idea? might just be annoying
                # if self.files[file_path] == "/".join(folder_list):
                del self.files[file_path]
            elif not args.hide_warnings:
                file_block.warning("Trying to remove a file that hasn't been added yet: " + file_path)

    def add_dependency(self, qpc_path: str) -> None:
        self.container.add_dependency(replace_macros(self._convert_dependency_path(qpc_path), self.macros))

    def remove_dependency(self, qpc_path: str) -> None:
        self.container.remove_dependency(replace_macros(self._convert_dependency_path(qpc_path), self.macros))

    def add_dependencies(self, *qpc_paths) -> None:
        [self.add_dependency(qpc_path) for qpc_path in qpc_paths]
    
    def remove_dependencies(self, *qpc_paths) -> None:
        [self.remove_dependency(qpc_path) for qpc_path in qpc_paths]
        
    def is_build_event_defined(self, name: str):
        return name in self.build_events
        
    def call_build_event(self, event_name: str, *event_args):
        if event_name in self.build_events:
            event_args = replace_macros_list(self.macros, *event_args)
            arg_list = []
            has_glob_and_none_found = False
            
            for index, event_macro in enumerate(event_args):
                if check_file_path_glob(event_macro):
                    found_files = glob.glob(event_macro, recursive=True)
                    has_glob_and_none_found = not bool(found_files)
                    for found_file in found_files:
                        # TODO: multiple wildcards that don't find anything might act odd here
                        current_list = [*event_args[index:], found_file, *event_args[:index]]
                        arg_list.append(current_list)
            else:
                if not arg_list and not has_glob_and_none_found:
                    arg_list = [list(event_args)]
                    
            for item in arg_list:
                self.build_events[event_name].call_event(self, *item)
    
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


class ProjectContainer:
    # base_info is BaseInfo from qpc_parser.py
    def __init__(self, name: str, project_path: str, base_info, project_def: ProjectDefinition, generator_list: list):
        self.file_name = name  # the actual file name
        self.project_path = project_path  # should use the macro instead tbh, might remove
        self.out_dir = os.path.split(project_path)[0]
        self.hash_dict = {}
        self.base_info = base_info
        
        # self.dependency_convert = dependency_dict
        self.dependencies = set()
        # shared across configs, used as a base for them
        self.macros = {
            "$PROJECT_NAME": name,
            "$PROJECT_DIR": self.out_dir,
            "$SCRIPT_NAME": name,
            "$ROOT_DIR": args.root_dir,
            **get_arg_macros()
        }
        
        self._passes = []
        generator_macros = {}
        for generator in generator_list:
            macro = generator.get_macro()
            macro = "$" + macro if macro else macro
            generator_macros[generator] = macro

        for generator, macro in generator_macros.items():
            generator_platforms = generator.get_supported_platforms()
            for platform in project_def.platforms:
                if platform in generator_platforms:
                    for config in base_info.get_base_info(platform).configurations:
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
        return self._passes[0].macros["$PROJECT_NAME"]

    def get_out_dir(self) -> str:
        out_dir = ""  # os.path.split(project.project_path)[0]
        # TODO: actually test this and see if it works just fine, it should
        '''
        if args.project_dir:
            try:
                out_dir = posix_path(self.projects[0].macros["$PROJECT_DIR"])
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


# TODO: maybe add some enums for options with specific values?
#  though how would writers get all the available values? maybe a seperate file


class Configuration:
    def __init__(self, project: ProjectPass):
        self._project = project
        self.debug = Debug()
        self.general = General(project.container.file_name, project.platform)
        self.compiler = ConfigCompiler()
        self.linker = Linker()
        self.pre_build = []
        self.pre_link = []
        self.post_build = []
        
    def add_build_event_options(self, group_block: QPCBlock, option_block: QPCBlock):
        value = replace_macros(option_block.key, self._project.macros)
        if option_block.values:
            value += " " + replace_macros(" ".join(option_block.values), self._project.macros)
        if value:
            # TODO: improve this, what if \\n is used in the file? it would just become \ and then new line, awful
            value = value.replace("\\n", "\n")
            self.__dict__[group_block.key].append(value)

    def parse_config_option(self, group_block: QPCBlock, option_block: QPCBlock):
        if group_block.key in self.__dict__ and group_block.key != "_project":
            if group_block.key in {"post_build", "pre_build", "pre_link"}:
                self.add_build_event_options(group_block, option_block)
            else:
                self.__dict__[group_block.key].parse_option(self._project.macros, option_block)
        elif group_block.key == "global":
            pass
        else:
            group_block.error("Unknown Configuration Group: ")


# idea, for debug options in the editor used (if it can debug)
class Debug:
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
    return posix_path(os.path.normpath(replace_macros(string, macros)))


class General:
    def __init__(self, file_name: str, platform: Platform):
        self.out_dir = None
        self.build_dir = None
        self.out_name = file_name

        # i want to make these configuration options unaffected by config and platform macros,
        # and have it run before it goes through each config/platform
        # except what if someone sets a macro with a config conditional and uses it in one of these?
        # won't work, so im just leaving it as it is for now, hopefully i can get something better later on
        self.configuration_type = None
        self.language = None
        self.compiler = "msvc" if platform == Platform.WINDOWS else "gcc"
        
        self.default_include_directories = True
        self.default_library_directories = True
        self.include_directories = []
        self.library_directories = []
        self.options = []

    def parse_option(self, macros: dict, option_block: QPCBlock) -> None:
        # multiple path options
        if option_block.key in {"include_directories", "library_directories", "options"}:
            for item in option_block.items:
                if item.solve_condition(macros):
                    self.__dict__[option_block.key].extend(replace_macros_list(macros, *item.get_list()))

        elif option_block.key == "options":
            for item in option_block.items:
                if item.solve_condition(macros):
                    self.options.extend(item.get_list())

        if not option_block.values:
            return
        
        if option_block.key in {"out_dir", "int_dir", "build_dir"}:
            value = clean_path(option_block.values[0], macros)
            if option_block.key in {"build_dir", "int_dir"}:
                self.build_dir = value
            else:
                self.out_dir = value
            
        elif option_block.key == "out_name":
            self.out_name = replace_macros(option_block.values[0], macros)
        
        elif option_block.key in {"default_include_directories", "default_library_directories"}:
            self.__dict__[option_block.key] = convert_bool_option(self.__dict__[option_block.key], option_block)
            
        elif option_block.key == "configuration_type":
            self.set_type(option_block)
        elif option_block.key == "language":
            self.set_language(option_block)
        elif option_block.key in {"toolset_version", "compiler"}:
            if option_block.key == "toolset_version":
                if not args.hide_warnings:
                    option_block.warning("toolset_version is now compiler")
            self.compiler = replace_macros(option_block.values[0], macros)
            
        else:
            option_block.error("Unknown General Option: ")
            
    def set_type(self, option: QPCBlock) -> None:
        self.configuration_type = convert_enum_option(self.configuration_type, option, ConfigType)

    def set_language(self, option: QPCBlock) -> None:
        self.language = convert_enum_option(self.language, option, Language)


class ConfigCompiler:
    def __init__(self):
        self.preprocessor_definitions = []
        self.precompiled_header = None  # PrecompiledHeader.NONE
        self.precompiled_header_file = None
        self.precompiled_header_output_file = None
        self.options = []

    def parse_option(self, macros: dict, option_block: QPCBlock) -> None:
        if option_block.key in ("preprocessor_definitions", "options"):
            for item in option_block.items:
                if item.solve_condition(macros):
                    self.__dict__[option_block.key].extend(replace_macros_list(macros, *item.get_list()))
    
        elif option_block.key == "precompiled_header":
            if option_block.values:
                self.precompiled_header = convert_enum_option(self.precompiled_header, option_block, PrecompiledHeader)
    
        elif option_block.key in {"precompiled_header_file", "precompiled_header_output_file"}:
            self.__dict__[option_block.key] = replace_macros(option_block.values[0], macros)
    
        else:
            option_block.error("Unknown Compiler Option: ")


class Linker:
    def __init__(self):
        self.output_file = None
        self.debug_file = None
        self.import_library = None
        self.ignore_import_library = False  # idk what the default should be
        self.entry_point = None
        self.libraries = []
        self.ignore_libraries = []  # maybe change to ignored_libraries?
        self.options = []

    def parse_option(self, macros: dict, option_block: QPCBlock) -> None:
        if option_block.key in {"options", "libraries", "ignore_libraries"}:
            for item in option_block.items:
                if item.solve_condition(macros):
                    if option_block.key == "libraries":
                        if item.key == "-":
                            self.remove_lib(macros, item)
                        else:
                            self.add_lib(macros, item)
                    else:
                        self.__dict__[option_block.key].extend(replace_macros_list(macros, *item.get_list()))
                    
        elif not option_block.values:
            return
            
        elif option_block.key in {"output_file", "debug_file"}:
            # TODO: maybe split the extension for output_file, debug_file, or import_library?
            self.__dict__[option_block.key] = clean_path(option_block.values[0], macros)
            
        elif option_block.key in {"import_library", "entry_point"}:
            # TODO: maybe split the extension for output_file, debug_file, or import_library?
            self.__dict__[option_block.key] = replace_macros(option_block.values[0], macros)
            
        elif option_block.key == "ignore_import_library":
            self.ignore_import_library = convert_bool_option(self.ignore_import_library, option_block)
    
        else:
            option_block.error("Unknown Linker Option: ")

    def add_lib(self, macros: dict, lib_block: QPCBlock) -> None:
        for lib_path in (lib_block.key, *lib_block.values):
            lib_path = self._fix_lib_path_and_ext(macros, lib_path)
            if lib_path not in self.libraries:
                self.libraries.append(lib_path)
            elif not args.hide_warnings:
                lib_block.warning("Library already added")

    def remove_lib(self, macros: dict, lib_block: QPCBlock) -> None:
        for lib_path in lib_block.values:
            lib_path = self._fix_lib_path_and_ext(macros, lib_path)
            if lib_path in self.libraries:
                self.libraries.remove(lib_path)
            elif not args.hide_warnings:
                lib_block.warning("Trying to remove a library that hasn't been added yet")

    # actually do you even need the extension?
    @staticmethod
    def _fix_lib_path_and_ext(macros: dict, lib_path: str) -> str:
        lib_path = clean_path(lib_path, macros)
        return os.path.splitext(lib_path)[0] + macros["$_STATICLIB_EXT"]
    
    
def convert_bool_option(old_value: bool, option_block: QPCBlock) -> bool:
    value = option_block.values[0]
    if value == "true":
        return True
    elif value == "false":
        return False
    else:
        option_block.invalid_option("true", "false")
        return old_value
    
    
def convert_enum_option(old_value: Enum, option_block: QPCBlock, enum_list: EnumMeta) -> Enum:
    # value = replace_macros(option_block.values[0])
    value = option_block.values[0]
    for enum in enum_list:
        if value == enum.name.lower():
            return enum
    else:
        option_block.invalid_option(*[enum.name.lower() for enum in enum_list])
        return old_value
    
    
class BuildEvent:
    def __init__(self, name: str, *event_macros):
        self.name = name
        self.macros = ["$" + event_macro for event_macro in event_macros]
        self.pre_build = []
        self.pre_link = []
        self.post_build = []
        
    def call_event(self, project: ProjectPass, *event_macros):
        macro_dict = {}
        for index, macro_value in enumerate(event_macros):
            if index < len(self.macros):
                macro_dict[self.macros[index]] = macro_value
            else:
                # tf are you doing
                break
                
        # todo later: maybe handle undefined stuff? probably going to forget about this
            
        self._add_event(project.config, macro_dict, "pre_build")
        self._add_event(project.config, macro_dict, "pre_link")
        self._add_event(project.config, macro_dict, "post_build")
    
    def _add_event(self, config: Configuration, macros: dict, event_name: str):
        event_list = replace_macros_list(macros, *self.__dict__[event_name])
        config.__dict__[event_name].extend(event_list)
        
        
def check_if_file_exists(file_path: str, option_warning: classmethod):
    if args.check_files:
        if not os.path.isfile(file_path):
            if not args.hide_warnings:
                # raise FileNotFoundError("File does not exist: " + file_path)
                option_warning("File does not exist: ")


def split_folders(path_list):
    full_folder_paths = set()
    
    for folder_path in set(path_list):
        # uhhhhhh
        # current_path = list(os.path.split(folder_path)[0].split("/"))
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


def replace_macros(string, macros):
    if "$" in string:
        for macro, macro_value in macros.items():
            if macro in string:
                string_split = string.split(macro)
                string = macro_value.join(string_split)
    return string
