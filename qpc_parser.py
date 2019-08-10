# Parses Project Scripts, Base Scripts, Definition Files, and Hash Files

# TODO: figure out what is $CRCCHECK is
# may need to add a /checkfiles launch option to have this check if a file exists or not
# it would probably slow it down as well

import os
import hashlib
import qpc_base as base
import qpc_reader as reader
from pathlib import PurePath


class ProjectDefinition:
    def __init__( self, project_name, folder_list=[] ):
        self.name = project_name
        self.script_list = []

        # this is just so it stops changing this outside of the function
        self.group_folder_list = []
        self.group_folder_list.extend( folder_list )

    def AddScript(self, script_path):
        self.script_list.append(script_path)

    def AddScriptList(self, script_list):
        self.script_list.extend(script_list)


class ProjectGroup:
    def __init__( self, group_name ):
        self.name = group_name
        self.projects = []

    def AddProject(self, project_name, project_scripts, folder_list):
        project_def = ProjectDefinition( project_name, folder_list)
        project_def.AddScriptList(project_scripts)
        self.projects.append( project_def )


class Project:
    def __init__( self, macros, config, platform ):
        # self.file_name = name  # the actual file name
        self.config = Configuration()
        # self.source_files = []
        self.source_files = {}
        self.files = {}  # []
        self.dependencies = {}  # store project script paths here, "name": "path"

        self.hash_list = {}
        self.macros = { **macros,  "$" + config.upper(): "1", "$" + platform.upper(): "1", }

        self.config_name = config
        self.platform = platform

    def AddMacro( self, values ):
        key_name = "$" + values[0].upper()

        try:
            value = values[1]
        except IndexError:
            if key_name not in self.macros:
                self.macros[key_name] = ''
            return

        self.macros[ key_name ] = value

        self.ReplaceAnyUndefinedMacros()
        return

    def ReplaceAnyUndefinedMacros( self ):
        # this could probably be sped up 
        # TODO: add scanning of files and certain config settings
        for macro, value in self.macros.items():
            self.macros[ macro ] = ReplaceMacros( value, self.macros )
        
    def AddFile( self, folder_list, file_block ):
        wtf = ( file_block.key, *file_block.values )
        for file_path in ( file_block.key, *file_block.values ):
            if os.path.splitext(file_path)[1] in (".cpp", ".c", ".cxx"):
                if self.IsSourceFileAdded(file_path):
                    file_block.Warning("File already added")
                else:
                    # self.source_files[file_path] = (os.sep.join(folder_list), Compiler())
                    self.source_files[file_path] = SourceFile(folder_list)
                    continue
            else:
                if self.IsFileAdded(file_path):
                    file_block.Warning("File already added")
                else:
                    self.files[file_path] = os.sep.join(folder_list)
                    continue

    # unused currently, might use in the future
    def GetAllFileFolderDepthLists( self ):

        folder_lists = []
        for file_obj in self.files:
            if file_obj.folder_depth_list not in folder_lists and file_obj.folder_depth_list != []:
                folder_lists.append( file_obj.folder_depth_list )

        return folder_lists

    # Gets every single folder in the project, splitting each one as well
    # this function is awful
    def GetAllEditorFolderPaths(self):
        folder_paths = set()
        # TODO: is there a better way to do this?
        [folder_paths.add(path) for path in self.files.values()]
        [folder_paths.add(sf.folder) for sf in tuple([*self.source_files.values()])]

        full_folder_paths = set()
        # split every single folder because visual studio bad
        for folder_path in folder_paths:
            current_path = list(PurePath(folder_path).parts)
            if not current_path:
                continue
            folder_list = [current_path[0]]
            del current_path[0]
            for folder in current_path:
                folder_list.append( folder_list[-1] + os.sep + folder )
            full_folder_paths.update(folder_list)

        return tuple(full_folder_paths)

    def GetAllFolderPaths(self):
        folder_paths = set( GetAllPaths(self.files) )
        folder_paths.update( GetAllPaths(tuple([*self.source_files])) )
        return tuple(folder_paths)

    # TODO: update this for the newer version
    def GetFileObjectsInFolder( self, folder_list ):
        file_obj_list = []
        for file_obj in self.files:
            if file_obj.folder_depth_list == folder_list:
                file_obj_list.append( file_obj )
        return file_obj_list

    def IsFileAdded(self, file_path):
        try:
            return self.files[file_path]
        except KeyError:
            return False

    def IsSourceFileAdded(self, file_path):
        try:
            return self.source_files[file_path]
        except KeyError:
            return False

    def GetFileFolder(self, file_path):
        # TODO: setup try and except here if needed
        return self.files[file_path]

    def GetSourceFileFolder(self, file_path):
        return self.GetSourceFileObject(file_path)[1]

    def GetSourceFileOptions(self, file_path):
        return self.GetSourceFileObject(file_path)[0]

    def GetSourceFileObject(self, file_path):
        # TODO: setup try and except here
        return self.files[file_path]
        # return False

    def AddLib(self, lib_block):
        for lib_path in ( lib_block.key, *lib_block.values ):
            lib_path = self._FixLibPathAndExt(lib_path)
            if lib_path not in self.config.linker.libraries:
                self.config.linker.libraries.append( lib_path )
            else:
                lib_block.Warning("Library already added")

    def RemoveLib( self, lib_block ):
        for lib_path in lib_block.values:
            lib_path = self._FixLibPathAndExt(lib_path)
            if lib_path in self.config.linker.libraries:
                self.config.linker.libraries.remove(lib_path)
            else:
                lib_block.Warning("Trying to remove a library that hasn't been added yet")

    # actually do you even need the extension?
    def _FixLibPathAndExt(self, lib_path):
        lib_path = ReplaceMacros(lib_path, self.macros)
        return os.path.splitext(os.path.normpath(lib_path))[0] + self.macros["$_STATICLIB_EXT"]

    def RemoveFile( self, file_block ):
        for file_path in file_block.values:
            if os.path.splitext(file_path)[1] in (".cpp", ".c", ".cxx"):
                if file_path in self.source_files:
                    del self.source_files[file_path]
                else:
                    file_block.Warning("Trying to remove a file that hasn't been added yet")
            else:
                if file_path in self.files:
                    del self.files[file_path]
                else:
                    file_block.Warning("Trying to remove a file that hasn't been added yet")


