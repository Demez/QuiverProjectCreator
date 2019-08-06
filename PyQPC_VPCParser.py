# Parses Project Scripts, Base Scripts, Definition Files, and Hash Files

# will remove this and merge into qpc_writer soon

# TODO: figure out what is $CRCCHECK is
# may need to add a /checkfiles launch option to have this check if a file exists or not
# it would probably slow it down as well

import os
import hashlib
import PyQPC_Base as base
import PyQPC_Parser as qpc_parser
import PyQPC_Reader as reader


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


class VPCProject:
    def __init__( self, name, path, macros ):
        self.file_name = name  # the actual file name
        self.name = name  # the project name
        # self.path = path # folder the project script is in (using $PROJECTDIR instead, maybe use this instead?)
        
        self.includes = {}

        self.files = []
        self.libraries = []
        self.dependencies = []  # maybe store project script paths here?

        # maybe add an "self.other_files" dictionary where the files aren't objects and just the paths?
        # and only use self.files for h and cpp files?

        self.config = {}

        self.hash_list = {}

        self.base_macros = { "$PROJECTDIR" : path, "$PROJECTNAME" : name }
        for key, value in macros.items():
            self.base_macros[ key ] = value

        self.macros = []
        
    def AddFile( self, folder_list, file_object ):

        for file_path in file_object.values:
            if self.GetFileObject( file_path ):
                if not base.FindCommand( "/hidewarnings" ):
                    print( "WARNING: File already added: \"" + file_path + "\"" )
                return
            self.files.append( ProjectFile( file_path, folder_list, self.config, file_object.condition ) )

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

    # TODO: i probably need to add more stuff here for the prefix and ext macros
    # also add a check file option, since sometimes i may use "$DynamicFile" for a lib
    # maybe make a DynamicLib option? idk
    def AddLib(self, lib_path, implib = False):
        # TODO: fix this for if you have multiple libs in the value
        lib_path = self.GetLibPath(lib_path[0], implib)

        if lib_path not in self.libraries:
            self.libraries.append( lib_path )
        else:
            if not base.FindCommand("/hidewarnings"):
                print( "WARNING: Library already added: \"" + lib_path + "\"" )

        if lib_path not in self.dependencies:
            self.dependencies.append( lib_path )
        # else:
            # if not base.FindCommand("/hidewarnings"):
                # print( "WARNING: Dependency already added: \"" + lib_path + "\"" )

    def RemoveLib( self, lib_path, implib = False ):
        # TODO: fix this for if you have multiple libs in the value
        lib_path = self.GetLibPath(lib_path[0], implib)
        self.libraries.remove(lib_path)
        self.dependencies.remove(lib_path)

    def GetLibPath(self, lib_path, implib = False ):
        lib_path = os.path.normpath(lib_path)

        if implib:
            lib_ext = self.macros["$_IMPLIB_EXT"]
        else:
            lib_ext = self.macros["$_STATICLIB_EXT"]

        # remove this ugly ass hack valve did later
        # may have to check if the file exists in this folder before adding it (vmpi)
        if os.sep not in lib_path and lib_ext not in lib_path:
            lib_path = self.macros["$LIBPUBLIC"] + os.sep + lib_path

        # might break if for whatever reason we have a different extension
        if not lib_path.endswith( lib_ext ):
            lib_path += lib_ext

        return lib_path

    def RemoveFile( self, file_list ):

        for file_obj in self.files:
            if file_obj.path in file_list:
                del self.files[ self.files.index(file_obj) ]
                break


class ProjectFile:
    def __init__( self, file_path, folder_list, project_config, condition ):
        self.path = file_path
        self.config = {}

        self.condition = condition

        # maybe add a file extension value?

        # folder layout in any editor you want to use
        self.folder_depth_list = []
        self.folder_depth_list.extend( folder_list )  # make sure it's a list even if it's a string
        self.folder_path = os.sep.join( folder_list )

        for config_name in project_config:
            base.CreateNewDictValue( self.config, config_name, "dict" )


