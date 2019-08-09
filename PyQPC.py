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
import PyQPC_Reader as reader
import PyQPC_Parser as parser
import PyQPC_Writer as writer


def SetupBaseDefines():
    macros = {
        "$ROOTDIR": os.path.dirname(os.path.realpath(__file__)),
        "$_CONFIG": "0",
        "$_PLATFORM": "0",
    }

    # OS Specific Defines
    if sys.platform == "win32":
        macros.update( {
            "$WINDOWS": "1",
            "$_BIN_EXT": ".dll",
            "$_STATICLIB_EXT": ".lib",
            "$_IMPLIB_EXT": ".lib",
            "$_APP_EXT": ".exe",
            # what does sym mean?
            # "$_SYM_EXT": ".pdb",
        } )

    # fix this, these are pretty much for linux only
    elif sys.platform.startswith('linux'):
        macros.update( {
            "$POSIX": "1",
            "$LINUX": "1",
            "$_BIN_EXT": ".so",
            "$_STATICLIB_EXT": ".a",
            "$_IMPLIB_EXT": ".so",
            "$_APP_EXT": "",
            # what does sym mean?
            # "$_SYM_EXT": ".dbg",
        } )

    return macros


if __name__ == "__main__":
    
    print( "----------------------------------------------------------------------------------" )
    print( " PyQPC " + ' '.join(sys.argv[1:]) )
    print( "----------------------------------------------------------------------------------" )

    # TODO: setup argparse and ditch base.FindCommand()
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

        "vpc_convert": False,

        # "vscode": False,
        # "make": False,
    }

    unknown_macros = []

    all_groups = {}
    all_projects = []

    base_macros = SetupBaseDefines()

    # maybe move handling command line parameters to different functions?

    # now start the recursion with default.vgc, which i just set to be in the same folder as this
    # does not set to the python script path though, idk if should change that or not

    # TODO: replace all this FindCommand() stuff with argparse, this here is really bad

    base_file_path = base.FindCommand("/basefile", True)
    root_dir = base.FindCommand("/rootdir", True)

    if root_dir:
        if os.path.isabs(root_dir):
            base_macros["$ROOTDIR"] = os.path.normpath( root_dir )
        else:
            base_macros["$ROOTDIR"] = os.path.normpath( base_macros["$ROOTDIR"] + os.sep + root_dir )

    if base_file_path:
        if os.path.isabs(base_file_path):
            abs_base_file_path = base_file_path
        else:
            abs_base_file_path = os.path.normpath(base_macros[ "$ROOTDIR" ] + os.sep + base_file_path)
    elif base.FindCommand( "/rootdir" ):
        print( "Setting Base File to default: /qpc_scripts/_default.qpc_base" )
        abs_base_file_path = os.path.normpath(base_macros[ "$ROOTDIR" ] + "/qpc_scripts/_default.qpc_base")
    else:
        raise Exception( "Base File path not defined.\n" +
                         "\tUse /basefile \"Path\" on the command line, relative to the script location." )

    cmdline_conditionals = base.FindCommandValues("/")

    if cmdline_conditionals:
        if "basefile" in cmdline_conditionals:
            cmdline_conditionals.remove( "basefile" )
        if "rootdir" in cmdline_conditionals:
            cmdline_conditionals.remove( "rootdir" )

        for conditional in cmdline_conditionals:

            if conditional in cmd_options:
                cmd_options[conditional] = True

            elif conditional in project_types:
                project_types[conditional] = True
                # should i even bother forcing it to be uppercase?
                base_macros["$" + conditional.upper()] = "1"

            else:
                unknown_macros.append(conditional.upper())

    if project_types[ "vpc_convert" ]:
        import PyQPC_qpc_writer as vpc_converter
        print("\nConverting VPC Scripts to QPC Scripts")

        print("Finding All VPC and VGC Scripts")
        vgc_path_list, vpc_path_list = vpc_converter.GetAllVPCScripts(base_macros["$ROOTDIR"])

        if vgc_path_list:
            print("\nConverting VGC Scripts")
            for vgc_path in vgc_path_list:
                print( "Converting: " + vgc_path )
                read_vgc, vgc_dir, vgc_name = vpc_converter.GetVPCFileDirName(vgc_path)
                vpc_converter.ConvertVGC(vgc_dir, vgc_name, read_vgc)

        if vpc_path_list:
            print("\nConverting VPC Scripts")

            for vpc_path in vpc_path_list:
                # TODO: maybe make a keep comments option in ReadFile()? otherwise, commented out files won't be kept
                print( "Converting: " + vpc_path )
                read_vpc, vpc_dir, vpc_name = vpc_converter.GetVPCFileDirName(vpc_path)
                vpc_converter.ConvertVPC(vpc_dir, vpc_name, read_vpc)

        print("----------------------------------")
        print(" Finished")
        print("----------------------------------\n")

        quit()

    else:
        if cmd_options[ "verbose" ]:
            print( "Reading: " + abs_base_file_path )

        base_file = reader.ReadFile( abs_base_file_path )

        configurations, platforms = parser.ParseBaseFile(
            base_file, base_macros, unknown_macros, all_projects, all_groups)

    base_macros[ "$ROOTDIR" ] = os.path.normpath( base_macros[ "$ROOTDIR" ] )
    
    # TODO: check the cmd options if help was set 

    # maybe report any unknown conditionals remaining?

    # setup any defines from the command line for what projects and/or groups we want
    
    # AddedProjectsOrGroups
    add_proj_and_grps = base.FindCommandValues("+")
    # RemovedProjectsOrGroups
    rm_proj_and_grps = base.FindCommandValues("-")

    if not rm_proj_and_grps:
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

    # TODO: move all this vpc convert stuff into it's own function
    # and have this run before everything above

    for project_def in project_def_list:
        for project_path in project_def.script_list:

            # only run if the hash check fails or if the user force creates the projects
            if base.FindCommand( "/f" ) or parser.HashCheck(base_macros["$ROOTDIR"], project_path):

                # OPTIMIZATION IDEA that i don't feel like setting up:
                # every time you call ReadFile(), add the return onto some dictionary,
                # keys are the absolute path, values are the returns
                # and then scan that dictionary whenever you reach an include,
                # and then just grab it from the last to parse again
                # so you don't slow it down with re-reading it for no damn reason

                project = parser.ParseProject(project_path, base_macros, configurations, platforms)

                hash_dep_file_path = os.path.join(base_macros["$ROOTDIR"], project_path) + "_hash"
                with open(hash_dep_file_path, mode="w", encoding="utf-8") as hash_dep_file:
                    parser.WriteHashList(hash_dep_file, project.hash_list)
                    # hash_dep_file.write("--------------------------------------------------\n")
                    # parser.WriteDependencies(hash_dep_file, project.dependencies, project_def_list)

                if base.FindCommand( "/verbose" ):
                    print( "Parsed: " + project.name )

                # i might need to get a project uuid from this, oof
                # except i can't actually do that, because of hash checks
                writer.CreateProject( project, project_types )

                del project
                print( "" )

            else:
                # TODO: fix this for if the project script is in the root dir
                if os.sep in project_path:
                    print( "Valid: " + project_path.rsplit(os.sep, 1)[1] + "_hash_dep\n" )
                else:
                    print( "Valid: " + project_path + "_hash_dep\n" )

    # maybe change to /masterfile or something?
    if base.FindCommand( "/mksln" ):
        # maybe use a hash check here?
        writer.MakeSolutionFile(project_types, project_def_list,
                                base_macros["$ROOTDIR"], base.FindCommand("/mksln", True), configurations, platforms)

    # would be cool to add a timer here that would be running on another thread
    # if the cmd option "/benchmark" was specified, though that might be used as a conditional
    print( "----------------------------------" )
    print( " Finished" )
    print( "----------------------------------\n" )