class ProjectList:
    def __init__(self, name, path, base_macros):
        self.file_name = name  # the actual file name
        self.project_dir = path  # should use the macro instead tbh, might remove
        self.projects = []
        self.hash_dict = {}
        # shared across configs, used as a base for them
        self.macros = { **base_macros, "$PROJECT_DIR": path, "$PROJECT_NAME": name }

    def AddParsedProject(self, project):
        self.hash_dict.update({ **project.hash_list })

        # update them in case they changed (i doubt the project_dir will change though)
        self.macros.update({
            "$PROJECT_DIR": project.macros["$PROJECT_DIR"],
            "$PROJECT_NAME": project.macros["$PROJECT_NAME"],
        })

        del project.hash_list
        del project.macros["$PROJECT_DIR"]
        del project.macros["$PROJECT_NAME"]

        self.projects.append(project)

    # TODO: this is supposed to get all file objects in every project without duplicates
    #  need to finish this and make one for source_files
    def GetAllFileObjects( self, file_path ):
        return
        all_files = []
        for project in self.projects:
            for file_obj in project.files:
                if file_obj.path == file_path:
                    return file_obj
        return False

    def GetAllEditorFolderPaths(self):
        folder_paths = set()
        for project in self.projects:
            folder_paths.update(project.GetAllEditorFolderPaths())
        return tuple(folder_paths)

    def GetAllFolderPaths(self):
        folder_paths = set()
        for project in self.projects:
            folder_paths.update(project.GetAllFolderPaths())
        return tuple(folder_paths)


class SourceFile:
    def __init__( self, folder_list ):
        self.folder = os.sep.join(folder_list)
        self.compiler = Compiler()


class Configuration:
    def __init__( self ):
        self.general = General()
        self.compiler = Compiler()
        self.linker = Linker()
        self.post_build = PostBuild()


class General:
    def __init__( self ):
        self.out_dir = ''
        self.int_dir = ''
        self.configuration_type = ''
        self.language = ''
        self.toolset_version = ''
        self.include_directories = []
        self.library_directories = []
        self.options = []