def AddConfig( project, config ):
    if config != '':
        base.CreateNewDictValue( project.config, config, "dict" )


def AddConfigGroup( project, config, group_name ):
    if config == '':
        for config_name in project.config:
            base.CreateNewDictValue( project.config[ config_name ], group_name, "dict" )
    else:
        base.CreateNewDictValue( project.config[ config ], group_name, "dict" )


def _AddConfigOption( project, config, group_name, option_name, option_value, option_definition ):

    if type(option_value) == str:  # and self.config[ config ][ group_name ][ option_name ] != '':
        base.CreateNewDictValue( project.config[ config ][ group_name ], option_name, "str" )

        if "$BASE" in option_value:
            # add onto what we already have

            base_value = project.config[ config ][ group_name ][ option_name ]

            '''
            option_value_split = option_value.split("$BASE")

            if option_definition.prefer_semicolon_no_comma or option_definition.prefer_semicolon_no_space:
                if not base_value.endswith( ";" ):
                    if not option_value_split[0].endswith( ";" ):
                        if not option_value_split[1].startswith( ";" ):
                            base_value += ";"
            '''

            option_value = option_value.replace( "$BASE", base_value )

        project.config[ config ][ group_name ][ option_name ] = option_value
    else:
        project.config[ config ][ group_name ].update( { option_name: option_value } )


def _AddFileConfigOption( project, file_obj, config, group_name, option_name, option_value, option_definition ):

    if type(option_value) == str:  # and self.config[ config ][ group_name ][ option_name ] != '':
        base.CreateNewDictValue( file_obj.config[ config ][ group_name ], option_name, "str" )

        if "$BASE" in option_value:
            # add everything from the project and what we may already have

            # try:
            #     base_value = project.config[config][group_name][option_name]
            # except KeyError:
            #     base_value = ''

            base_value = project.config[config][group_name][option_name]
            option_value = ''.join(option_value.split("$BASE"))

            if option_definition.prefer_semicolon_no_comma or option_definition.prefer_semicolon_no_space:
                if not base_value.endswith(";"):
                    if not option_value.startswith(";"):
                        base_value += ";"

            file_obj.config[config][group_name][option_name] = base_value + option_value

            # file_obj.config[config][group_name][option_name] += value + ''.join( option_value.split("$BASE") )
        else:
            file_obj.config[ config ][ group_name ][ option_name ] = option_value
    else:
        file_obj.config[ config ][ group_name ].update( { option_name: option_value } )


def AddConfigOption( project, config, group_name, option_name, option_value, option_definition, file_obj = None ):

    # check if the config name is '', if it is, add it to all configurations
    # this won't add onto an option, this will just replace it
    # so maybe check the type for if we should replace it or not
    if config == '':
        for config_name in project.config:
            if file_obj:
                _AddFileConfigOption( project, file_obj, config_name, group_name, option_name, option_value, option_definition )
            else:
                _AddConfigOption( project, config_name, group_name, option_name, option_value, option_definition )
    else:
        if file_obj:
            _AddFileConfigOption( project, file_obj, config, group_name, option_name, option_value, option_definition )
        else:
            _AddConfigOption( project, config, group_name, option_name, option_value, option_definition )
    return


def GetConfigOptionValue( project, config, group_name, option_name, option_value, file_obj = None ):

    if not option_value or config == '':
        return

    if file_obj:
        try:
            return file_obj.config[config][group_name][option_name]
        except KeyError:
            return None

    else:
        try:
            return project.config[config][group_name][option_name]
        except KeyError:
            return None


class DefinitionsFile:
    def __init__( self, file ):
        self.file = file
        self.version = 0
        self.groups = {}

    def SetVersion( self, version ):
        self.version = int(version)

    def AddGroup( self, group_name ):
        base.CreateNewDictValue( self.groups, group_name, "list" )

    def AddOption( self, group_name, option ):
        self.groups[ group_name ].append( option )


