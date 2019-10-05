import qpc_hash
import qpc_visual_studio
import qpc_makefile
# import qpc_vscode
# import qpc_ninja

from os import path, sep
from qpc_base import args


def CreateProject(project_list):
    if "vstudio" in args.types:
        return qpc_visual_studio.CreateProject(project_list)
    
    if "makefile" in args.types:
        return qpc_makefile.CreateMakefile(project_list)
    
    # if project_type == "vscode":
    #     qpc_vscode.CreateFiles(project_list)
    
    # if project_type == "ninja":
    #     qpc_ninja.CreateProject(project_list)


def MakeMasterFile(project_def_list, project_list, master_file_name, configurations, platforms):
    if "vstudio" in args.types:
        if not FindMasterFile(master_file_name) or not qpc_hash.CheckHash(master_file_name + ".sln", project_list):
            qpc_visual_studio.MakeSolutionFile(project_def_list, project_list, master_file_name, configurations, platforms)
            qpc_hash.WriteHashFile(master_file_name + ".sln", file_list=project_list, master_file=True)
    
    if "makefile" in args.types:
        pass
        # if not qpc_hash.CheckHash(master_file_name + ".makefile"):
        #     qpc_makefile.MakeMasterMakefile(project_def_list, master_file_name, configurations, platforms)
        #     qpc_hash.WriteHashFile(master_file_name + ".makefile", file_list=project_list, master_file=True)


def FindProject(project_path):
    # we can't check this if we are putting it somewhere else
    # we would have to parse first, then check
    if args.project_dir:
        return True
    
    base_path, project_name = path.split(project_path)
    split_ext_path = path.splitext(project_path)[0]
    base_path += sep
    
    if "vstudio" in args.types:
        if path.isfile(split_ext_path + ".vcxproj") and path.isfile(split_ext_path + ".vcxproj.filters"):
            return True
        else:
            return False
        
    if "makefile" in args.types:
        if path.isfile(base_path + "makefile"):
            return True
        else:
            return False


def FindMasterFile(file_path):
    base_path, project_name = path.split(file_path)
    split_ext_path = path.splitext(file_path)[0]
    base_path += sep
    if "vstudio" in args.types:
        if path.isfile(split_ext_path + ".sln"):
            return True
        else:
            return False
