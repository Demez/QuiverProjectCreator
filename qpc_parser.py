# Parses Project Scripts, Base Scripts, Definition Files, and Hash Files

# TODO: figure out what is $CRCCHECK is
# may need to add a /checkfiles launch option to have this check if a file exists or not
# it would probably slow it down as well

import re
import qpc_hash
from qpc_reader import SolveCondition, ReadFile
from os import sep, path
from qpc_base import args, ConfigurationTypes, Platforms, Compilers, Languages, PosixPath

if args.time:
    from time import perf_counter


# IDEA: be able to reference values from the configuration, like a macro
# so lets say you set output directory in the configuration,
# and you don't want to make that a macro just to use that somewhere else.
# so, you do something like this instead: @config.general.out_dir
# this would use the value of out_dir in the configuration
# if it's invalid, just return None, or an empty string


class ProjectDefinition:
    def __init__(self, project_name: str, *folder_list):
        self.name = project_name
        self.script_list = []
        self.groups = []
        
        # this is just so it stops changing this outside of the function
        self.group_folder_list = folder_list
    
    def AddScript(self, script_path: str) -> None:
        self.script_list.append(PosixPath(script_path))
    
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


class ProjectPass:
    def __init__(self, macros, config, platform):
        self.config = Configuration()
        self.source_files = {}
        self.files = {}
        self.dependencies = []
        
        self.hash_list = {}
        self.macros = {**macros, "$" + config.upper(): "1", "$" + platform.upper(): "1"}
        
        self.config_name = config
        self.platform = platform
    
    def AddMacro(self, macro_name: str, macro_value: str = "") -> None:
        key_name = "$" + macro_name.upper()
        
        if macro_value:
            self.macros[key_name] = macro_value
        else:
            if key_name not in self.macros:
                self.macros[key_name] = ''

        self.ReplaceAnyUndefinedMacros()
    
    def ReplaceAnyUndefinedMacros(self):
        # this could probably be sped up
        # TODO: add scanning of files and certain config settings
        for macro, value in self.macros.items():
            self.macros[macro] = ReplaceMacros(value, self.macros)

    def AddFileWildcard(self, folder_list, file_block) -> None:
        # use glob to search
        pass
    
    def AddFile(self, folder_list, file_block) -> None:
        for file_path in (file_block.key, *file_block.values):
            if path.splitext(file_path)[1] in (".cpp", ".cxx", ".c", ".cc"):
                if self.GetSourceFile(file_path):
                    file_block.Warning("File already added")
                else:
                    CheckFileExists(file_path)
                    self.source_files[file_path] = SourceFile(folder_list)
                    continue
            else:
                if self.GetFileFolder(file_path):
                    file_block.Warning("File already added")
                else:
                    CheckFileExists(file_path)
                    self.files[file_path] = sep.join(folder_list)
                    continue

    def AddDependency(self, qpc_path: str) -> None:
        self.dependencies.append(qpc_path)

    def AddDependencies(self, *qpc_paths) -> None:
        [self.dependencies.append(PosixPath(qpc_path)) for qpc_path in qpc_paths if qpc_path not in self.dependencies]
    
    def RemoveDependencies(self, *qpc_paths) -> None:
        [self.dependencies.remove(dep) for dep in qpc_paths if dep in self.dependencies]
    
    # Gets every single folder in the project, splitting each one as well
    # this function is awful
    def GetAllEditorFolderPaths(self) -> set:
        folder_paths = set()
        # TODO: is there a better way to do this?
        [folder_paths.add(file_path) for file_path in self.files.values()]
        [folder_paths.add(sf.folder) for sf in self.source_files.values()]
        
        full_folder_paths = set()
        # split every single folder because visual studio bad
        for folder_path in folder_paths:
            current_path = list(folder_path.split(sep))
            if not current_path or not current_path[0]:
                continue
            folder_list = [current_path[0]]
            del current_path[0]
            for folder in current_path:
                folder_list.append(folder_list[-1] + sep + folder)
            full_folder_paths.update(folder_list)
        
        return full_folder_paths
    
    def GetAllFolderPaths(self) -> set:
        folder_paths = GetAllPaths(self.files)
        folder_paths.update(GetAllPaths(self.source_files))
        return folder_paths
    
    def GetFilesInFolder(self, folder_path) -> list:
        file_list = []
        
        # maybe change to startswith, so you can get stuff in nested folders as well?
        for file_path, file_folder in self.files.items():
            if file_folder == folder_path:
                file_list.append(file_path)
        
        for file_path, file_folder in self.source_files.items():
            if file_folder == folder_path:
                file_list.append(file_path)
        
        return file_list
    
    def GetFileFolder(self, file_path):
        try:
            return self.files[file_path]
        except KeyError:
            return False
    
    def GetSourceFile(self, file_path):
        try:
            return self.source_files[file_path]
        except KeyError:
            return False
    
    def GetSourceFileFolder(self, file_path):
        return self.GetSourceFile(file_path).folder
    
    def GetSourceFileCompiler(self, file_path):
        return self.GetSourceFile(file_path).compiler
    
    def AddLib(self, lib_block):
        for lib_path in (lib_block.key, *lib_block.values):
            lib_path = self.FixLibPathAndExt(lib_path)
            if lib_path not in self.config.linker.libraries:
                self.config.linker.libraries.append(lib_path)
            else:
                lib_block.Warning("Library already added")
    
    def RemoveLib(self, lib_block):
        for lib_path in lib_block.values:
            lib_path = self.FixLibPathAndExt(lib_path)
            if lib_path in self.config.linker.libraries:
                self.config.linker.libraries.remove(lib_path)
            else:
                lib_block.Warning("Trying to remove a library that hasn't been added yet")
    
    # actually do you even need the extension?
    def FixLibPathAndExt(self, lib_path):
        lib_path = ReplaceMacros(lib_path, self.macros)
        return path.splitext(path.normpath(lib_path))[0] + self.macros["$_STATICLIB_EXT"]
    
    def RemoveFile(self, file_block):
        for file_path in file_block.values:
            if path.splitext(file_path)[1] in (".cpp", ".cxx", ".c", ".cc"):
                if file_path in self.source_files:
                    del self.source_files[file_path]
                else:
                    file_block.Warning("Trying to remove a file that hasn't been added yet")
            else:
                if file_path in self.files:
                    del self.files[file_path]
                else:
                    file_block.Warning("Trying to remove a file that hasn't been added yet")


