
import qpc_visual_studio as vstudio
# import qpc_makefile as makefile


def CreateProject(project_list, project_types):
    if not project_types:
        return

    if project_types["vstudio"] or project_types["vs2019"]:
        vstudio.CreateProject(project_list)

    # if project_types["makefile"]:
    #     makefile.CreateProject(project_list)

    else:
        print( "Unknown Project Type" )


def MakeMasterFile(project_types, project_def_list, root_folder, solution_name, configurations, platforms):
    if not project_types:
        return

    if project_types["vstudio"] or project_types["vs2019"]:
        vstudio.MakeSolutionFile( project_def_list, root_folder, solution_name, configurations, platforms )

    # if project_types["makefile"]:
    #     makefile.MakeMasterMakefile()

    else:
        print( "Unknown Project Type" )
