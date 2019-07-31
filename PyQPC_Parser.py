# Parses Project Scripts, Base Scripts, Definition Files, and Hash Files

# TODO: figure out what is $CRCCHECK is
# may need to add a /checkfiles launch option to have this check if a file exists or not
# it would probably slow it down as well

import os
import hashlib
import PyQPC_Base as base


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


# TODO: add line number and file path for error reporting
# otherwise you would have to use /v and search in the file manually, ugh
class ProjectBlock:
    def __init__( self, key, values=None, condition=None ):
        self.key = key
        if values:
            self.values = values
        else:
            self.values = []
        self.condition = condition
        self.items = []

    def AddItem( self, item ):
        self.items.append( item )


class Project:
    def __init__( self, name, path, macros ):
        self.file_name = name  # the actual file name
        # self.path = path # folder the project script is in (using $PROJECTDIR instead, maybe use this instead?)
        
        self.source_files = []
        self.files = []

        self.libraries = {}  # []
        # self.dependencies = {}  # []  # store project script paths here

        # maybe add an "self.other_files" dictionary where the files aren't objects and just the paths?
        # and only use self.files for h and cpp files?

        self.configs = []

        self.hash_list = {}

        self.macros = { **macros, "$PROJECT_DIR": path, "$PROJECT_NAME": name }

        self.name = self.macros["$PROJECT_NAME"]  # the project name

    def AddMacro( self, values ):
        key_name = "$" + values[0].upper()

        if key_name == "$_CONFIG" or key_name == "$_PLATFORM":
            raise Exception( "You cannot change the value of \"" + key_name + "\" in a project script." +
                             "\nIf you want to change it, change it in the base file(s)" )

        try:
            value = values[1]
        except IndexError:
            value = ''

        # if key_name not in self.macros:
        self.macros[ key_name ] = value

        self.ReplaceAnyUndefinedMacros()
        return

    def ReplaceAnyUndefinedMacros( self ):
        # this could probably be sped up 
        # TODO: add scanning of files and certain config settings
        for macro, value in self.macros.items():
            self.macros[ macro ] = ReplaceMacros( value, self.macros )
        
    def AddFile( self, folder_list, file_path ):

        if file_path.endswith(".cpp") or  file_path.endswith(".c") or file_path.endswith(".cxx"):
            file_obj = self.GetSourceFileObject( file_path )
        else:
            file_obj = self.GetFileObject( file_path )

        if file_obj:
            if not base.FindCommand( "/hidewarnings" ):
                print( "WARNING: File already added: \"" + file_path + "\"" )
        else:
            if file_path.endswith(".cpp") or file_path.endswith(".c") or file_path.endswith(".cxx"):
                self.source_files.append(SourceFile(file_path, folder_list))
            else:
                self.files.append(File(file_path, folder_list))

    # unused currently, might use in the future
    def GetAllFileFolderDepthLists( self ):

        folder_lists = []
        for file_obj in self.files:
            if file_obj.folder_depth_list not in folder_lists and file_obj.folder_depth_list != []:
                folder_lists.append( file_obj.folder_depth_list )

        return folder_lists

    def GetAllFileFolderPaths( self ):

        folder_paths = []
        for file_obj in self.files:
            if file_obj.folder_path not in folder_paths and file_obj.folder_path != '':
                folder_paths.append( file_obj.folder_path )

        for file_obj in self.source_files:
            if file_obj.folder_path not in folder_paths and file_obj.folder_path != '':
                folder_paths.append( file_obj.folder_path )

        return folder_paths

    def GetFileObjectsInFolder( self, folder_list ):

        file_obj_list = []
        for file_obj in self.files:
            if file_obj.folder_depth_list == folder_list:
                file_obj_list.append( file_obj )

        return file_obj_list

    def GetFileObject( self, file_path ):
        for file_obj in self.files:
            if file_obj.path == file_path:
                return file_obj
        return False

    def GetSourceFileObject( self, file_path ):
        for file_obj in self.source_files:
            if file_obj.path == file_path:
                return file_obj
        return False

    def AddLib(self, lib_path, implib=False):
        lib_path = self.FixLibPathAndExt(lib_path, implib)

        libraries = self.libraries[self.macros["$_CONFIG"]][self.macros["$_PLATFORM"]]

        if lib_path not in libraries:
            libraries.append( lib_path )
        else:
            if not base.FindCommand("/hidewarnings"):
                print( "WARNING: Library already added: \"" + lib_path + "\"" )

        # if lib_path not in self.dependencies:
        #     self.dependencies.append( lib_path )
        # else:
            # if not base.FindCommand("/hidewarnings"):
                # print( "WARNING: Dependency already added: \"" + lib_path + "\"" )

    def RemoveLib( self, lib_path, implib=False ):
        lib_path = self.FixLibPathAndExt(lib_path, implib)
        self.libraries[self.macros["$_CONFIG"]][self.macros["$_PLATFORM"]].remove(lib_path)
        # self.dependencies.remove(lib_path)

    def FixLibPathAndExt(self, lib_path, implib=False):
        lib_path = os.path.normpath(lib_path)

        if implib:
            lib_ext = self.macros["$_IMPLIB_EXT"]
        else:
            lib_ext = self.macros["$_STATICLIB_EXT"]

        # this would break if, for whatever reason, we have a different extension
        if not lib_path.endswith( lib_ext ):
            lib_path += lib_ext

        return lib_path

    def RemoveFile( self, file_list ):
        for file_obj in self.files:
            if file_obj.path in file_list:
                del self.files[ self.files.index(file_obj) ]
                break