class Project:
    def __init__(self, name, project_path, base_macros):
        self.file_name = name  # the actual file name
        self.project_dir = project_path  # should use the macro instead tbh, might remove
        self.projects = []
        self.hash_dict = {}
        # shared across configs, used as a base for them
        self.macros = {**base_macros, "$PROJECT_NAME": name}
        # self.global_config = GlobalConfig()
    
    def AddParsedProject(self, project):
        self.hash_dict.update({**project.hash_list})
        
        # update the name in case it changed
        self.macros.update({"$PROJECT_NAME": project.macros["$PROJECT_NAME"]})
        
        del project.hash_list
        del project.macros["$PROJECT_NAME"]
        
        self.projects.append(project)
    
    def GetAllEditorFolderPaths(self) -> set:
        folder_paths = set()
        for project in self.projects:
            folder_paths.update(project.GetAllEditorFolderPaths())
        return folder_paths
    
    def GetAllFolderPaths(self) -> set:
        folder_paths = set()
        for project in self.projects:
            folder_paths.update(project.GetAllFolderPaths())
        return folder_paths

    def GetProjectName(self) -> str:
        return self.macros["$PROJECT_NAME"]


class SourceFile:
    def __init__(self, folder_list):
        self.folder = sep.join(folder_list)
        self.compiler = Compiler()


# TODO: maybe add some enums for options with specific values?
#  though how would writers get all the available values? maybe a seperate file


class Configuration:
    def __init__(self):
        self.general = General()
        self.compiler = Compiler()
        self.linker = Linker()
        self.pre_build = []
        self.pre_link = []
        self.post_build = []


class General:
    def __init__(self):
        self.out_dir = ''
        self.int_dir = ''
        self.out_name = ''
        self.configuration_type = ''
        self.language = ''
        self.toolset_version = ''
        self.include_directories = []
        self.library_directories = []
        self.options = []


