
import os, sys
import PyQPC_Base as base
import PyQPC_Reader as reader


# idfk what to call this function
def GetVPCFileDirName( project_script_path, base_macros, definitions ):
    project_filename = project_script_path.rsplit(os.sep, 1)[1]
    project_name = project_filename.rsplit( ".", 1 )[0]

    project_dir = os.path.join( base_macros[ "$ROOTDIR" ], project_script_path.rsplit(os.sep, 1)[0] )

    project_path = os.path.join( project_dir, project_filename )

    project_file = reader.ReadFile( project_path )

    return project_file, project_dir, project_name


def GetAllVPCScripts( root_dir ):
    vpc_paths = []
    vgc_paths = []
    for subdir, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith( ".vpc" ):
                vpc_paths.append( os.path.join(subdir, file) )
            elif file.endswith( ".vgc" ):
                vgc_paths.append( os.path.join(subdir, file) )

    return vgc_paths, vpc_paths



def ConvertVGC( project ):

    print( "uhhhh" )

    return


# TODO: need to fix this up for writing conditions, ugh
def ConvertVPC( vpc_dir, vpc_filename, vpc_project, base_macros ):

    qpc_project_path = vpc_dir + os.sep + vpc_filename + ".qpc"

    with open( qpc_project_path, mode="w", encoding="utf-8" ) as qpc_project:
        WriteTopComment( qpc_project )

        for project_block in vpc_project:

            key = project_block.key.casefold()  # compare with ignoring case

            if key == "$configuration":
                print( "config" )

            elif key == "$project":
                print( "project files" )

                if project_block.values:
                    qpc_project.write( "project_name " + project_block.values[0] + "\n\n" )

                qpc_project.write( "files" )
                WriteCondition( project_block, qpc_project )
                qpc_project.write( "{\n" )
                WriteFilesBlock( project_block, qpc_project, "\t" )
                qpc_project.write( "}\n" )

            elif key in ("$macro", "$macrorequired", "$macrorequiredallowempty", "$conditional"):
                WriteMacro( project_block, qpc_project )

            elif key == "$include":
                WriteInclude( project_block, qpc_project )

            elif key in ("$ignoreredundancywarning", "$linux", "$loadaddressmacro", "$loadaddressmacroauto"):
                pass

            else:
                print("ERROR: Unknown key found: " + key)

        # WriteConfiguration( project_block.config, qpc_project )

        print("uhhhh")


    return


def WriteTopComment( qpc_project ):
    qpc_project.write(
        "// ---------------------------------------------------------------\n" +
        "// Auto Generated QPC Script - Fix if needed before using\n" +
        "// ---------------------------------------------------------------\n\n" )


def WriteCondition( vpc_block, qpc_project ):
    if vpc_block.condition:
        qpc_project.write(" [" + vpc_block.condition + "]")
    qpc_project.write("\n")


def DeleteBaseMacros( vpc_macros, base_macros ):
    for base_macro in base_macros:
        if base_macro in vpc_macros:
            del vpc_macros[ base_macro ]
    del vpc_macros[ "$PROJECTDIR" ]
    del vpc_macros[ "$PROJECTNAME" ]


def WriteMacro( vpc_macro, qpc_project ):
    qpc_project.write(  "macro " + vpc_macro.values[0] + " \"" + vpc_macro.values[1] + "\"" )
    WriteCondition( vpc_macro, qpc_project )


def WriteInclude( vpc_include, qpc_project ):
    qpc_include_path = vpc_include.values[0].replace( ".vpc", ".qpc" )
    qpc_include_path = os.path.normpath( qpc_include_path )
    qpc_project.write(  "include \"" + qpc_include_path + "\"\n" )
    WriteCondition( vpc_include, qpc_project )


def WriteFilesBlock( vpc_files, qpc_project, indent ):
    libraries = []
    for file_block in vpc_files.items:

        if file_block.key.casefold() == "$folder" and not file_block.values[0] == "Link Libraries":
            qpc_project.write( indent + "folder " + file_block.values[0])
            WriteCondition( file_block, qpc_project )
            qpc_project.write( indent + "{\n" )
            WriteFilesBlock( file_block, qpc_project, indent+"\t" )
            qpc_project.write( indent + "}\n" )

        elif file_block.key.casefold() in ("$file", "$dynamicfile", "-$file"):
            WriteFile( file_block, qpc_project, indent )

        elif file_block.key.casefold() == "$folder" and file_block.values[0] == "Link Libraries":
            libraries = file_block.items

        # elif file_block.key.casefold() in ("$lib", "$implib", "-$lib", "-$implib"):
        #     libraries.append(file_block)
    qpc_project.write( "\n" )

    return libraries


# def ConvertFilesToLibraries()
def WriteFile( file_block, qpc_project, indent ):
    if file_block.key.casefold() in ("$file", "$dynamicfile", "-$file"):
        if len(file_block.values) > 1:
            for file_path in file_block.values:
                if not file_block.values( file_block.values.index(file_path) ) >= len( file_block.values ):
                    qpc_project.write( indent + '"' + file_path + "\"\t\\\n" )
                else:
                    qpc_project.write( indent + '"' + file_path + "\"\t\\" )
        else:
            qpc_project.write(indent + '"' + file_block.values[0] + '"')

        WriteCondition( file_block, qpc_project )

        if file_block.items:
            for file_path in file_block.values:
                WriteConfiguration( file_block.items[0], qpc_project )
    else:
        print( "unknown key: " + file_block.key )


def WriteConfiguration( vpc_config, qpc_project ):
    pass

    # for vpc_config_group in vpc_config:

        # qpc_include_path = vpc_include_path.replace( ".vpc", ".qpc" )
        # qpc_project.write(  "include \"" + qpc_include_path + "\"\n" )
    # qpc_project.write( "\n" )