class File:
    def __init__( self, file_path, folder_list ):
        self.path = file_path

        # folder layout in any editor you want to use
        self.folder_depth_list = []
        self.folder_depth_list.extend( folder_list )  # make sure it's a list even if it's a string
        self.folder_path = os.sep.join( folder_list )


# class ProjectFile:
class SourceFile(File):
    def __init__( self, file_path, folder_list ):
        # super().__init__( file_path, folder_list )
        File.__init__( self, file_path, folder_list )
        self.compiler = {}


class Configuration:
    def __init__( self, config_name, platform_name ):
        self.config_name = config_name
        self.platform_name = platform_name

        self.general = {
            "out_dir": "",
            "int_dir": "",
            "configuration_type": "",
            "language": "",
            "include_directories": [],
            "library_directories": [],
            "options": [],
        }

        self.compiler = {
            "include_directories": [],
            "preprocessor_definitions": [],
            "options": [],
            # "treat_warning_as_error": "",
        }

        self.linker = {
            "library_directories": [],
            "options": [],
        }

        self.post_build = {
            "command_line": [],
            "use_in_build": "",
        }


def AddConfigPlatform( project, macros ):
    config, platform = macros["$_CONFIG"], macros["$_PLATFORM"]
    # maybe change configuration to work the same as the rest?
    project.configs.append( Configuration(config, platform) )

    base.CreateNewDictValue(project.libraries, config, "dict")
    project.libraries[config].update({ platform: [] })

    # base.CreateNewDictValue(project.dependencies, config, "dict")
    # project.dependencies[config].update({ platform: [] })
    return


def AddConfigPlatformForFile( file_obj, macros ):
    config, platform = macros["$_CONFIG"], macros["$_PLATFORM"]
    file_obj.configs.append( Configuration(config, platform) )
    return


def AddConfigOption(config_group, option_name, option_value):

    if type(config_group[option_name]) == str:
        config_group[option_name] = option_value

    elif type(config_group[option_name]) == list:
        config_group[option_name].append(option_value)

    else:
        print( "wtf" )


# maybe add a depth variable here as well? idk
def ReadFile( path ):

    with open( path, mode="r", encoding="utf-8" ) as file:
        file = file.read().splitlines()
    file = RemoveCommentsAndFixLines( file )
    file = _FormatConfigBlocks( file )
    file = CreateFileBlockObjects( file )

    return file