class GlobalConfig:
    def __init__(self):
        self.configuration_type = ConfigurationTypes.STATIC_LIB
        self.language = Languages.CPP
        self.toolset_version = Compilers.MSVC_142 if \
            args.platform in {Platforms.WIN32, Platforms.WIN64} else Compilers.GCC_9

    # these convert to Enum
    def SetType(self, option: str) -> None:
        if option in {"static_library", "static_lib"}:
            self.configuration_type = ConfigurationTypes.STATIC_LIB
        elif option in {"dynamic_library", "dynamic_lib"}:
            self.configuration_type = ConfigurationTypes.DYNAMIC_LIB
        elif option in {"shared_library", "shared_lib"}:
            self.configuration_type = ConfigurationTypes.SHARED_LIB
        elif option in {"application", "executable"}:  # TODO: rename all application stuff to executable?
            self.configuration_type = ConfigurationTypes.APPLICATION

    def SetLanguage(self, option: str) -> None:
        if option == "cpp":
            self.language = Languages.CPP
        elif option == "c":
            self.language = Languages.C

    def SetToolsetVersion(self, option: str) -> None:
        if option == "msvc_142":  # TODO: change msvc-X options to msvc_X
            self.toolset_version = Compilers.MSVC_142
        elif option == "msvc_141":
            self.toolset_version = Compilers.MSVC_141
        elif option == "msvc_140":
            self.toolset_version = Compilers.MSVC_140
        elif option == "msvc_120":
            self.toolset_version = Compilers.MSVC_120
        elif option == "msvc_100":
            self.toolset_version = Compilers.MSVC_100

        elif option == "clang_9":
            self.toolset_version = Compilers.CLANG_9
        elif option == "clang_8":
            self.toolset_version = Compilers.CLANG_8

        elif option == "gcc_9":
            self.toolset_version = Compilers.GCC_9
        elif option == "gcc_8":
            self.toolset_version = Compilers.GCC_8
        elif option == "gcc_7":
            self.toolset_version = Compilers.GCC_7
        elif option == "gcc_6":
            self.toolset_version = Compilers.GCC_6


class Compiler:
    def __init__(self):
        self.preprocessor_definitions = []
        self.precompiled_header = ''
        self.precompiled_header_file = ''
        self.precompiled_header_out_file = ''
        self.options = []

    def SetPrecompiledHeader(self, option: str) -> None:
        # convert to Enum
        pass


class Linker:
    def __init__(self):
        self.output_file = ''
        self.debug_file = ''
        self.import_library = ''
        self.ignore_import_library = ''
        self.libraries = []
        self.ignore_libraries = []
        self.options = []

    def SetIgnoreImportLibrary(self, option: str) -> None:
        pass

       
# TODO: maybe do this?
class SpecificOption:
    def __init__(self):
        self.value = ''
        self.valid_options = []
        
        
def CheckFileExists(file_path):
    if args.check_files:
        if not path.isfile(file_path):
            raise FileNotFoundError("File does not exist: " + file_path)


def GetAllPaths(path_list):
    full_folder_paths = set()
    
    for folder_path in set(path_list):
        # uhhhhhh
        current_path = list(path.split(folder_path)[0].split(sep))
        if not current_path:
            continue
        folder_list = [current_path[0]]
        del current_path[0]
        for folder in current_path:
            folder_list.append(folder_list[-1] + sep + folder)
        full_folder_paths.update(folder_list)
    
    return full_folder_paths


