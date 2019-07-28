# ---------------------------------------------------------------------
# Purpose: Be a pretty much exact copy of Valve Project Creator
#   except i strongly doubt i will even come close to finishing lol
# 
# Written by Demez
# 
# Days worked on:
#   07/02/2019
#   07/03/2019
#   07/04/2019
#   07/05/2019
#   07/06/2019
#   07/07/2019
#   07/08/2019
#   07/09/2019 - finished parsing vgc files with ReadFile() (it can also read keyvalues)
#   07/10/2019
#   07/11/2019
#   07/12/2019
#   07/13/2019
#   07/14/2019
# ---------------------------------------------------------------------

import os
import sys

import PyQPC_Base as base
import PyQPC_Parser as parser
import PyQPC_Writer as writer


def SetupBaseDefines():
    base_macros[ "$ROOTDIR" ] = os.path.dirname(os.path.realpath(__file__))
    base_macros[ "$QUOTE" ] = '"'

    # idk what this does, though in vpc it apparently forces all projects to regenerate if you change it
    # i've never changed it before
    # base_macros[ "$InternalVersion" ] = "104"
    # base_conditionals[ "$InternalVersion" ] = 104

    # also apparently a macro doesn't need to be in caps? ffs
    base_macros[ "$INTERNALVERSION" ] = "104"
    base_conditionals[ "$INTERNALVERSION" ] = 104

    # OS Specific Defines
    if sys.platform == "win32":
        base_conditionals[ "$WINDOWS" ] = 1

        base_macros[ "$_DLL_EXT" ] = ".dll"
        base_macros[ "$_STATICLIB_EXT" ] = ".lib"
        base_macros[ "$_IMPLIB_EXT" ] = ".lib"
        base_macros[ "$_EXE_EXT" ] = ".exe"

        # for win64 just use /win64 from the commmand line for now
        # if you ever finish this pile of shit
        # change it so you can have x86 and x64 in the same project
        if base.FindCommand( "/win64" ):
            base_conditionals[ "$WIN64" ] = 1
            base_macros[ "$PLATFORM" ] = "win64"
        else:
            base_conditionals[ "$WIN32" ] = 1
            base_macros[ "$PLATFORM" ] = "win32"

    # fix this, these are pretty much for linux only
    elif sys.platform.startswith('linux'):
        base_conditionals[ "$POSIX" ] = 1
        base_conditionals[ "$LINUXALL" ] = 1

        base_conditionals[ "$GL" ] = 1

        base_macros[ "$POSIX" ] = "1"
        base_macros[ "$_POSIX" ] = "1"

        base_macros[ "$_DLL_EXT" ] = ".so"
        base_macros[ "$_EXTERNAL_DLL_EXT" ] = ".so"
        
        base_macros[ "$_STATICLIB_EXT" ] = ".a"
        base_macros[ "$_EXTERNAL_STATICLIB_EXT" ] = ".a"

        base_macros[ "$_IMPLIB_EXT" ] = ".so"
        base_macros[ "$_EXTERNAL_IMPLIB_EXT" ] = ".so"

        base_macros[ "$_IMPLIB_PREFIX" ] = "lib"
        base_macros[ "$_IMPLIB_DLL_PREFIX" ] = "lib"

        base_macros[ "$_EXE_EXT" ] = ""
        base_macros[ "$_SYM_EXT" ] = ".dbg"

        if base.FindCommand( "/linux64" ):
            base_conditionals[ "$POSIX64" ] = 1
            base_macros[ "$PLATFORM" ] = "linux64"
        else:
            base_conditionals[ "$POSIX32" ] = 1
            base_macros[ "$PLATFORM" ] = "linux32"