class ConfigOption:
    def __init__( self, key ):
        self.key = key
        self.type = "ignore"

        # this is a list because the order of these matter, as it uses the top one by default
        self.ordinals = []

        self.output = None  # what the key name will be instead

        # alternative key names
        self.alias = None
        self.legacy = None

        # booleans
        self.append_slash = False  # adds a slash to the end of it?
        self.fix_slashes = False
        self.prefer_semicolon_no_comma = False
        self.prefer_semicolon_no_space = False
        self.invert_output = False

        # idk yet
        self.global_property = False  # allows this key to be used anywhere

    def AddOrdinalOption( self, key, value ):
        self.ordinals.append( dict({key : value}) )
        # self.ordinals[ key ] = value

    def ConvertOrdinal( self, value ):
        if not value:
            return None

        # TODO: change self.ordinals to a dictionary, having it as a list is dumb
        for ordinal in self.ordinals:
            if value[0] in ordinal:
                return ordinal[ value[0] ]
        else:
            print( "ERROR: Unknown Ordinal option: " + value )
            quit()


def ParseBaseFile(base_file, macros, unknown_macros, project_list, group_dict):
    for project_block in base_file:
        key = project_block.key.casefold() # compare with ignoring case

        if key == "$games":

            for sub_project_block in project_block.items:
                if sub_project_block.key.upper() in unknown_macros:
                    if qpc_parser.SolveCondition( sub_project_block.condition, macros ):
                        macros[ "$" + sub_project_block.key.upper() ] = 1
                        del unknown_macros[ unknown_macros.index( sub_project_block.key.upper() ) ]

        elif key == "$project":
            project_def = ProjectDefinition(project_block.values[0])

            for item in project_block.items:
                if qpc_parser.SolveCondition( item.condition, macros ):
                    item.key = qpc_parser.ReplaceMacros( item.key, macros )
                    project_def.AddScript( item.key )
                    # project_dict[ project_block.values[0].casefold() ].append( item.key )
            project_list.append(project_def)

        elif key == "$group":
            # TODO: fix this for multiple groups
            for group in project_block.values:

                # do we have a group with this name already?
                if group in group_dict:
                    project_group = group_dict[ group ]
                else:
                    project_group = ProjectGroup( group )

                ParseProjectGroupItems(project_group, project_list, project_block, macros)
                group_dict[ project_group.name ] = project_group

        elif key in ("$conditional", "$macro", "$macrorequired"):
            macros["$" + project_block.values[0].upper()] = qpc_parser.ReplaceMacros(project_block.values[1], macros)

        elif key == "$include":
            # "Ah shit, here we go again."
            path = os.path.normpath(qpc_parser.ReplaceMacros( project_block.values[0], macros ))

            # maybe add a depth counter like in parsing projects?
            if base.FindCommand( "/verbose" ):
                print( "Reading: " + path )

            if not os.path.isabs(path):
                path = os.path.normpath(macros["$ROOTDIR"] + os.sep + path)

            include_file = reader.ReadFile( path )
            ParseBaseFile(include_file, macros, unknown_macros, project_list, group_dict)

        else:
            print( "Unknown VGC Key: " + project_block.key )

    return


def ParseProjectGroupItems(project_group, project_list, project_block, macros, folder_list = []):
    for item in project_block.items:
        if qpc_parser.SolveCondition(item.condition, macros):

            if item.key.casefold() == "$folder":
                folder_list.append( item.values[0] )
                ParseProjectGroupItems(project_group, project_list, item, macros, folder_list)
                folder_list.remove( item.values[0] )
            else:
                for project in project_list:
                    if project.name == item.key:
                        project_group.AddProject(project.name, project.script_list, folder_list)

    return