def RemoveCommentsAndFixLines( config ):
    in_comment = False
    in_quote = False
    new_config = []

    for line_num, line in enumerate(config):
        # TODO: check for quotes before removing comments,
        # we don't want to remove comments that are in quotes
        # removes all multi-line comments from the line
        # line = re.sub(r'/\*.*?\*/', r'', line)

        new_line = ''
        for char_num, char in enumerate(line):

            if not in_comment:
                if char == '"' and not line[char_num-1] == "\\":
                    in_quote = not in_quote

                if not in_quote and char_num+1 < len(line):
                    if char == "/" and line[char_num+1] == "/":
                        break

                    if char == "/" and line[char_num+1] == "*":
                        in_comment = True
                        char = ''

                if char == "\t":
                    char = ' '

                new_line += char

            elif line[char_num-1] == "*" and char == "/":
                in_comment = False

        new_line = _RemoveQuotesAndSplitLine(new_line)

        if new_line:
            new_line = JoinConditionLine(new_line)
            new_config.append(new_line)

    return new_config


# remove quotes in the string if there is any
def _RemoveQuotesAndSplitLine( line ):

    # add a gap in between these if they exist just in case
    # so we can have no spaces in the actual file if we want
    # line = line.replace( "{", " { ")
    # line = line.replace( "}", " } ")

    line_split = []
    raw_line_split = line.split(" ")

    str_num = 0
    while str_num < len( raw_line_split ):
        string = raw_line_split[ str_num ]

        if string.startswith( '"' ) or '\\"' in string:

            if string.endswith( '"' ):
                str_len = len( string )
                string = string[ 1: str_len-1 ]

            else:
                quote = string[1:]  # strip the start quote off
                quote_str_num = str_num + 1

                # this will keep adding strings together until one of them ends with a quote
                while quote_str_num < len(raw_line_split) and ( quote.endswith('\\"') or not quote.endswith('"') ):
                    quote += " " + raw_line_split[ quote_str_num ]
                    quote_str_num += 1

                if '\\"' in quote:
                    # replace '\\"' with '"'
                    quote = '"'.join(quote.split('\\"'))

                str_num = quote_str_num - 1
                string = quote[:-1]  # strip the end quote off

        elif not string:
            str_num += 1
            continue

        line_split.append(string)
        str_num += 1

    return line_split


def JoinConditionLine(line_split):

    cond_line_len, cond_line = GetConditionLine(line_split)

    new_line_split = line_split
    # get rid of the conditional from the line
    if cond_line:
        for string in line_split:
            if "[" in string:
                # line_split = line_split[ :line_split.index(string) ]
                index = line_split.index(string)
                new_line_split = line_split[ :index ]
                new_line_split.append( cond_line )
                new_line_split.extend( line_split[ index+cond_line_len: ] )
                break

    return new_line_split


def GetConditionLine(line_split):

    found_cond = False
    cond_len = 0

    for string_num, string in enumerate(line_split):
        if "[" in string:
            if cond_len == 0:
                found_cond = line_split[ string_num ]

        if found_cond:
            cond_len += 1
            if "]" in string:
                break

    if found_cond != False:
        line = ''.join(line_split)
        cond_line = "[" + ( line.split( "[" )[1] ).split( "]" )[0] + "]"
        return cond_len, cond_line

    return 0, None


# Re-Formats the config, so no more blocks in one single line
def _FormatConfigBlocks(script):

    new_config = []
    for line_num, split_line in enumerate(script):

        if "{" in split_line or "}" in split_line:
            new_split_line = []
            for item in split_line:

                if "{" in item or "}" in item:
                    # what about if the length is over 2?
                    if new_split_line:
                        new_config.append( new_split_line )
                    new_config.append([item])
                    new_split_line = []

                elif len(new_split_line) >= 2:
                    new_config.append( new_split_line )
                    new_split_line = [item]

                else:
                    new_split_line.append( item )

            # new_config.append( new_split_line )

        elif len(new_config) > 1 and len(new_config[-1]) > 1 and new_config[-1][-1] == "\\":
            if split_line:
                del new_config[-1][-1]
                new_config[-1].extend( split_line )
            continue

        else:
            new_config.append( split_line )

    return new_config


# Purpose: to clean up the project script to make parsing it easier
def CreateFileBlockObjects( file ):

    cleaned_file = []

    line_num = 0
    while line_num < len( file ):

        if file[ line_num ] == '':
            line_num += 1
            continue

        line_num, block = GetFileBlockSplit( file, line_num )

        line_num = line_num - 1
        block = CreateFileBlockObject( block )
        cleaned_file.append( block )
            
        line_num += 1
        continue

    return cleaned_file