class Compiler:
    def __init__( self ):
        self.preprocessor_definitions = []
        self.precompiled_header = ''
        self.precompiled_header_file = ''
        self.precompiled_header_output_file = ''
        self.options = []


class Linker:
    def __init__( self ):
        self.output_file = ''
        self.debug_file = ''
        self.import_library = ''
        self.ignore_import_library = ''
        self.libraries = []
        self.ignore_libraries = []
        self.options = []


class PostBuild:
    def __init__( self ):
        self.command_line = []
        self.use_in_build = ''


def GetAllPaths( path_list ):
    full_folder_paths = set()

    for folder_path in set(path_list):
        current_path = list(PurePath(os.path.split(folder_path)[0]).parts)
        if not current_path:
            continue
        folder_list = [current_path[0]]
        del current_path[0]
        for folder in current_path:
            folder_list.append( folder_list[-1] + os.sep + folder )
        full_folder_paths.update(folder_list)

    return tuple(full_folder_paths)


def SolveCondition(condition, macros):
    if not condition:
        return True

    sub_cond_values = []

    # split by "(" for any sub conditionals
    # maybe do the same for anything with "!" in it?
    if "(" in condition:
        sub_cond_line = (condition.split('(')[1]).split(')')[0]

        sub_cond_values.append(SolveCondition(sub_cond_line, macros))

        # convert the booleans to ints
        sub_cond_values = [boolean * 1 for boolean in sub_cond_values]

        condition = (condition.split('('))
        condition = condition[0] + condition[1].split(')')[1]

    condition = ReplaceMacros(condition, macros)

    operator_list = ["||", "&&", ">=", "<=", "==", "!=", ">", "<"]

    cond_list = []
    cond_test = []

    if not cond_list:
        for operator in operator_list:
            if operator in condition:
                cond_list.extend(condition.split(operator))

                if operator == "||" or operator == "&&":
                    cond_test.append(operator)
                else:
                    cond_test = operator
                    break

    if not cond_list:
        cond_list.append(condition)

    # are there any empty values here?
    if '' in cond_list:
        del cond_list[cond_list.index('')]

    for cond in cond_list:
        cond_index = cond_list.index(cond)
        if cond.startswith("!"):
            try:
                cond_value = int(not cond[1:])
            except ValueError:
                if "$" in cond:
                    cond_value = 1
                else:
                    # maybe raise an exception for trying to set a string to the opposite instead?
                    cond_value = 0
        else:
            try:
                cond_value = int(cond)
            except ValueError:
                if "$" in cond:
                    cond_value = 0
                else:
                    cond_value = cond

        cond_list[cond_index] = cond_value

    [cond_list.insert(0, value) for value in sub_cond_values]

    # must be a single condition
    if not cond_test:
        if not cond_value:
            return False  # ?
        elif type(cond_value) == int:
            return bool(cond_value)
        else:
            return True

    elif "||" in cond_test or "&&" in cond_test:
        for test in cond_test:

            # TODO: fix these for strings, though idk if you could even compare them here anyway
            if test == "||":
                # can't be below zero
                if sum(cond_list) > 0:
                    return True

            elif test == "&&":
                # all of them have to be true, so we can't have any False
                if 0 not in cond_list:
                    return True
    else:
        if cond_test == "==":
            if cond_list[0] == cond_list[1]:
                return True

        elif cond_test == "!=":
            if cond_list[0] != cond_list[1]:
                return True

        # TODO: test this
        if type(cond_list[0]) == int and type(cond_list[1]) == int:
            if cond_test == ">":
                if cond_list[0] > cond_list[1]:
                    return True

            elif cond_test == ">=":
                if cond_list[0] >= cond_list[1]:
                    return True

            elif cond_test == "<=":
                if cond_list[0] <= cond_list[1]:
                    return True

            elif cond_test == "<":
                if cond_list[0] < cond_list[1]:
                    return True

    return False


