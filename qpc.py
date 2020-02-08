# ---------------------------------------------------------------------
# Quiver Project Creator
# Written by Demez
# ---------------------------------------------------------------------

import os
import sys

from qpc_base import args, PosixPath
import qpc_hash
import qpc_reader
import qpc_parser
import qpc_writer

if args.time:
    from time import perf_counter


def GetBaseMacros():
    # OS Specific Defines
    arg_macros = {}
    for macro in args.macros:
        arg_macros["$" + macro.upper()] = "1"
    
    if sys.platform == "win32":
        return {
            "$WINDOWS": "1",
            "$_BIN_EXT": ".dll",
            "$_STATICLIB_EXT": ".lib",
            "$_IMPLIB_EXT": ".lib",
            "$_APP_EXT": ".exe",
            # "$_DBG_EXT": ".pdb",
            **arg_macros,
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
            **arg_macros,
        }
    
    # TODO: finish setting up MacOS stuff here
    elif sys.platform == "darwin":
        return {
            "$POSIX": "1",
            "$MACOS": "1",
            "$_BIN_EXT": ".dylib",
            "$_STATICLIB_EXT": ".a",
            "$_IMPLIB_EXT": ".so",
            "$_APP_EXT": "",
            # "$_DBG_EXT": ".dbg",
        }


def VPCConvert():
    import qpc_vpc_converter as vpc_converter
    print("\nConverting VPC Scripts to QPC Scripts")
    
    print("Finding All VPC and VGC Scripts")
    vgc_path_list, vpc_path_list = vpc_converter.GetAllVPCScripts(args.root_dir)
    
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


def GetAllProjects(all_groups, all_projects):
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
        return ["win32", "win64"]
    
    elif sys.platform.startswith("linux"):
        return ["linux32", "linux64"]
    
    elif sys.platform == "darwin":
        return ["macos"]


def SetProjectTypeMacros(base_macros, project_types_list):
    for name in project_types_list:
        base_macros["$" + name.upper()] = "1"
        if args.verbose:
            print('Set Macro: ${0} = "1"'.format(name.upper()))


def Main():
    base_macros = GetBaseMacros()
    
    if args.verbose:
        print()
        for macro_name, macro_value in base_macros.items():
            print('Set Macro: {0} = "{1}"'.format(macro_name, macro_value))
    
    SetProjectTypeMacros(base_macros, args.types)
    
    os.chdir(args.root_dir)
    
    if "vpc_convert" in args.types:
        VPCConvert()
        return
    
    if args.verbose:
        print("\nReading: " + args.base_file)
    
    base_file = qpc_reader.ReadFile(args.base_file)
    
    all_groups = {}
    all_projects = []
    configurations = qpc_parser.ParseBaseFile(base_file, base_macros, all_projects, all_groups)
    
    # --------------------------------------------------------------------------------------
    
    # get all the projects the user wants (this is probably the worst part in this whole project)
    project_def_list = GetAllProjects(all_groups, all_projects)
    print()
    platforms = GetPlatforms()
    project_pass = 0
    
    if args.time:
        start_time = perf_counter()

    project_hash_list = {}
    project_out_dirs = {}
    project_dependencies = {}

    for project_def in project_def_list:
        for project_path in project_def.script_list:
            
            # only run if the hash check fails or if the user force creates the projects
            if args.force or not qpc_writer.FindProject(project_path) or not qpc_hash.CheckHash(project_path):
                
                project_dir, project_name = os.path.split(project_path)
                
                # change to the project directory if needed
                if project_dir:
                    os.chdir(project_dir)
                
                # TODO: maybe make this multi-threaded?
                #  would speed it up a bit now that you're reading it multiple times
                project_list, project_pass = qpc_parser.ParseProject(project_dir, project_name, base_macros,
                                                                     configurations, platforms, project_pass)
                
                if args.verbose:
                    print("Parsed: " + project_list.macros["$PROJECT_NAME"])
                
                out_dir = qpc_writer.CreateProject(project_list)

                # TODO: move dependencies out of the loop
                #  qpc's project looping just seems really awful to me
                #  though i don't know how i would do it better,
                #  besides having a small part that is parsed once before looping
                project_dependency_list = set()
                for project in project_list.projects:
                    project_dependency_list.update(project.dependencies)
                    
                # can't have it depend on itself
                posix_proj_path = PosixPath(project_path)
                if posix_proj_path in project_dependency_list:
                    project_dependency_list.remove(posix_proj_path)

                # i know this is bad but i want the types to be consistent
                project_dependency_list = tuple(project_dependency_list)
                    
                qpc_hash.WriteHashFile(project_path, out_dir, project_list.hash_dict,
                                       dependencies=project_dependency_list)
                project_dependencies[project_path] = project_dependency_list
                
                del project_list
                print("")
                
                # change back to the root_dir if needed:
                if project_dir:
                    os.chdir(args.root_dir)
            
            # TODO: make a function called "GetProjectDependencies", and use that here
            else:
                project_dependencies[project_path] = tuple(qpc_hash.GetProjectDependencies(project_path))

            project_hash_list[qpc_hash.GetHashFilePath(project_path)] = project_path
    
    if args.time:
        print("Finished Parsing Projects"
              "\n\tTime: " + str(perf_counter() - start_time) +
              "\n\tPasses: " + str(project_pass))
    
    if args.master_file:
        # TODO: this won't rebuild the master file if the project groups "includes" are changed
        qpc_writer.MakeMasterFile(project_def_list, project_hash_list, args.master_file,
                                  configurations, platforms, project_dependencies)
    
    # would be cool to add a timer here that would be running on another thread
    # if the cmd option "/benchmark" was specified, though that might be used as a conditional


if __name__ == "__main__":
    # TODO: maybe print more info here if verbose?
    print("----------------------------------------------------------------------------------\n"
          " Quiver Project Creator\n " + ' '.join(sys.argv[1:]) +
          "\n----------------------------------------------------------------------------------")
    
    Main()
    
    print("----------------------------------\n"
          " Finished\n"
          "----------------------------------\n")