def CreateFileBlockObject( block ):

    value_list = []
    condition = None
    
    value_index = 1
    while len(block[0]) > value_index:

        # don't add any conditional to the value_list
        if "[" in block[0][value_index] or "]" in block[0][value_index]:
            condition = block[0][value_index][1:-1]  # no brackets on the ends
        else:
            value_list.append( block[0][value_index] )
        value_index += 1

    key = ProjectBlock( block[0][0], value_list, condition )

    if len( block ) > 1:

        block_line_num = 1
        while block_line_num < len( block ):

            if block[ block_line_num ] != [] and block[ block_line_num ][0] != '{' and block[ block_line_num ][0] != '}':

                sub_block = GetFileBlockSplit( block, block_line_num )

                if isinstance( sub_block[1], list ):
                    block_line_num = sub_block[0]  # - 1
                    sub_block = CreateFileBlockObject( sub_block[1] )
                    key.AddItem( sub_block )
                    continue

            block_line_num += 1

    return key


# Returns a block into a list with each string split up starting from a line number
def GetFileBlockSplit( file, line_number ):

    block_depth_num = 0

    block = [file[line_number]]
    if file[line_number] == ['{']:
        block_depth_num = 1
    # else:
    # if file[ line_number ] != ["{"]:
    #     return [ line_number, block ]

    line_number += 1

    while line_number < len( file ):

        current_line = file[ line_number ]
        
        # the value is split across multiple lines
        if len(block[-1]) > 1:
            if block_depth_num == 0 and current_line == []:
                break

        if current_line != []:
            if ( current_line == ['{'] ) or ( block_depth_num != 0 ):
                block.append( current_line )

            elif len(block[-1]) > 1:
                if block_depth_num == 0:
                    # this is a single line block like $Macro
                    break

            else:
                break

        if current_line == ["{"]:
            block_depth_num += 1

        if current_line == ["}"]:
            block_depth_num -= 1

        line_number += 1

    return line_number, block


# ------------------------------------------------------------------------------------------


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
                # maybe raise an exception for trying to set a string to the opposite instead?
                cond_value = 0
        else:
            try:
                cond_value = int(cond)
            except ValueError:
                cond_value = cond

        cond_list[cond_index] = cond_value

    [cond_list.insert(0, value) for value in sub_cond_values]

    # must be a single condition
    if not cond_test:
        if not cond_value:
            return False  # ?
        elif type(cond_value) == int:
            return bool(cond_value)

        # might be an undefined macro, so return False
        elif "$" in cond_value:
            return False
        else:
            return True

    elif "||" in cond_test or "&&" in cond_test:
        for test in cond_test:

            if test == "||":
                # can't be below zero
                if sum(cond_list) > 0:
                    return True

            elif test == "&&":
                # all of them have to be true, so we can't have any False
                if not 0 in cond_list:
                    return True
    else:

        # TODO: make these 2 support strings
        if cond_test == "==":
            if cond_list[0] == cond_list[1]:
                return True

        elif cond_test == "!=":
            if cond_list[0] != cond_list[1]:
                return True

        # TODO: have all these below be integers only
        elif cond_test == ">":
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

    configurations, platforms = [], []
    for project_block in base_file:

        if project_block.key == "cmd_conditionals":

            for sub_project_block in project_block.items:
                if sub_project_block.key.upper() in unknown_macros:
                    if SolveCondition(sub_project_block.condition, macros):
                        macros[ "$" + sub_project_block.key.upper() ] = 1
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

        elif project_block.key == "platforms":
            for item in project_block.items:
                if SolveCondition(item.condition, macros):
                    platforms.append(item.key)

        elif project_block.key == "include":
            # "Ah shit, here we go again."
            path = os.path.normpath(ReplaceMacros( project_block.values[0], macros ))

            # maybe add a depth counter like in parsing projects?
            if base.FindCommand( "/verbose" ):
                print( "Reading: " + path )

            if not os.path.isabs(path):
                path = os.path.normpath(macros["$ROOTDIR"] + os.sep + path)

            include_file = ReadFile( path )
            ParseBaseFile(include_file, macros, unknown_macros, project_list, group_dict)

        else:
            print( "Unknown Key: " + project_block.key )

    return configurations, platforms


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