# TODO: bug discovered with this,
#  if i include the groups before the projects, it won't add any projects
def ParseBaseFile(base_file, macros, project_list, group_dict):
    configurations = set()
    for project_block in base_file:
        
        if not SolveCondition(project_block.condition, macros):
            continue
        
        if project_block.key == "project":
            project_def = ProjectDefinition(project_block.values[0])
            
            # could have values next to it as well now
            for script_path in project_block.values[1:]:
                script_path = ReplaceMacros(script_path, macros)
                project_def.AddScript(script_path)
            
            for item in project_block.items:
                if SolveCondition(item.condition, macros):
                    item.key = ReplaceMacros(item.key, macros)
                    project_def.AddScript(item.key)
            
            project_list.append(project_def)
        
        elif project_block.key == "group":
            # TODO: fix this for multiple groups
            for group in project_block.values:
                
                # do we have a group with this name already?
                if group in group_dict:
                    project_group = group_dict[group]
                else:
                    project_group = ProjectGroup(group)
                
                ParseProjectGroupItems(project_group, project_list, project_block, macros)
                group_dict[project_group.name] = project_group
        
        elif project_block.key == "macro":
            macros["$" + project_block.values[0].upper()] = ReplaceMacros(project_block.values[1], macros)
        
        elif project_block.key == "configurations":
            configurations.update(project_block.GetItemKeyAndValuesThatPassCondition(macros))
        
        elif project_block.key == "include":
            # "Ah shit, here we go again."
            file_path = path.normpath(ReplaceMacros(project_block.values[0], macros))
            
            if args.verbose:
                print("Reading: " + file_path)
            
            include_file = ReadFile(file_path)
            
            if args.verbose:
                print("Parsing... ")
            
            ParseBaseFile(include_file, macros, project_list, group_dict)
        
        else:
            project_block.Warning("Unknown Key: ")
    
    return configurations


def ParseProjectGroupItems(project_group, project_list, project_block, macros, folder_list=None):
    if not folder_list:
        folder_list = []
    
    for item in project_block.items:
        if SolveCondition(item.condition, macros):
            
            if item.key == "folder":
                folder_list.append(item.values[0])
                ParseProjectGroupItems(project_group, project_list, item, macros, folder_list)
                folder_list.remove(item.values[0])
            else:
                for project in project_list:
                    if project.name == item.key:
                        project_group.AddProject(project.name, project.script_list, folder_list)
    return


def ParseProjectFile(project_file, project, project_path, indent):
    for project_block in project_file:
        if SolveCondition(project_block.condition, project.macros):
            
            project_block.values = ReplaceMacrosInList(project.macros, *project_block.values)
            
            if project_block.key == "macro":
                project.AddMacro(*project_block.values)
            
            elif project_block.key == "configuration":
                ParseConfigBlock(project_block, project)
            
            elif project_block.key == "files":
                ParseFilesBlock(project_block, project, [])
            
            elif project_block.key == "dependencies":
                for block in project_block.items:
                    if block.key == "-":
                        project.RemoveDependencies(*block.values)
                    else:
                        project.AddDependencies(block.key, *block.values)
            
            elif project_block.key == "include":
                # Ah shit, here we go again.
                include_path = project_block.values[0]
                include_file = IncludeFile(include_path, project, project_path, indent + "    ")
                ParseProjectFile(include_file, project, include_path, indent + "    ")
                if args.verbose:
                    print(indent + "    " + "Finished Parsing")
            
            else:
                project_block.Warning("Unknown key: ")
    return


def IncludeFile(include_path, project, project_path, indent):
    project.hash_list[include_path] = qpc_hash.MakeHash(include_path)
    include_file = ReadFile(include_path)
    
    if not include_file:
        raise FileNotFoundError(
            "File does not exist:\n\tScript: {0}\n\tFile: {1}".format(project_path, include_path))
    
    if args.verbose:
        print(indent + "Parsing: " + include_path)
    
    return include_file


def ParseLibrariesBlock(libraries_block, project):
    if SolveCondition(libraries_block.condition, project.macros):
        for library in libraries_block.items:
            if SolveCondition(library.condition, project.macros):
                
                if library.key == "-":
                    library_path = ReplaceMacros(library.values[0], project.macros)
                    project.RemoveLib(library_path)
                else:
                    library_path = ReplaceMacros(library.key, project.macros)
                    project.AddLib(library_path)


def ParseFilesBlock(files_block, project, folder_list):
    if SolveCondition(files_block.condition, project.macros):
        for block in files_block.items:
            if SolveCondition(block.condition, project.macros):
                
                if block.key == "folder":
                    folder_list.append(block.values[0])
                    ParseFilesBlock(block, project, folder_list)
                    folder_list.remove(block.values[0])
                
                elif block.key == "-":
                    block.values = ReplaceMacrosInList(project.macros, *block.values)
                    project.RemoveFile(block)
                else:
                    block.key = ReplaceMacros(block.key, project.macros)
                    block.values = ReplaceMacrosInList(project.macros, *block.values)
                    project.AddFile(folder_list, block)
                    
                    if block.items:
                        for file_path in (block.key, *block.values):
                            source_file = project.GetSourceFile(file_path)
                            
                            # TODO: set this to directly edit the configuration options
                            #  remove need to write out configuration {}
                            #  also this is messy
                            
                            for config_block in block.items:
                                if SolveCondition(config_block.condition, project.macros):
                                    for group_block in config_block.items:
                                        
                                        if group_block.key != "compiler":
                                            group_block.Error("Invalid Group, can only use compiler")
                                            continue
                                        
                                        if SolveCondition(group_block.condition, project.macros):
                                            for option_block in group_block.items:
                                                if SolveCondition(option_block.condition, project.macros):
                                                    ParseCompilerOption(project, source_file.compiler, option_block)


