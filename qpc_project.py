# Parses Project Scripts, Base Scripts, Definition Files, and Hash Files

# TODO: figure out what is $CRCCHECK is
# may need to add a /checkfiles launch option to have this check if a file exists or not
# it would probably slow it down as well

import os
import re
import qpc_hash
from qpc_reader import solve_condition, read_file, QPCBlock
# from os import sep, path
from qpc_args import args
from qpc_base import posix_path, Platform, PlatformName
from enum import EnumMeta, Enum, auto

if args.time:
    from time import perf_counter


# IDEA: be able to reference values from the configuration, like a macro
# so lets say you set output directory in the configuration,
# and you don't want to make that a macro just to use that somewhere else.
# so, you do something like this instead: @config.general.out_dir
# this would use the value of out_dir in the configuration
# if it's invalid, just return None, or an empty string


EXTS_C = {".cpp", ".cxx", ".c", ".cc"}


class Compiler(Enum):
    MSVC_142 = auto(),
    MSVC_141 = auto(),
    MSVC_140 = auto(),
    MSVC_120 = auto(),
    MSVC_100 = auto(),

    CLANG_9 = auto(),
    CLANG_8 = auto(),

    # GCC_10 = auto(),
    GCC_9 = auto(),
    GCC_8 = auto(),
    GCC_7 = auto(),
    GCC_6 = auto(),


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
        self.script_list = []
        self.groups = []
        
        # this is just so it stops changing this outside of the function
        self.group_folder_list = folder_list
    
    def AddScript(self, script_path: str) -> None:
        self.script_list.append(posix_path(script_path))
    
    def AddScriptList(self, script_list) -> None:
        [self.AddScript(script_path) for script_path in script_list]


class ProjectGroup:
    def __init__(self, group_name):
        self.name = group_name
        self.projects = []
    
    def AddProject(self, project_name, project_scripts, folder_list):
        project_def = ProjectDefinition(project_name, *folder_list)
        project_def.AddScriptList(project_scripts)
        self.projects.append(project_def)


class SourceFile:
    def __init__(self, folder_list: list):
        self.folder = "/".join(folder_list)
        self.compiler = ConfigCompiler()


class ProjectPass:
    def __init__(self, project, config: str, platform: Enum):
        self.project = project
        self.config_name = config
        self.platform = platform
        self.config = Configuration(self)
        self.source_files = {}
        self.files = {}
        
        self.hash_list = {}
        self.macros = {**project.macros, "$" + config.upper(): "1", "$" + platform.name.upper(): "1"}
    
    def add_macro(self, macro_name: str, macro_value: str = "") -> None:
        key_name = "$" + macro_name.upper()
        
        if macro_value:
            self.macros[key_name] = macro_value
        else:
            if key_name not in self.macros:
                self.macros[key_name] = ''

        self._replace_undefined_macros()
    
    def _replace_undefined_macros(self):
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
            if os.path.splitext(file_path)[1] in EXTS_C:
                if file_path in self.source_files:
                    if not args.hide_warnings:
                        file_block.warning("File already added")
                else:
                    check_if_file_exists(file_path, file_block.warning)
                    self.source_files[file_path] = SourceFile(folder_list)
            else:
                if file_path in self.files:
                    if not args.hide_warnings:
                        file_block.warning("File already added")
                else:
                    check_if_file_exists(file_path, file_block.warning)
                    self.files[file_path] = "/".join(folder_list)
    
    def remove_file(self, file_block: QPCBlock):
        for file_path in file_block.values:
            file_path = self.replace_macros(file_path)
            if os.path.splitext(file_path)[1] in EXTS_C:
                if file_path in self.source_files:
                    del self.source_files[file_path]
                elif not args.hide_warnings:
                    file_block.warning("Trying to remove a file that hasn't been added yet")
            else:
                if file_path in self.files:
                    del self.files[file_path]
                elif not args.hide_warnings:
                    file_block.warning("Trying to remove a file that hasn't been added yet")

    def add_file_glob(self, folder_list, file_block: QPCBlock) -> None:
        # use glob to search
        pass

    def remove_file_glob(self, folder_list, file_block: QPCBlock) -> None:
        # use glob to search
        pass

    def add_dependency(self, qpc_path: str) -> None:
        self.project.add_dependency(qpc_path)

    def remove_dependency(self, qpc_path: str) -> None:
        self.project.remove_dependency(qpc_path)

    def add_dependencies(self, *qpc_paths) -> None:
        self.project.add_dependencies(*qpc_paths)
    
    def remove_dependencies(self, *qpc_paths) -> None:
        self.project.remove_dependencies(*qpc_paths)
    
    # Gets every single folder in the project, splitting each one as well
    # this function is awful
    def get_editor_folders(self) -> set:
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
                folder_list.append(folder_list[-1] + "/" + folder)
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
        try:
            return self.files[self.replace_macros(file_path)]
        except KeyError:
            pass
    
    def get_source_file(self, file_path) -> SourceFile:
        try:
            return self.source_files[self.replace_macros(file_path)]
        except KeyError:
            pass
    
    def GetSourceFileFolder(self, file_path):
        return self.get_source_file(self.replace_macros(file_path)).folder
    
    def GetSourceFileCompiler(self, file_path):
        return self.get_source_file(self.replace_macros(file_path)).compiler