# this is the first pass of the project file only reading things that
# won't be affected by the dynamic macros ($_CONFIG and $_PLATFORM) to save time
def ParseProjectFile(project_file, project, depth=0):
    for project_block in project_file:

        # check if the conditional result is true before checking the key
        if SolveCondition(project_block.condition, project.macros):

            for value in project_block.values:
                index = project_block.values.index( value )
                project_block.values[ index ] = ReplaceMacros( value, project.macros )

            # should i just have it be a macro in the file instead?
            if project_block.key == "project_name":
                project.macros["$PROJECT_NAME"] = project_block.values[0]
                project.name = project_block.values[0]

            # issue with these: after the 1st path, it tries adding the same thing again
            # if something is added only on a certain config or platform, it would be added to all here
            # fuck
            # i might have to do the same thing with configuration here, ugh
            elif project_block.key == "files":
                ParseFilesBlock(project_block, project, [])

            elif project_block.key == "macro":
                project.AddMacro( project_block.values )

            elif project_block.key == "include":
                # Ah shit, here we go again.
                path = project_block.values[0]
                include_file = IncludeFile(path, project, depth)
                ParseProjectFile( include_file, project, depth )
                PrintIncludeFileFinished(path, depth)

            elif project_block.key == "configuration" or project_block.key == "libraries":
                pass

            else:
                print( "WARNING: Unknown key found: " + project_block.key )
    return


# this is run multiple times depending on how many configurations and platforms being used
def ParseProjectFileMulti(project_file, project, depth=0):
    for project_block in project_file:

        # check if the conditional result is true before checking the key
        if SolveCondition(project_block.condition, project.macros):

            for value in project_block.values:
                index = project_block.values.index( value )
                project_block.values[ index ] = ReplaceMacros( value, project.macros )

            if project_block.key == "configuration":
                ParseConfigBlock(project_block, project)

            elif project_block.key == "libraries":
                ParseLibrariesBlock(project_block, project)

            elif project_block.key == "macro":
                project.AddMacro( project_block.values )

            elif project_block.key == "include":
                # Ah shit, here we go again.
                path = project_block.values[0]
                include_file = IncludeFile(path, project, depth)
                ParseProjectFileMulti( include_file, project, depth )
                PrintIncludeFileFinished(path, depth)

            elif project_block.key == "project_name" or project_block.key == "files":
                pass

            else:
                print( "WARNING: Unknown key found: " + project_block.key )
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
    include_file = ReadFile(full_path)

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
                    block.values = ReplaceMacros( block.values[0], project.macros )
                    project.RemoveFile(block.values)
                else:
                    block.key = ReplaceMacros( block.key, project.macros )
                    project.AddFile( folder_list, block.key )


def ParseConfigBlock(project_block, project, file_obj=None):
    if SolveCondition(project_block.condition, project.macros):

        if file_obj:
            AddConfigPlatformForFile(file_obj, project.macros)

        for group_block in project_block.items:
            if SolveCondition(group_block.condition, project.macros):
                for option_block in group_block.items:
                    if SolveCondition(option_block.condition, project.macros):
                        ParseConfigOption(project, group_block.key, option_block, file_obj)


