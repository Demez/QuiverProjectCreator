
import PyQPC_VisualStudio as vstudio


def CreateProject( project, project_type ):

    if project_type == "vstudio":
        vstudio.CreateProject( project )

    elif not project_type:
        pass

    else:
        print( "Unknown Project Type" )


def MakeSolutionFile( project_type, project_def_list, root_folder, solution_name ):

    if project_type == "vstudio":
        vstudio.MakeSolutionFile( project_def_list, root_folder, solution_name )

    elif not project_type:
        pass

    else:
        print( "Unknown Project Type" )