def ParseBaseFile(base_file, macros, unknown_macros, project_list, group_dict):

    configurations = []
    for project_block in base_file:

        if project_block.key == "cmd_conditionals":

            for sub_project_block in project_block.items:
                if sub_project_block.key.upper() in unknown_macros:
                    if SolveCondition(sub_project_block.condition, macros):
                        macros[ "$" + sub_project_block.key ] = "1"
                        del unknown_macros[ unknown_macros.index(sub_project_block.key.upper())]

        elif project_block.key == "project":
            project_def = ProjectDefinition(project_block.values[0])

            for item in project_block.items:
                if SolveCondition(item.condition, macros):
                    item.key = ReplaceMacros(item.key, macros)
                    project_def.AddScript(item.key)
                    # project_dict[ project_block.values[0] ].append( item.key )
            project_list.append(project_def)

        elif project_block.key == "group":
            # TODO: fix this for multiple groups
            for group in project_block.values:

                # do we have a group with this name already?
                if group in group_dict:
                    project_group = group_dict[ group ]
                else:
                    project_group = ProjectGroup( group )

                ParseProjectGroupItems(project_group, project_list, project_block, macros)
                group_dict[ project_group.name ] = project_group

        elif project_block.key == "macro":
            macros[ "$" + project_block.values[0].upper() ] = ReplaceMacros( project_block.values[1], macros )

        elif project_block.key == "configurations":
            for item in project_block.items:
                if SolveCondition(item.condition, macros):
                    configurations.append(item.key)

        elif project_block.key == "include":
            # "Ah shit, here we go again."
            path = os.path.normpath(ReplaceMacros( project_block.values[0], macros ))

            # maybe add a depth counter like in parsing projects?
            if base.FindCommand( "/verbose" ):
                print( "Reading: " + path )

            if not os.path.isabs(path):
                path = os.path.normpath(macros["$ROOTDIR"] + os.sep + path)

            include_file = reader.ReadFile( path )
            ParseBaseFile(include_file, macros, unknown_macros, project_list, group_dict)

        else:
            project_block.Warning("Unknown Key: ")

    return configurations


def ParseProjectGroupItems(project_group, project_list, project_block, macros, folder_list=None):
    if not folder_list:
        folder_list = []

    for item in project_block.items:
        if SolveCondition(item.condition, macros):

            if item.key == "folder":
                folder_list.append( item.values[0] )
                ParseProjectGroupItems(project_group, project_list, item, macros, folder_list)
                folder_list.remove( item.values[0] )
            else:
                for project in project_list:
                    if project.name == item.key:
                        project_group.AddProject(project.name, project.script_list, folder_list)
    return


def ParseProjectFile(project_file, project, depth=0):
    for project_block in project_file:

        # check if the conditional result is true before checking the key
        if SolveCondition(project_block.condition, project.macros):

            for value in project_block.values:
                index = project_block.values.index( value )
                project_block.values[ index ] = ReplaceMacros( value, project.macros )

            if project_block.key == "macro":
                project.AddMacro( project_block.values )

            elif project_block.key == "configuration":
                ParseConfigBlock(project_block, project)

            elif project_block.key == "files":
                ParseFilesBlock(project_block, project, [])

            elif project_block.key == "dependencies":
                project_block.Warning("Project Dependencies are not setup yet")

            elif project_block.key == "include":
                # Ah shit, here we go again.
                path = project_block.values[0]
                include_file = IncludeFile(path, project, depth)
                ParseProjectFile( include_file, project, depth )
                PrintIncludeFileFinished(path, depth)

            else:
                project_block.Warning("Unknown key: ")
    return


def IncludeFile(path, project, depth):
    if base.FindCommand("/verbose"):
        depth += 1
        space = []
        while len(space) < depth:
            space.append("    ")

        print(''.join(space) + "Reading: " + path)

    # full_path = os.path.join( project.macros[ "$PROJECT_DIR" ], path )
    full_path = os.path.normpath(project.macros["$PROJECT_DIR"] + os.sep + path)

    project.hash_list[path] = MakeHash(full_path)
    include_file = reader.ReadFile(full_path)

    if base.FindCommand("/verbose"):
        print(''.join(space) + "Parsing: " + path)

    return include_file


def PrintIncludeFileFinished(path, depth):
    if base.FindCommand("/verbose"):
        depth += 1
        space = []
        while len(space) < depth:
            space.append("    ")
        print(''.join(space) + "Parsed: " + path)
        depth -= 1


def ParseLibrariesBlock(libraries_block, project):
    if SolveCondition(libraries_block.condition, project.macros):
        for library in libraries_block.items:
            if SolveCondition(library.condition, project.macros):

                if library.key == "-":
                    library_path = ReplaceMacros( library.values[0], project.macros )
                    project.RemoveLib(library_path)
                else:
                    library_path = ReplaceMacros( library.key, project.macros )
                    project.AddLib(library_path)


