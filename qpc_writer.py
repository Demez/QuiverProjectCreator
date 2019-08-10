
import qpc_visual_studio as vstudio
# import qpc_makefile as makefile


def CreateProject(project_list, project_types):
    if project_types.vstudio:
        vstudio.CreateProject(project_list)

    if project_types.makefile:
        pass
    #     makefile.CreateProject(project_list)


def MakeMasterFile(project_types, project_def_list, root_folder, solution_name, configurations, platforms):
    if project_types.vstudio:
        vstudio.MakeSolutionFile( project_def_list, root_folder, solution_name, configurations, platforms )

    if project_types.makefile:
        pass
    #     makefile.MakeMasterMakefile()