if __name__ == "__main__":
    
    print( "----------------------------------------------------------------------------------" )
    print( " PyQPC " + ' '.join(sys.argv[1:]) )
    print( "----------------------------------------------------------------------------------" )
    
    base_macros = {}
    base_macrosRequired = {}
    base_conditionals = {}

    # is this useless now that im just using base.FindCommand()?
    # it might lead to some obscure command buried somewhere
    # while this keeps it all here, but then you need to include it in a ton of functions
    cmd_options = {
        "verbose": False,
        "showlegacyoptions": False,
        "hidewarnings": False,
        "mksln": False,
        "checkfiles": False,
    }

    # this does nothing currently
    cmd_help = [
        "help",
        "h",
        "?",
    ]

    project_types = {
        "vstudio": False,
        "vs2019": False,
        # "vscode": False,
        # "make": False,
    }

    unknown_conditionals = []

    all_groups = {}
    all_projects = []

    SetupBaseDefines()

    # maybe move handling command line parameters to different functions?

    cmdline_conditionals = base.FindCommandValues( "/" )

    if cmdline_conditionals:
        for conditional in cmdline_conditionals:

            if conditional in cmd_options:
                cmd_options[conditional] = True
                        
            elif conditional in project_types:
                project_types[conditional] = True
                base_conditionals["$" + conditional.upper()] = 1

            else:
                unknown_conditionals.append( conditional.upper() )

    # now start the recursion with default.vgc, which i just set to be in the same folder as this
    # does not set to the python script path though, idk if should change that or not

    base_file_path = base.FindCommand("/basefile", True)

    if base_file_path:
        if os.path.isabs(base_file_path):
            abs_base_file_path = base_file_path
        else:
            abs_base_file_path = os.path.normpath(base_macros[ "$ROOTDIR" ] + os.sep + base_file_path)
    else:
        # abs_base_file_path = os.path.normpath(base_macros[ "$ROOTDIR" ] + "/../../vpc_scripts/default.vgc")
        raise Exception( "Base File path not defined.\n" +
                         "\tUse /basefile \"Path\" on the command line, relative to the script location." )

    if cmd_options[ "verbose" ]:
        print( "Reading: " + abs_base_file_path )

    base_file = parser.ReadFile( abs_base_file_path )
    definitions_file_path = parser.ParseBaseFile(base_file, base_macros, base_conditionals,
                                                 unknown_conditionals, all_projects, all_groups)

    base_macros[ "$ROOTDIR" ] = os.path.normpath( base_macros[ "$ROOTDIR" ] )

    if os.path.isabs(definitions_file_path):
        definitions_file_path = os.path.normpath( definitions_file_path )
    else:
        definitions_file_path = os.path.normpath( base_macros["$ROOTDIR"] + os.sep + definitions_file_path )
    
    # TODO: check the cmd options if help was set 

    # maybe report any unknown conditionals remaining? 

    if definitions_file_path:
        definitions_file = parser.ReadFile( definitions_file_path )
    else: 
        print( "---------------------------------------------------------------------------------" )
        print( "ERROR:  Definitions file needed for configuration options is undefined" )
        print( "        Set this with $Definitions \"Path\" in default.vgc" )
        print( "---------------------------------------------------------------------------------" )
        quit()

    definitions = parser.ParseDefFile( definitions_file[0] )

    # setup any defines from the command line for what projects and/or groups we want
    
    # AddedProjectsOrGroups
    add_proj_and_grps = base.FindCommandValues("+")
    # RemovedProjectsOrGroups
    rm_proj_and_grps = base.FindCommandValues("-")

    if rm_proj_and_grps == None:
        rm_proj_and_grps = []

    # TODO: figure out how vpc handles these and recreate it here
    # might come waaay later since it's very low priority
    # FindCommandValues( "*" ) # add a project and all projects that depend on it.
    # FindCommandValues( "@" ) # add a project and all projects that it depends on.
    # Use /h spew final target build set only (no .vcproj created). - what?

    # Now go through everything and add all the project scripts we want to this list
    # why did i make it so damn condensed
    # actually should i make this contain the project name and the project script as a dictionary? like in VPC?

    # --------------------------------------------------------------------------------------
    # get all the projects the user wants (this is probably the worst part in this whole project)

    project_def_list = []

    # this way i don't have to go through each group every single damn time
    unwanted_projects = {}
    for removed_item in rm_proj_and_grps:
        if removed_item in all_groups:
            for project in all_groups[removed_item].projects:
                if project.name not in unwanted_projects:
                    unwanted_projects[project.name] = project

        else:
            for project in all_projects:
                if project.name == removed_item:
                    unwanted_projects[project.name] = project
                    break

    # TODO: clean up this mess
    if add_proj_and_grps:
        for added_item in add_proj_and_grps:
            if added_item in all_groups:
                if added_item not in rm_proj_and_grps:

                    # TODO: move to a function
                    for project in all_groups[ added_item ].projects:
                        if project.name not in unwanted_projects:
                            for added_project in project_def_list:
                                if added_project.name == project.name:
                                    break
                            else:
                                project_def_list.append( project )
                                continue

            else:
                if added_item not in rm_proj_and_grps:
                    for project in all_projects:
                        if added_item == project.name:
                            for added_project in project_def_list:
                                if added_project.name == project.name:
                                    break
                            else:
                                project_def_list.append(project)
                                continue
                # else:
                    # print("hey this item doesn't exist: " + added_item)
    else:
        print( "add some projects or groups ffs" )

    # --------------------------------------------------------------------------------------

    print( "" )
    definitions_file_hash = parser.MakeHash( definitions_file_path )
    for project_def in project_def_list:
        for project_path in project_def.script_list:

            # only run if the hash check fails or if the user force creates the projects
            if base.FindCommand( "/f" ) or parser.HashCheck(base_macros["$ROOTDIR"], project_path):

                # OPTIMIZATION IDEA:
                # every time you call ReadFile(), add the return onto some dictionary, keys are the absolute path, values are the returns
                # and then scan that dictionary whenever you reach an include, and then just grab it from the last to parse again
                # so you don't slow it down with re-reading it for no damn reason

                # another idea:
                # make a ParseConfigGroup() function, so you can parse config groups recursively
                # would also nead to tweak ParseDefFile() to use ParseDefOption() and ParseDefGroup() as well

                project = parser.ParseProject(project_path, base_macros, base_conditionals, definitions)

                project.hash_list[ definitions_file_path ] = definitions_file_hash

                hash_dep_file_path = os.path.join(base_macros["$ROOTDIR"], project_path) + "_hash_dep"
                with open(hash_dep_file_path, mode="w", encoding="utf-8") as hash_dep_file:
                    parser.WriteHashList(hash_dep_file, project.hash_list)
                    hash_dep_file.write("--------------------------------------------------\n")
                    parser.WriteDependencies(hash_dep_file, project.dependencies, project_def_list)

                if base.FindCommand( "/verbose" ):
                    print( "Parsed: " + project.name )

                # i might need to get a project uuid from this, oof
                # except i can't actually do that, because of hash checks
                writer.CreateProject( project, project_types )

                del project
                print( "" )

            else:
                # TODO: fix this for if the project script is in the root dir
                project_filename = project_path.rsplit( os.sep, 1 )[1]
                print( "Valid: " + project_filename + "_hash_dep\n" )

    # maybe change to /masterfile or something?
    if base.FindCommand( "/mksln" ):
        # maybe use a hash check here?
        writer.MakeSolutionFile(project_types, project_def_list,
                                base_macros["$ROOTDIR"], base.FindCommand("/mksln", True))

    # would be cool to add a timer here that would be running on another thread
    # if the cmd option "/benchmark" was specified, though that might be used as a conditional
    print( "----------------------------------" )
    print( " Finished" )
    print( "----------------------------------\n" )