def ParseConfigBlock(project_block, project):
    if SolveCondition(project_block.condition, project.macros):
        for group_block in project_block.items:
            if SolveCondition(group_block.condition, project.macros):
                for option_block in group_block.items:
                    if SolveCondition(option_block.condition, project.macros):
                        ParseConfigOption(project, group_block, option_block)


# this could be so much better
def ParseConfigOption(project, group_block, option_block):
    config = project.config
    if group_block.key == "general":
        # single path options
        if option_block.key in ("out_dir", "int_dir", "out_name", "toolset_version"):
            if not option_block.values:
                return
            if option_block.key == "out_dir":
                config.general.out_dir = path.normpath(ReplaceMacros(option_block.values[0], project.macros))
            elif option_block.key == "int_dir":
                config.general.int_dir = path.normpath(ReplaceMacros(option_block.values[0], project.macros))
            elif option_block.key == "out_name":
                config.general.out_name = ReplaceMacros(option_block.values[0], project.macros)
            elif option_block.key == "toolset_version":
                # self.config.SetToolsetVersion(option_block.values[0])
                config.general.toolset_version = option_block.values[0]
        
        # multiple path options
        elif option_block.key in ("include_directories", "library_directories"):
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    value_list = ReplaceMacrosInList(project.macros, item.key, *item.values)
                    if option_block.key == "include_directories":
                        config.general.include_directories.extend(value_list)
                    elif option_block.key == "library_directories":
                        config.general.library_directories.extend(value_list)
        
        elif option_block.key in {"configuration_type", "type"}:
            # if option_block.values:
            #     # function will convert the option set to the enum
            #     self.config.SetConfiguration(option_block.values[0})
            if option_block.values:
                if option_block.values[0] in ("static_library", "dynamic_library", "application"):
                    config.general.configuration_type = option_block.values[0]
                else:
                    option_block.InvalidOption("static_library", "dynamic_library", "application")
        
        elif option_block.key == "language":
            if option_block.values:
                # function will convert the option set to the enum
                # self.config.SetLanguage(option_block.values[0})
                if option_block.values[0] in ("c", "cpp"):
                    config.general.language = option_block.values[0]
                else:
                    option_block.InvalidOption("c", "cpp")
    
    elif group_block.key == "compiler":
        # TODO: maybe do the same for the rest? only moving this to it's own function for source files
        ParseCompilerOption(project, config.compiler, option_block)
    
    elif group_block.key == "linker":
        if option_block.key in ("output_file", "debug_file", "import_library", "ignore_import_library"):
            if option_block.values:
                if option_block.key == "ignore_import_library":
                    # self.config.SetIgnoreImportLibrary(option_block.values[0])
                    if option_block.values[0] in ("true", "false"):
                        config.linker.ignore_import_library = option_block.values[0]
                    else:
                        option_block.InvalidOption("true", "false")
                    return
                
                # TODO: maybe split the extension here?
                value = path.normpath(ReplaceMacros(option_block.values[0], project.macros))
                
                if option_block.key in {"output_file", "output_file"}:
                    config.linker.output_file = value
                elif option_block.key == "debug_file":
                    config.linker.debug_file = value
                elif option_block.key == "import_library":
                    config.linker.import_library = value
        
        elif option_block.key in ("libraries", "ignore_libraries"):
            
            if option_block.key == "libraries":
                for item in option_block.items:
                    if SolveCondition(item.condition, project.macros):
                        if item.key != "-":
                            project.AddLib(item)
                        else:
                            project.RemoveLib(item)
            
            elif option_block.key == "ignore_libraries":
                for item in option_block.items:
                    if SolveCondition(item.condition, project.macros):
                        config.linker.ignore_libraries.extend(
                            ReplaceMacrosInList(project.macros, item.key, *item.values))
        
        elif option_block.key == "options":
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    config.linker.options.extend([item.key, *item.values])
    
    elif group_block.key in ("post_build", "pre_build", "pre_link"):
        value = ReplaceMacros(' '.join(option_block.values), project.macros)
        if value:
            # TODO: improve this, what if \\n is used in the file? it would just become \ and then new line, awful
            value = value.replace("\\n", "\n")
        
            if group_block.key == "post_build":
                config.post_build.append(value)
            
            elif group_block.key == "pre_build":
                config.pre_build.append(value)
            
            elif group_block.key == "pre_link":
                config.pre_link.append(value)
    
    else:
        group_block.Error("Unknown Configuration Group: ")
    
    return