# this could be so much better
def ParseConfigOption(project, group_name, option_block, file_obj = None):
    config = None
    if file_obj:
        for config_obj in file_obj.configs:
            if config_obj.config_name == project.macros["$_CONFIG"] and \
                    config_obj.platform_name == project.macros["$_PLATFORM"]:
                config = config_obj
                break
    else:
        for config_obj in project.configs:
            if config_obj.config_name == project.macros["$_CONFIG"] and \
                    config_obj.platform_name == project.macros["$_PLATFORM"]:
                config = config_obj
                break

    if group_name == "general":
        if option_block.key in ("out_dir", "int_dir"):
            value = ReplaceMacros(option_block.values[0], project.macros)
            AddConfigOption(config.general, option_block.key, os.path.normpath(value))

        elif option_block.key in ("include_directories", "library_directories"):
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    value = ReplaceMacros(item.key, project.macros)
                    AddConfigOption(config.general, option_block.key, os.path.normpath(value))

        elif option_block.key == "configuration_type":
            if option_block.values[0] in ("static_library", "dynamic_library", "application"):
                AddConfigOption(config.general, option_block.key, option_block.values[0])
            else:
                print( "Invalid Value for configuration_type: " + option_block.values[0] )

        elif option_block.key == "commands":
            AddConfigOption(config.general, option_block.key, option_block.values[0])

        elif option_block.key == "language":
            pass

    elif group_name == "compiler":
        if option_block.key == "include_directories":
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    value = ReplaceMacros(item.key, project.macros)
                    AddConfigOption(config.compiler, option_block.key, os.path.normpath(value))

        elif option_block.key in ("preprocessor_definitions", "options"):
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    AddConfigOption(config.compiler, option_block.key, item.key)
                    if item.values:
                        for value in item.values:
                            AddConfigOption(config.compiler, option_block.key, value)

        elif option_block.key == "treat_warning_as_error":
            AddConfigOption(config.compiler, option_block.key, option_block.values[0])

    elif group_name == "linker":

        if option_block.key == "library_directories":
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    value = ReplaceMacros(item.key, project.macros)
                    AddConfigOption(config.linker, option_block.key, os.path.normpath(value))

        elif option_block.key == "options":
            for item in option_block.items:
                if SolveCondition(item.condition, project.macros):
                    AddConfigOption(config.linker, option_block.key, item.key)
                    if item.values:
                        for value in item.values:
                            AddConfigOption(config.linker, option_block.key, value)

    elif group_name == "post_build":

        if group_name == "post_build":
            event = config.post_build

        # elif group_name == "pre_build":
        #     event = config.pre_build

        # elif group_name == "pre_link":
        #     event = config.pre_link

        if option_block.key == "command_line":
            value = ReplaceMacros(' '.join( option_block.values ), project.macros)
            value = value.replace( "\\n", "\n" )
            AddConfigOption(event, option_block.key, value)

        elif option_block.key == "use_in_build":
            AddConfigOption(event, option_block.key, option_block.values[0])
        pass

    return


def ReplaceMacros( string, macros ):
    if "$" in string:
        # go through all the known macros and check if each one is in the value
        for macro, macro_value in macros.items():
            if macro in string:
                string_split = string.split( macro )
                string = str(macro_value).join( string_split )
    return string


# keeping this since i might need it still, i hope not
def WriteDependencies(hash_dep_file, dependencies, project_def_list):
    for item in dependencies:
        for project_def in project_def_list:
            if project_def.name.lower() in item.lower():
                # TODO: fix this for multiple scripts in a project def (im going to get rid of that probably)
                # this is also very bad because the output name might be different than the project name
                hash_dep_file.write(item + " " + project_def.script_list[0] + "\n")


def ParseProject( project_script_path, base_macros, configurations, platforms ):

    try:
        project_filename = project_script_path.rsplit(os.sep, 1)[1]
    except IndexError:
        project_filename = project_script_path

    project_name = project_filename.rsplit( ".", 1 )[0]

    if os.sep not in project_script_path:
        project_dir = base_macros[ "$ROOTDIR" ]
    else:
        project_dir = os.path.join( base_macros[ "$ROOTDIR" ], project_script_path.rsplit(os.sep, 1)[0] )

    project_path = os.path.join( project_dir, project_filename )

    project = Project( project_name, project_dir, base_macros )

    project.hash_list[ project_filename ] = MakeHash( project_path )

    if base.FindCommand( "/verbose" ):
        print( "Reading: " + project_filename)

    project_file = ReadFile( project_path )

    if base.FindCommand( "/verbose" ):
        print( "Parsing: " + project_filename)
    else:
        print( "Parsing: " + project.name )

    ParseProjectFile(project_file, project, 0)

    # now for "multi-pass"
    for config in configurations:
        project.macros["$_CONFIG"] = config
        for platform in platforms:
            project.macros["$_PLATFORM"] = platform
            # just add the configuration object here instead
            AddConfigPlatform( project, project.macros )
            ParseProjectFileMulti(project_file, project, 0)

    return project


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

            if hash_line[0] == '--------------------------------------------------':
                break
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
    hash = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(128 * hash.block_size), b""):
            hash.update(chunk)
    return hash.hexdigest()


def WriteHashList(tmp_file, hash_list):
    for project_script_path, hash_value in hash_list.items():
        tmp_file.write( hash_value + " " + project_script_path + "\n" )
    return
