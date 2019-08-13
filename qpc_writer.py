
import os

from qpc_base import args

import qpc_visual_studio as vstudio
# import qpc_vscode as vscode
# import qpc_makefile as makefile


def CreateProject(project_list):
    if "vstudio" in args.types:
        vstudio.CreateProject(project_list)

    # if "vscode" in args.types:
    #     vscode.CreateProject(project_list)

    if "makefile" in args.types:
        pass
    #     makefile.CreateProject(project_list)


def MakeMasterFile(project_def_list, solution_name, configurations, platforms):
    if "vstudio" in args.types:
        vstudio.MakeSolutionFile( project_def_list, solution_name, configurations, platforms )

    if "makefile" in args.types:
        pass
    #     makefile.MakeMasterMakefile()


def FindProject(project_path):
    split_ext_path = os.path.splitext(project_path)[0]
    if "vstudio" in args.types:
        if os.path.isfile(split_ext_path + ".vcxproj") and os.path.isfile(split_ext_path + ".vcxproj.filters"):
            return True
        else:
            return False