def ParseFilesBlock(files_block, project, folder_list):
    if SolveCondition(files_block.condition, project.macros):
        for block in files_block.items:
            if SolveCondition(block.condition, project.macros):

                if block.key == "folder":
                    folder_list.append(block.values[0])
                    ParseFilesBlock( block, project, folder_list )
                    folder_list.remove(block.values[0])

                elif block.key == "-":
                    for index, value in enumerate(block.values):
                        block.values[index] = ReplaceMacros( value, project.macros )
                    project.RemoveFile( block )
                else:
                    block.key = ReplaceMacros( block.key, project.macros )
                    project.AddFile( folder_list, block )

                    # if block.items:
                    #     block.Warning("Source File Compiler options aren't setup yet")


def ParseConfigBlock(project_block, project, file_obj=None):
    if SolveCondition(project_block.condition, project.macros):

        if file_obj:
            print( "setup file_obj's" )
            pass

        for group_block in project_block.items:
            if SolveCondition(group_block.condition, project.macros):
                for option_block in group_block.items:
                    if SolveCondition(option_block.condition, project.macros):
                        ParseConfigOption(project, group_block, option_block, file_obj)


# this could be so much better
def ParseConfigOption(project, group_block, option_block, file_obj=None):
    if file_obj:
        config = file_obj.config
    else:
        config = project.config

    if group_block.key == "general":
        # single path options
        if option_block.key in ("out_dir", "int_dir"):
            if option_block.key == "out_dir":
                config.general.out_dir = os.path.normpath(ReplaceMacros(option_block.values[0], project.macros))
            elif option_block.key == "int_dir":
                config.general.int_dir = os.path.normpath(ReplaceMacros(option_block.values[0], project.macros))

        # multiple path options
        elif option_block.key in ("include_directories", "library_directories"):
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    value_list = ReplaceMacrosInList(project.macros, item.key, *item.values)
                    if option_block.key == "include_directories":
                        config.general.include_directories.extend(value_list)
                    elif option_block.key == "library_directories":
                        config.general.library_directories.extend(value_list)

        elif option_block.key == "configuration_type":
            if option_block.values:
                if option_block.values[0] in ("static_library", "dynamic_library", "application"):
                    config.general.configuration_type = option_block.values[0]
                else:
                    option_block.InvalidOption( "static_library", "dynamic_library", "application" )

        elif option_block.key == "language":
            if option_block.values:
                if option_block.values[0] in ("c", "cpp"):
                    config.general.language = option_block.values[0]
                else:
                    option_block.InvalidOption( "c", "cpp" )

    elif group_block.key == "compiler":

        if option_block.key in ("preprocessor_definitions", "options"):
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    if option_block.key == "preprocessor_definitions":
                        config.compiler.preprocessor_definitions.extend([item.key, *item.values])
                    elif option_block.key == "options":
                        config.compiler.options.extend([item.key, *item.values])

        elif option_block.key == "precompiled_header":
            if option_block.values:
                if option_block.values[0] in ("none", "create", "use"):
                    config.compiler.precompiled_header = option_block.values[0]
                else:
                    option_block.InvalidOption("none", "create", "use")

        elif option_block.key in ("precompiled_header_file", "precompiled_header_output_file"):
            config.compiler.precompiled_header = ReplaceMacros(option_block.values[0], project.macros)

    elif group_block.key == "linker":

        if option_block.key in ("output_file", "debug_file", "import_library", "ignore_import_library"):
            if option_block.values:

                if option_block.key == "ignore_import_library":
                    if option_block.values[0] in ("true", "false"):
                        config.linker.ignore_import_library = option_block.values[0]
                    else:
                        option_block.InvalidOption( "true", "false" )
                    return

                # TODO: maybe split the extension here?
                value = os.path.normpath(ReplaceMacros(option_block.values[0], project.macros))

                if option_block.key == "output_file":
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
                            project.AddLib( item )
                        else:
                            project.RemoveLib( item )

            elif option_block.key == "ignore_libraries":
                for item in option_block.items:
                    if SolveCondition(item.condition, project.macros):
                        config.linker.ignore_libraries.extend(ReplaceMacrosInList(project.macros, item.key, *item.values))

        elif option_block.key == "options":
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    config.linker.options.extend([item.key, *item.values])

    elif group_block.key == "post_build":

        if group_block.key == "post_build":
            event = config.post_build

        # elif group_block.key == "pre_build":
        #     event = config.pre_build

        # elif group_block.key == "pre_link":
        #     event = config.pre_link

        else:
            raise Exception("how tf did you get here, "
                            "should only get here with post_build, pre_build, and pre_link")

        if option_block.key == "command_line":
            value = ReplaceMacros(' '.join( option_block.values ), project.macros)
            if value:
                value = value.replace("\\n", "\n")
                event.command_line.append(value)

        elif option_block.key == "use_in_build":
            if option_block.values:
                if option_block.values[0] in ("true", "false"):
                    event.use_in_build = option_block.values[0]
                else:
                    option_block.InvalidOption("true", "false")

    else:
        group_block.Error("Unknown Configuration Group: ")

    return