def SortProjectFile(project_file, project, definitions):

    for project_block in project_file:

        key = project_block.key.casefold()  # compare with ignoring case

        if key == "$configuration":
            ParseConfigBlock( project_block, project, definitions, project.macros )

        elif key == "$project":
            ParseProjectBlock( project_block, project, definitions )

        elif key in ("$macro", "$macrorequired", "$macrorequiredallowempty", "$conditional"):
            project.macros.append( project_block )

        elif key == "$include":
            # project.includes.append( project_block )
            project.includes[project_block.values[0]] = project_block.condition

        elif key in ("$ignoreredundancywarning", "$linux", "$loadaddressmacro", "$loadaddressmacroauto"):
            pass

        else:
            print( "ERROR: Unknown key found: " + key )

    return  # project


def ParseProjectBlock( project_block, project, definitions ):

    if project_block.values:
        project.name = project_block.values[0]

    # now go through each item
    for block in project_block.items:

        if block.key.casefold() == "$folder":
            ParseFolder( block, project, definitions, [] )

        elif "$file" in block.key.casefold() or "$dynamicfile" in block.key.casefold() \
        or "$lib" in block.key.casefold() or "$implib" in block.key.casefold():
            ParseFile( block, project, definitions )

        else:
            print( "Unknown Key: " + block.key )


def ParseFolder( folder_block, project, definitions, folder_list ):
    folder_list.append( folder_block.values[0] )

    for block in folder_block.items:
        if block.key.casefold() == "$folder":
            ParseFolder( block, project, definitions, folder_list )

        elif "$file" in block.key.casefold() or "$dynamicfile" in block.key.casefold() \
        or "$lib" in block.key.casefold() or "$implib" in block.key.casefold():
            ParseFile( block, project, definitions, folder_list )

        elif "$shaders" in block.key.casefold():
            pass

        else:
            print( "Unknown Key: " + block.key )

    # now "leave" the last folder
    del folder_list[-1]


# def ConvertFilesToLibraries()
def ParseFile( file_block, project, definitions, folder_list ):
    # ew
    if folder_list and folder_list[-1] == "Link Libraries":
        if not "lib" in file_block.key.casefold():
            file_block.key = "$Lib"

    if file_block.key.casefold() in ("$file", "$dynamicfile", "-$file"):
        project.AddFile( folder_list, file_block )

        if file_block.items:
            for file_path in file_block.values:
                file_object = project.GetFileObject( file_path )
                ParseConfigBlock( file_block.items[0], project, definitions, project.macros, file_object )

    elif file_block.key.casefold() in ("$lib", "$implib"):
        project.libraries.append( file_block )

    # ----------------------------------------------------------
    # Removing Files now
    elif file_block.key.casefold() == "-$file":
        project.RemoveFile( file_block.values )

    elif file_block.key.casefold() == "-$lib":
        project.RemoveLib( file_block.values )

    elif file_block.key.casefold() == "-$implib":
        project.RemoveLib( file_block.values, True )

    else:
        print( "unknown key: " + file_block.key )