class Project:
    # def __init__(self, name: str, script_path: str, base_macros, dependency_dict: dict):
    def __init__(self, name: str, project_path: str, settings):  # info is BaseInfo from qpc_parser.py
        self.file_name = name  # the actual file name
        self.project_path = project_path  # should use the macro instead tbh, might remove
        self.out_dir = os.path.split(project_path)[0]
        self.projects = []
        self.hash_dict = {}
        self.base_settings = settings
        # self.dependency_convert = dependency_dict
        self.dependencies = set()
        # shared across configs, used as a base for them
        self.macros = {**settings.macros, "$PROJECT_NAME": name, "$SCRIPT_NAME": name}
        # self.global_config = GlobalConfig()
        
    def parse_project(self):
        pass
    
    def add_parsed_project_pass(self, project):
        self.hash_dict.update({**project.hash_list})
        
        # update the name in case it changed
        self.macros.update({"$PROJECT_NAME": project.macros["$PROJECT_NAME"]})
        
        del project.hash_list
        del project.macros["$PROJECT_NAME"]
        
        self.projects.append(project)

    @staticmethod
    def _add_dependency_ext(qpc_path: str) -> str:
        if not qpc_path.endswith(".qpc"):
            qpc_path = os.path.splitext(qpc_path)[0] + ".qpc"
        return qpc_path

    def _convert_dependency_path(self, key: str) -> str:
        if key in self.base_settings.dependency_dict:
            return self.base_settings.dependency_dict[key]
        return key

    def add_dependency(self, qpc_path: str) -> None:
        new_qpc_path = self._convert_dependency_path(qpc_path)
        qpc_path = new_qpc_path if new_qpc_path else posix_path(self._add_dependency_ext(qpc_path))
        if qpc_path != self.project_path:
            self.dependencies.add(qpc_path)

    def remove_dependency(self, qpc_path: str) -> None:
        new_qpc_path = self._convert_dependency_path(qpc_path)
        qpc_path = new_qpc_path if new_qpc_path else posix_path(self._add_dependency_ext(qpc_path))
        if qpc_path in self.dependencies:
            self.dependencies.remove(qpc_path)

    def add_dependencies(self, *qpc_paths) -> None:
        [self.add_dependency(qpc_path) for qpc_path in qpc_paths]

    def remove_dependencies(self, *qpc_paths) -> None:
        [self.remove_dependency(qpc_path) for qpc_path in qpc_paths]
    
    def get_editor_folders(self) -> set:
        folder_paths = set()
        for project in self.projects:
            folder_paths.update(project.get_editor_folders())
        return folder_paths
    
    def get_folders(self) -> set:
        folder_paths = set()
        for project in self.projects:
            folder_paths.update(project.get_folders())
        return folder_paths

    def get_display_name(self) -> str:
        return self.macros["$PROJECT_NAME"]


# TODO: maybe add some enums for options with specific values?
#  though how would writers get all the available values? maybe a seperate file


class Configuration:
    def __init__(self, project_pass: ProjectPass):
        self._project = project_pass
        # self.debug = Debug()
        self.general = General(project_pass.platform)
        self.compiler = ConfigCompiler()
        self.linker = Linker()
        self.pre_build = []
        self.pre_link = []
        self.post_build = []
        
    def add_build_event_options(self, group_block: QPCBlock, option_block: QPCBlock):
        value = replace_macros(' '.join(option_block.values), self._project.macros)
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


def clean_path(string: str, macros: dict) -> str:
    return posix_path(os.path.normpath(replace_macros(string, macros)))


class General:
    def __init__(self, platform: Enum):
        self.out_dir = None
        self.int_dir = None
        self.out_name = None

        # i want to make these configuration options unaffected by config and platform macros,
        # and have it run before it goes through each config/platform
        # except what if someone sets a macro with a config conditional and uses it in one of these?
        # won't work, so im just leaving it as it is for now, hopefully i can get something better later on
        self.configuration_type = None
        self.language = None
        self.compiler = Compiler.MSVC_142 if platform in {Platform.WIN32, Platform.WIN64} else Compiler.GCC_9
        
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
            
        if option_block.key in {"out_dir", "int_dir"}:
            self.__dict__[option_block.key] = clean_path(option_block.values[0], macros)
            
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
            self.set_compiler(option_block)
            
        else:
            option_block.error("Unknown General Option: ")
            
    def set_type(self, option: QPCBlock) -> None:
        self.configuration_type = convert_enum_option(self.configuration_type, option, ConfigType)

    def set_language(self, option: QPCBlock) -> None:
        self.language = convert_enum_option(self.language, option, Language)

    def set_compiler(self, option: QPCBlock) -> None:
        self.compiler = convert_enum_option(self.compiler, option, Compiler)


class ConfigCompiler:
    def __init__(self):
        self.preprocessor_definitions = []
        self.precompiled_header = PrecompiledHeader.NONE
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
        lib_path = replace_macros(lib_path, macros)
        return os.path.splitext(posix_path(os.path.normpath(lib_path)))[0] + macros["$_STATICLIB_EXT"]
    
    
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