def ReplaceMacrosInList( macros, *value_list ):
    value_list = list(value_list)
    for index, item in enumerate(value_list):
        value_list[index] = ReplaceMacros( item, macros )
    return value_list


def ReplaceMacros( string, macros ):
    if "$" in string:
        # go through all the known macros and check if each one is in the value
        for macro, macro_value in macros.items():
            if macro in string:
                string_split = string.split( macro )
                string = str(macro_value).join( string_split )
    return string


def ParseProject( project_script_path, base_macros, configurations, platforms ):
    project_dir, project_filename = os.path.split(project_script_path)
    project_name = os.path.splitext(project_filename)[0]

    if not os.path.isabs(project_dir):
        project_dir = os.path.normpath(base_macros["$ROOTDIR"] + "/" + project_dir)

    project_script_path = os.path.normpath(project_dir + "/" + project_filename)

    if base.FindCommand( "/verbose" ):
        print( "Reading: " + project_filename )

    project_file = reader.ReadFile(project_script_path)

    print( "Parsing: " + project_filename )

    project_hash = MakeHash(project_script_path)
    # project_list = []
    project_list = ProjectList(project_name, project_dir, base_macros)

    project_macros = { **base_macros, "$PROJECT_DIR": project_dir, "$PROJECT_NAME": project_name }

    for config in configurations:
        for platform in platforms:
            project = Project(project_macros, config, platform)
            project.hash_list[project_filename] = project_hash
            # AddConfigPlatform( project, project.macros )
            ParseProjectFile(project_file, project, 0)
            project_list.AddParsedProject(project)
    return project_list


# TODO: maybe move to a file called "qpc_hash.py",
#  so you can run this from vstudio or something to check hash only?
def HashCheck( root_dir, project_path ):
    project_hash_file_path = os.path.join( root_dir, project_path + "_hash" )

    if os.sep in project_path:
        project_path = project_path.rsplit( os.sep, 1 )[0]
    else:
        project_path = ''

    project_dir = os.path.normpath( root_dir + project_path ) + os.sep

    # open the hash file if it exists,
    # run MakeHash on every file there
    # and check if it matches what MakeHash returned
    if os.path.isfile( project_hash_file_path ):
        with open(project_hash_file_path, mode="r", encoding="utf-8") as hash_file:
            hash_file = hash_file.read().splitlines()

        for hash_line in hash_file:
            hash_line = hash_line.split(" ")
            if os.path.isabs(hash_line[1]):
                project_file_path = os.path.normpath( hash_line[1] )
            else:
                project_file_path = os.path.normpath( project_dir + os.sep + hash_line[1] )

            if hash_line[0] != MakeHash( project_file_path ):
                print( "Invalid: " + hash_line[1] + "_hash" )
                return True

        return False
    else:
        print( "Hash File does not exist" )
        return True


# Source: https://bitbucket.org/prologic/tools/src/tip/md5sum
def MakeHash(filename):
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(128 * hashlib.md5().block_size), b""):
            hashlib.md5().update(chunk)
    return hashlib.md5().hexdigest()


def WriteHashList(tmp_file, hash_list):
    for project_script_path, hash_value in hash_list.items():
        tmp_file.write( hash_value + " " + project_script_path + "\n" )
    return
