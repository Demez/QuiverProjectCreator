
from qpc_base import args

import qpc_visual_studio as vstudio
# import qpc_makefile as makefile


def CreateProject(project_list):
    if "vstudio" in args.types:
        vstudio.CreateProject(project_list)

    if "makefile" in args.types:
        pass
    #     makefile.CreateProject(project_list)


def MakeMasterFile(project_def_list, solution_name, configurations, platforms):
    if "vstudio" in args.types:
        vstudio.MakeSolutionFile( project_def_list, solution_name, configurations, platforms )

    if "makefile" in args.types:
        pass
    #     makefile.MakeMasterMakefile()