def ParseCompilerOption(project, compiler, option_block):
    if option_block.key in ("preprocessor_definitions", "options"):
        for item in option_block.items:
            if SolveCondition(item.condition, project.macros):
                if option_block.key == "preprocessor_definitions":
                    compiler.preprocessor_definitions.extend(ReplaceMacrosInList(project.macros, *item.GetKeyValues()))
                elif option_block.key == "options":
                    compiler.options.extend(item.GetKeyValues())
    
    elif option_block.key == "precompiled_header":
        if option_block.values:
            # self.config.SetPrecompiledHeader(option_block.values[0])
            if option_block.values[0] in ("none", "create", "use"):
                compiler.precompiled_header = option_block.values[0]
            else:
                option_block.InvalidOption("none", "create", "use")
    
    elif option_block.key == "precompiled_header_file":
        compiler.precompiled_header_file = ReplaceMacros(option_block.values[0], project.macros)
    
    elif option_block.key in {"precompiled_header_out_file", "precompiled_header_out_file"}:
        compiler.precompiled_header_out_file = ReplaceMacros(option_block.values[0], project.macros)
    
    return


# configuration options unaffected by config and platform macros, run before it goes through each config/platform
def ParseGlobalConfigOptions() -> None:
    pass


def ReplaceMacrosInList(macros, *value_list):
    value_list = list(value_list)
    for index, item in enumerate(value_list):
        value_list[index] = ReplaceMacros(item, macros)
    return value_list


def ReplaceMacros(string, macros):
    if "$" in string:
        for macro, macro_value in macros.items():
            if macro in string:
                string_split = string.split(macro)
                string = macro_value.join(string_split)
    return string


# unused, idk if this will ever be useful either
def ReplaceExactMacros(split_string, macros):
    for macro, macro_value in macros.items():
        for index, item in enumerate(split_string):
            if macro == item:
                split_string[index] = macro_value
    
    return split_string


def ParseProject(project_dir, project_filename, base_macros, configurations, platforms, project_pass):
    project_path = project_dir + sep + project_filename
    project_name = path.splitext(project_filename)[0]
    
    if args.verbose:
        print("Reading: " + project_filename)
    
    project_file = ReadFile(project_filename)
    
    print("Parsing: " + project_filename)
    
    project_hash = qpc_hash.MakeHash(project_filename)
    project_list = Project(project_name, project_dir, base_macros)
    
    project_macros = {**base_macros, "$PROJECT_NAME": project_name}
    
    if args.time:
        start_time = perf_counter()
    
    # TODO: read all include files in the project, and then put them into a list here, and then use that in parsing
    #  and maybe even return them as well so you don't have to read the same file like 40 times?
    #  apparently ReadFile is actually really slow, oof
    
    # you might have to loop through all project types you want to make, aaaa
    # project_pass = 0
    for config in configurations:
        for platform in platforms:
            
            project_pass += 1
            if args.verbose:
                print("Pass {0}: {1} - {2}".format(
                    str(project_pass), config, platform))
            
            project = ProjectPass(project_macros, config, platform)
            project.hash_list[project_filename] = project_hash
            ParseProjectFile(project_file, project, project_path, "")
            project_list.AddParsedProject(project)
    
    if args.time:
        end_time = perf_counter()
        print("Finished Parsing Project - Time: " + str(end_time - start_time))
    
    return project_list, project_pass
