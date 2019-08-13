# ---------------------------------------------------------------------
# Quiver Project Creator
# Written by Demez
# ---------------------------------------------------------------------

import os
import sys
from time import perf_counter

from qpc_base import args
import qpc_reader as reader
import qpc_parser as parser
import qpc_writer as writer


def GetBaseMacros():
    # OS Specific Defines
    if sys.platform == "win32":
        return {
            "$WINDOWS": "1",
            "$_BIN_EXT": ".dll",
            "$_STATICLIB_EXT": ".lib",
            "$_IMPLIB_EXT": ".lib",
            "$_APP_EXT": ".exe",
            # "$_DBG_EXT": ".pdb",
        }

    elif sys.platform.startswith("linux"):
        return {
            "$POSIX": "1",
            "$LINUX": "1",
            "$_BIN_EXT": ".so",
            "$_STATICLIB_EXT": ".a",
            "$_IMPLIB_EXT": ".so",
            "$_APP_EXT": "",
            # "$_DBG_EXT": ".dbg",
        }

    # TODO: finish setting up MacOS stuff here
    elif sys.platform == "darwin":
        return {
            "$POSIX": "1",
            "$MACOS": "1",
            "$_BIN_EXT": ".so",
            "$_STATICLIB_EXT": ".a",
            "$_IMPLIB_EXT": ".so",
            "$_APP_EXT": "",
            # "$_DBG_EXT": ".dbg",
        }


def VPCConvert():
    import qpc_vpc_converter as vpc_converter
    print("\nConverting VPC Scripts to QPC Scripts")

    print("Finding All VPC and VGC Scripts")
    vgc_path_list, vpc_path_list = vpc_converter.GetAllVPCScripts( args.root_dir )

    if vgc_path_list:
        print("\nConverting VGC Scripts")
        for vgc_path in vgc_path_list:
            print("Converting: " + vgc_path)
            read_vgc, vgc_dir, vgc_name = vpc_converter.GetVPCFileDirName(vgc_path)
            vpc_converter.ConvertVGC(vgc_dir, vgc_name, read_vgc)

    if vpc_path_list:
        print("\nConverting VPC Scripts")

        for vpc_path in vpc_path_list:
            # TODO: maybe make a keep comments option in ReadFile()? otherwise, commented out files won't be kept
            print("Converting: " + vpc_path)
            read_vpc, vpc_dir, vpc_name = vpc_converter.GetVPCFileDirName(vpc_path)
            vpc_converter.ConvertVPC(vpc_dir, vpc_name, read_vpc)

    print("----------------------------------")
    print(" Finished")
    print("----------------------------------\n")

    quit()


def GetAllProjects():
    project_def_list = []

    unwanted_projects = {}
    for removed_item in args.remove:
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
    if args.add:
        for added_item in args.add:
            if added_item in all_groups:
                if added_item not in args.remove:

                    # TODO: move to another function
                    for project in all_groups[added_item].projects:
                        if project.name not in unwanted_projects:
                            for added_project in project_def_list:
                                if added_project.name == project.name:
                                    break
                            else:
                                project_def_list.append(project)
                                continue

            else:
                if added_item not in args.remove:
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
        raise Exception("No projects were added to generate for")

    return project_def_list


def GetPlatforms():
    if sys.platform == "win32":
        return [ "win32", "win64" ]

    elif sys.platform.startswith("linux"):
        return [ "linux32", "linux64" ]

    elif sys.platform == "darwin":
        return [ "macos" ]


def SetProjectTypeMacros(project_types_list):
    for name in project_types_list:
        base_macros["$" + name.upper()] = "1"
        if args.verbose:
            print('Set Macro: ${0} = "1"'.format(name.upper()))


if __name__ == "__main__":

    # TODO: maybe print more info here if verbose?
    print( "----------------------------------------------------------------------------------\n" +
           " Quiver Project Creator\n " + ' '.join(sys.argv[1:]) + "\n" +
           "----------------------------------------------------------------------------------" )

    base_macros = GetBaseMacros()

    if args.verbose:
        print()
        for macro_name, macro_value in base_macros.items():
            print( 'Set Macro: {0} = "{1}"'.format(macro_name, macro_value) )

    SetProjectTypeMacros(args.types)

    os.chdir(args.root_dir)

    if "vpc_convert" in args.types:
        VPCConvert()

    if args.verbose:
        print( "\nReading: " + args.base_file)

    base_file = reader.ReadFile(args.base_file)

    all_groups = {}
    all_projects = []
    configurations = parser.ParseBaseFile(base_file, base_macros, all_projects, all_groups)

    if not args.remove:
        args.remove = []

    # --------------------------------------------------------------------------------------

    # get all the projects the user wants (this is probably the worst part in this whole project)
    project_def_list = GetAllProjects()
    print( "" )
    platforms = GetPlatforms()

    if args.verbose:
        start_time = perf_counter()

    for project_def in project_def_list:
        for project_path in project_def.script_list:

            # only run if the hash check fails or if the user force creates the projects
            if args.force or parser.HashCheck(project_path) or not writer.FindProject(project_path):

                # OPTIMIZATION IDEA that i don't feel like setting up:
                # every time you call ReadFile(), add the return onto some dictionary,
                # keys are the absolute path, values are the returns
                # and then scan that dictionary whenever you reach an include,
                # and then just grab it from the last to parse again
                # so you don't slow it down with re-reading it for no damn reason

                project_dir, project_name = os.path.split(project_path)

                # change to the project directory if needed
                if project_dir:
                    os.chdir( project_dir )

                # TODO: maybe make this multi-threaded?
                #  would speed it up a bit now that you're reading it multiple times
                project_list = parser.ParseProject(project_dir, project_name, base_macros, configurations, platforms)

                if args.verbose:
                    print( "Parsed: " + project_list.macros["$PROJECT_NAME"] )

                writer.CreateProject( project_list )

                with open(project_name + "_hash", mode="w", encoding="utf-8") as hash_file:
                    parser.WriteHashList(hash_file, project_list.hash_dict)

                del project_list
                print( "" )

                # change back to the root_dir if needed:
                if project_dir:
                    os.chdir( args.root_dir )

            else:
                # TODO: make a function called "GetProjectDependencies", and use that here

                print("Valid: " + project_path + "_hash\n")

    if args.verbose:
        end_time = perf_counter()
        print("Finished Parsing Projects - Time: " + str(end_time - start_time))

    if args.master_file:
        # maybe use a hash check here?
        writer.MakeMasterFile(project_def_list, args.master_file, configurations, platforms)

    # would be cool to add a timer here that would be running on another thread
    # if the cmd option "/benchmark" was specified, though that might be used as a conditional
    print( "----------------------------------" )
    print( " Finished" )
    print( "----------------------------------\n" )