# dammit, i accidentally made this so you can only have an option in a group
# and can't have a group in a group, not really sure if i should bother fixing it right now though
# TODO: split this up into ParseConfigGroup() and ParseConfigOption(), so you can parse it recursively
def ParseConfigBlock(project_block, project, definitions, macros, file_obj = None):

    # TODO: do something with the definitions here, maybe check what it is? idfk
    # or maybe add that definition option into the project config?

    if project_block.values == []:
        config_name = ""  # add it to all configs
    else:
        config_name = project_block.values[0]

    if file_obj:
        AddConfig( file_obj, config_name )
    else:
        AddConfig( project, config_name )

    for group_block in project_block.items:
        if group_block.key in definitions.groups:

            if file_obj:
                AddConfigGroup( file_obj, config_name, group_block.key )
            else:
                AddConfigGroup( project, config_name, group_block.key )

            for option_block in group_block.items:

                # maybe move this to ParseConfigOption()?
                # that way you don't have to use an option in a group? idk
                compare_name = option_block.key.casefold()
                for option_definition in definitions.groups[ group_block.key ]:
                    # PAIN
                    if compare_name == option_definition.key.casefold() or \
                        (option_definition.alias and compare_name == option_definition.alias.casefold()) or \
                            (option_definition.legacy and compare_name == option_definition.legacy.casefold()):

                        # floods the console with $PrecompiledHeaderFile
                        if base.FindCommand( "/showlegacyoptions" ):
                            if option_definition.legacy != None and compare_name == option_definition.legacy.casefold():
                                print( "Legacy option: " + option_block.key )

                        if option_definition.output:
                            name = option_definition.output
                        else:
                            name = option_definition.key
                        value = option_block.values

                        if value == []:
                            break

                        if "$" in name:
                            name = name.split( "$", 1 )[1]

                        if option_definition.type == "ignore":
                            break
                        elif option_definition.type == "string":
                            value = ''.join( option_block.values )

                        elif option_definition.type == "ordinals":
                            value = option_definition.ConvertOrdinal( value )

                        elif option_definition.type == "bool":
                            if value[0].lower().startswith("no") or value[0].lower().startswith("false"):
                                value = False
                            elif value[0].lower().startswith("yes") or value[0].lower().startswith("true"):
                                value = True
                            else:
                                print( "unknown bool option: " + value )

                            if option_definition.invert_output:
                                value = not value

                            value = str(value)

                        elif option_definition.type == "integer":
                            print( "integer is not setup yet as it is never used" )

                        else:
                            print( "unknown key type: " + option_definition.key )

                        # should i use the replace function instead?
                        if option_definition.prefer_semicolon_no_comma:
                            value = value.replace( ",", ";" )

                        if option_definition.prefer_semicolon_no_space:
                            value = value.replace( " ", ";" )

                        if option_definition.append_slash:
                            if not value.endswith( os.sep ):
                                value = value + os.sep

                        if option_definition.fix_slashes:
                            if value != '':
                                value = os.path.normpath( value )

                        if value:
                            AddConfigOption(project, config_name, group_block.key, name,
                                            value, option_definition, file_obj)
                        break

                else:
                    print( "Unknown option: " + option_block.key )
        else:
            print( "Unknown group: " + group_block.key )


# maybe make a configuration options class?
# and all the items be keys or groups
def ParseDefFile( def_file ):

    definitions = DefinitionsFile( def_file.key )

    for def_group in def_file.items:

        if def_group.key == "Version":
            definitions.SetVersion( def_group.values[0] )
            continue

        # maybe add an option in the def file for changing it?
        # like adding the output name next to the group name?
        # example: "$Compiler"  "ClCompile" {}
        definitions.AddGroup( def_group.key )

        for def_key in def_group.items:
            config_option = ConfigOption( def_key.key )

            for option in def_key.items:

                if option.key == "type":
                    config_option.type = option.values[0]
                
                elif option.key == "ordinals":
                    config_option.type = "ordinals"
                    for ordinal_option in option.items:
                        config_option.AddOrdinalOption( ordinal_option.key, ordinal_option.values[0] )

                elif option.key == "output":
                    config_option.output = option.values[0]

                # idfk
                elif option.key == "globalproperty":
                    config_option.global_property = option.values[0]

                # add a slash to the end of the value
                elif option.key == "AppendSlash":
                    config_option.append_slash = option.values[0]

                # fix the path seperators if needed
                elif option.key == "fixslashes":
                    config_option.fix_slashes = option.values[0]

                # change to "ReplaceCommaWithSemicolon"?
                elif option.key == "PreferSemicolonNoComma":
                    config_option.prefer_semicolon_no_comma = option.values[0]
                    
                # change to "ReplaceSpaceWithSemicolon"?
                elif option.key == "PreferSemicolonNoSpace":
                    config_option.prefer_semicolon_no_space = option.values[0]

                # changes bools to the opposite value
                elif option.key == "invertoutput":
                    config_option.invert_output = option.values[0]

                # in the def file, but the key is different so this is never used
                elif option.key == "alias":
                    config_option.alias = option.values[0]

                # option can also be called this
                elif option.key == "legacy":
                    config_option.legacy = option.values[0]

            # and now add that key to the Definitions Object
            definitions.AddOption( def_group.key, config_option )

    return definitions



