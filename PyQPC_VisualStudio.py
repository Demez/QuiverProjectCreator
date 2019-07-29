
import uuid, os, sys
import PyQPC_Base as base

import xml.etree.ElementTree as et
from xml.dom import minidom


def GetAllFolders( files ):
    folder_dict = {}
    for folder in files:
        if type(folder) == str:
            folder_dict[ folder ] = GetAllFolders( files[ folder ] )

    return folder_dict


def TurnFolderDictToStrings( folder_dict ):

    folder_list = []
    for folder, contents in folder_dict.items():
        current_folder = folder
        folder_list.append( current_folder )

        if contents != {}:
            current_folder += os.sep + ''.join( TurnFolderDictToStrings( contents ) )
            folder_list.append( current_folder )

    return folder_list


def MakeUUID():
    return f"{{{uuid.uuid4()}}}".upper()


def GetConfigOptionValue( config, option_name, config_group=None ):
        
        if config != {}:
            if config_group and config_group in config:
                value = GetConfigGroupOption( option_name, config[ config_group ] )
            else:
                value = GetConfigOption( option_name, config )

            return value
        return None


def GetConfigOption( option, config ):

    for group in config:
        if option in config[ group ]:
            return ReturnConfigOption( config[ group ][ option ] )
    else:
        return None


def GetConfigGroupOption( option, config ):

    if option in config:
        return ReturnConfigOption( config[ option ] )
    else:
        return None


def ReturnConfigOption( value ):

    if type( value ) == bool:
        return str( value ).lower()
    else:
        return value


# sln keys:
# https://www.codeproject.com/Reference/720512/List-of-Visual-Studio-Project-Type-GUIDs
# C++ - {8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}


def CreateProject( project ):

    print( "Creating: " + project.file_name + ".vcxproj" )
    vcxproject = CreateVCXProj( project )
    WriteProject( project, vcxproject )

    # would this be too much printing for the normal output? idk
    print( "Creating: " + project.file_name + ".vcxproj.filters" )
    vcxproject_filters = CreateVCXProjFilters( project, vcxproject )
    WriteProject( project, vcxproject_filters, True )

    return


def CreateVCXProj( project ):

    vcxproj = et.Element( "Project" )
    vcxproj.set( "DefaultTargets", "Build" )
    vcxproj.set( "ToolsVersion", "4.0" )
    vcxproj.set( "xmlns", "http://schemas.microsoft.com/developer/msbuild/2003" )

    # Project Configurations
    SetupProjectConfigurations( vcxproj, project )
    SetupGlobals( vcxproj, project )

    elem_import = et.SubElement( vcxproj, "Import" )
    elem_import.set( "Project", "$(VCTargetsPath)\\Microsoft.Cpp.Default.props" )

    SetupPropertyGroupConfigurations( vcxproj, project )

    elem_import = et.SubElement( vcxproj, "Import" )
    elem_import.set( "Project", "$(VCTargetsPath)\\Microsoft.Cpp.props" )

    extension_settings = et.SubElement( vcxproj, "ImportGroup" )
    extension_settings.set( "Label", "ExtensionSettings" )

    SetupPropertySheets( vcxproj, project )

    user_macros = et.SubElement( vcxproj, "PropertyGroup" )
    user_macros.set( "Label", "UserMacros" )

    SetupGeneralProperties( vcxproj, project )
    SetupItemDefinitionGroups( vcxproj, project )

    # --------------------------------------------------------------------
    # Now, add the files
    libraries = et.SubElement( vcxproj, "ItemGroup" )
    CreateFileItemGroups( "Library", project.libraries, libraries )
    
    # [ "rc", "c", "cxx", "cpp", "h", "hxx", "hpp" ]
    cl_include = et.SubElement( vcxproj, "ItemGroup" )
    include_list = GetProjectFiles( project.files, [ "h", "hxx", "hpp" ] )
    CreateFileItemGroups( "ClInclude", include_list, cl_include, True )

    cl_compile = et.SubElement( vcxproj, "ItemGroup" )
    include_list = GetProjectFiles( project.files, [ "c", "cxx", "cpp" ] )
    CreateFileItemGroups( "ClCompile", include_list, cl_compile, True, project )
    
    resource_compile = et.SubElement( vcxproj, "ItemGroup" )
    res_list = GetProjectFiles( project.files, [ "rc" ] )
    CreateFileItemGroups( "ResourceCompile", res_list, resource_compile, True )

    # CustomBuild = et.SubElement( vcxProj, "ItemGroup" )
    # include_list = GetProjectFiles( project.files, [ "c", "cxx", "cpp" ] )
    # CreateFileItemGroups( "CustomBuild", include_list, CustomBuild, True )
    
    item_group_none = et.SubElement( vcxproj, "ItemGroup" )
    none_list = GetProjectFiles( project.files, invalid_exts=[ "rc", "c", "cxx", "cpp", "h", "hxx", "hpp" ] )
    CreateFileItemGroups( "None", none_list, item_group_none, True )

    # other vstudio stuff idk
    elem_import = et.SubElement( vcxproj, "Import" )
    elem_import.set( "Project", "$(VCTargetsPath)\\Microsoft.Cpp.targets" )
    import_group = et.SubElement( vcxproj, "ImportGroup" )
    import_group.set( "Label", "ExtensionTargets" )

    return vcxproj


def SetupProjectConfigurations( vcxproj, project ):

    item_group = et.SubElement( vcxproj, "ItemGroup" )
    item_group.set( "Label", "ProjectConfigurations" )

    if project.macros[ "$PLATFORM" ] == "win64":
        platform = "x64"
    else:
        platform = project.macros[ "$PLATFORM" ]

    for config_name in project.config:
        # for platform in project.config:
        project_configuration = et.SubElement( item_group, "ProjectConfiguration" )
        project_configuration.set( "Include", config_name + "|" + platform )

        configuration = et.SubElement( project_configuration, "Configuration" )
        configuration.text = config_name

        elem_platform = et.SubElement( project_configuration, "Platform" )
        elem_platform.text = platform

    return


def SetupGlobals( vcxproj, project ):

    property_group = et.SubElement( vcxproj, "PropertyGroup" )
    property_group.set( "Label", "Globals" )

    project_name = et.SubElement( property_group, "ProjectName" )
    project_name.text = project.name

    project_guid = et.SubElement( property_group, "ProjectGuid" )
    project_guid.text = MakeUUID()
    
    return


def SetupPropertyGroupConfigurations( vcxproj, project ):

    if project.macros[ "$PLATFORM" ] == "win64":
        platform = "x64"
    else:
        platform = project.macros[ "$PLATFORM" ]
    
    for config_name in project.config:

        config = project.config[ config_name ]

        property_group = et.SubElement( vcxproj, "PropertyGroup" )
        property_group.set( "Condition", "'$(Configuration)|$(Platform)'=='" + config_name + "|" + platform + "'" )
        property_group.set( "Label", "Configuration" )

        option_dict = {
            "$General": [
                "ConfigurationType",
                "CharacterSet",
                "TargetName",
                "PlatformToolset",
            ],
            
            "$Compiler": [
                "WholeProgramOptimization",
            ],
        }

        for option_group, option_list in option_dict.items():
            for option_name in option_list:
                value = GetConfigOptionValue( config, option_name, option_group )
                if value:
                    option = et.SubElement( property_group, option_name )
                    option.text = value

    return


def SetupPropertySheets( vcxProj, project ):
    if project.macros["$PLATFORM"] == "win64":
        platform = "x64"
    else:
        platform = project.macros["$PLATFORM"]
    
    for config_name in project.config:

        import_group = et.SubElement( vcxProj, "ImportGroup" )
        import_group.set( "Condition", "'$(Configuration)|$(Platform)'=='" + config_name + "|" + platform + "'" )
        import_group.set( "Label", "PropertySheets" )

        elem_import = et.SubElement( import_group, "Import" )
        elem_import.set( "Project", "$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props" )
        elem_import.set( "Condition", "exists('$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props')" )
        elem_import.set( "Label", "LocalAppDataPlatform" )

    return


def SetupGeneralProperties( vcxproj, project ):

    property_group = et.SubElement( vcxproj, "PropertyGroup" )

    version = et.SubElement( property_group, "_ProjectFileVersion" )
    version.text = "10.0.30319.1"

    if project.macros["$PLATFORM"] == "win64":
        platform = "x64"
    else:
        platform = project.macros["$PLATFORM"]
    
    for config_name in project.config:
        config = project.config[ config_name ]
        condition = "'$(Configuration)|$(Platform)'=='" + config_name + "|" + platform + "'"
        
        option_dict = {
            "$General": [
                "OutDir",
                "IntDir",
                "TargetExt",
                "ExecutablePath",
            ],

            "$Linker": [
                "IgnoreImportLibrary",
                "LinkIncremental",
                "GenerateManifest",
            ],

            # IgnoreImportLibrary

            "$PreBuildEvent": [ "PreBuildEventUseInBuild" ],
            "$PreLinkEvent": [ "PreLinkEventUseInBuild" ],
            "$PostBuildEvent": [ "PostBuildEventUseInBuild" ],
        }

        for option_group, option_list in option_dict.items():
            for option_name in option_list:
                value = GetConfigOptionValue( config, option_name, option_group )

                if value:
                    option = et.SubElement( property_group, option_name )
                    option.set( "Condition", condition )

                    # ugh
                    if option_name == "ExecutablePath":
                        if "$(ExecutablePath)" not in value or "$(Path)" not in value:
                            if not base.FindCommand( "/hidewarnings" ):
                                print( "VS WARNING: \"ExecutablePath\" does not contain \"$(ExecutablePath);$(Path)\"" )
                            value += "$(ExecutablePath);$(Path)"

                    option.text = value

    return


def SetupItemDefinitionGroups( vcxproj, project ):

    for config_name in project.config:
        config = project.config[ config_name ]
        if project.macros["$PLATFORM"] == "win64":
            platform = "x64"
        else:
            platform = project.macros["$PLATFORM"]
        condition = "'$(Configuration)|$(Platform)'=='" + config_name + "|" + platform + "'"

        item_def_group = et.SubElement( vcxproj, "ItemDefinitionGroup" )
        item_def_group.set( "Condition", condition )

        # ------------------------------------------------------------------
        # PreBuildEvent

        pre_build_event = et.SubElement( item_def_group, "PreBuildEvent" )

        pre_build_options = {
            "$PreBuildEvent": [
                "Command",
                "Message",
                "PreBuildEventUseInBuild",
            ],
        }

        AddOptionListToElement(pre_build_options, pre_build_event, config, True)
    
        # ------------------------------------------------------------------
        # Compiler - ClCompile

        compiler = et.SubElement( item_def_group, "ClCompile" )

        compiler_options = {
            "$Compiler": [
                "AdditionalOptions",
                "Optimization",
                "InlineFunctionExpansion",
                "IntrinsicFunctions",
                "FavorSizeOrSpeed",
                "AdditionalIncludeDirectories",
                "PreprocessorDefinitions",
                "StringPooling",
                "MinimalRebuild",
                "ExceptionHandling",
                "BasicRuntimeChecks",
                "RuntimeLibrary",
                "BufferSecurityCheck",
                "FunctionLevelLinking",
                "EnableEnhancedInstructionSet",
                "FloatingPointModel",
                "TreatWChar_tAsBuiltInType",
                "ForceConformanceInForLoopScope",
                "RuntimeTypeInfo",
                "OpenMPSupport",
                "PrecompiledHeader",
                "PrecompiledHeaderFile",
                "PrecompiledHeaderOutputFile",
                "ExpandAttributedSource",
                "AssemblerOutput",
                "AssemblerListingLocation",
                "ObjectFileName",
                "ProgramDataBaseFileName",
                "GenerateXMLDocumentationFiles",
                "BrowseInformation",
                "WarningLevel",
                "TreatWarningAsError",
                "DebugInformationFormat",
                "CompileAs",
                "UseFullPaths",
                "DisableSpecificWarnings",
                "MultiProcessorCompilation",
                "BrowseInformationFile",
                "ErrorReporting",
            ],
        }

        AddOptionListToElement( compiler_options, compiler, config )
    
        # ------------------------------------------------------------------
        # Resources - ResourceCompile

        resources = et.SubElement( item_def_group, "ResourceCompile" )

        resource_options = {
            "$Resources" : [
                "PreprocessorDefinitions",
                "Culture",
            ],
        }        

        AddOptionListToElement( resource_options, resources, config )
    
        # ------------------------------------------------------------------
        # PreLinkEvent

        pre_link_event = et.SubElement( item_def_group, "PreLinkEvent" )

        pre_link_options = {
            "$PreLinkEvent": [
            ],
        }        
        # AddOptionListToElement( pre_link_options, pre_link_event, config, True )
    
        # ------------------------------------------------------------------
        # Linker - Link

        if config["$General"]["ConfigurationType"] == "DynamicLibrary" or \
                config["$General"]["ConfigurationType"] == "Application":

            linker = et.SubElement( item_def_group, "Link" )

            link_options = {
                "$Linker" : [
                    "AdditionalOptions",
                    "AdditionalDependencies",
                    "ShowProgress",
                    "OutputFile",
                    "SuppressStartupBanner",
                    "AdditionalLibraryDirectories",
                    "IgnoreSpecificDefaultLibraries",
                    "GenerateDebugInformation",
                    "ProgramDatabaseFile",
                    "GenerateMapFile",
                    "MapFileName",
                    "SubSystem",
                    "OptimizeReferences",
                    "EnableCOMDATFolding",
                    "BaseAddress",
                    "ImportLibrary",
                    "TargetMachine",
                    "LinkErrorReporting",
                    "RandomizedBaseAddress",
                    "ImageHasSafeExceptionHandlers",
                ],
            }

            AddOptionListToElement( link_options, linker, config )

        elif config["$General"]["ConfigurationType"] == "StaticLibrary":

            # ------------------------------------------------------------------
            # $Librarian - Lib

            librarian = et.SubElement( item_def_group, "Lib" )

            lib_options = {
                "$Librarian": [
                    "UseUnicodeResponseFiles",
                    "AdditionalDependencies",
                    "OutputFile",
                    "SuppressStartupBanner",
                    "AdditionalOptions",
                    "IgnoreAllDefaultLibraries",
                ],
            }

            AddOptionListToElement( lib_options, librarian, config )

        # ------------------------------------------------------------------
        # ManifestTool - Manifest

        manifest = et.SubElement( item_def_group, "Manifest" )
        option = et.SubElement( manifest, "SuppressStartupBanner" )
        option.text = GetConfigOptionValue( config, "SuppressStartupBanner", "$ManifestTool" )

        # ------------------------------------------------------------------
        # XMLDocumentGenerator - Xdcmake

        xdcmake = et.SubElement( item_def_group, "Xdcmake" )
        option = et.SubElement( xdcmake, "SuppressStartupBanner" )
        option.text = GetConfigOptionValue( config, "SuppressStartupBanner", "$XMLDocumentGenerator" )

        # ------------------------------------------------------------------
        # BrowseInformation - Bscmake

        bscmake = et.SubElement( item_def_group, "Bscmake" )

        browse_info_options = {
            "$BrowseInformation" : [
                "SuppressStartupBanner",
                "OutputFile",
            ],
        }        

        AddOptionListToElement( browse_info_options, bscmake, config )

        # ------------------------------------------------------------------
        # PostBuildEvent

        post_build_event = et.SubElement( item_def_group, "PostBuildEvent" )

        post_build_options = {
            "$PostBuildEvent": [
                "Command",
                "Message",
                "PostBuildEventUseInBuild",
            ],
        }        

        AddOptionListToElement( post_build_options, post_build_event, config, True )
            
        # ------------------------------------------------------------------
        # CustomBuildStep
        # custom_build_step = et.SubElement( item_def_group, "CustomBuildStep" )

    return


def AddOptionListToElement( option_dict, element, config, replace_new_lines=False ):
    for option_group, option_list in option_dict.items():
        for option_name in option_list:
            option_value = GetConfigOptionValue( config, option_name, option_group )
            if option_value != None:
                option = et.SubElement( element, option_name )

                if option_value == "True" or option_value == "False":
                    option_value = str(option_value).lower()

                if replace_new_lines:
                    option_value = option_value.replace( "\\n", "\n" )

                option.text = option_value
    return


def CreateFileItemGroups( file_type, file_list, item_group, get_values=False, project=None ):

    for file in file_list:

        if get_values:
            elem_file = et.SubElement( item_group, file_type )
            elem_file.set( "Include", file.path )

            if project:
                # file specific settings, idk if we can have more here
                for config_name in file.config:
                    config = file.config[ config_name ]
                    if project.macros[ "$PLATFORM" ] == "win64":
                        platform = "x64"
                    else:
                        platform = project.macros[ "$PLATFORM" ]

                    condition = "'$(Configuration)|$(Platform)'=='" + config_name + "|" + platform + "'"

                    file_config = {
                        "$Compiler" : [
                            "AdditionalIncludeDirectories",
                            "PrecompiledHeader",
                            "PrecompiledHeaderFile",
                            "PrecompiledHeaderOutputFile",
                            "AdditionalOptions",
                            "ExceptionHandling",
                        ],
                    }
                
                    # AddOptionListToElement( file_config, File, config )

                    for option_group, option_list in file_config.items():
                        for option_name in option_list:
                            option_value = GetConfigOptionValue( config, option_name, option_group )
                            if option_value:
                                option = et.SubElement( elem_file, option_name )
                                option.set( "Condition", condition )
                                option.text = option_value
        else:
            elem_file = et.SubElement( item_group, file_type )
            elem_file.set( "Include", file )


# TODO: maybe move this to the project class?
def GetProjectFiles( project_files, valid_exts=[], invalid_exts=[] ):

    # now get only add any file that has any of the valid file extensions and none of the invalid ones

    wanted_files = []
    for file_obj in project_files:
        if file_obj not in wanted_files:
            # what if this file doesn't have a file extension?
            file_ext = file_obj.path.rsplit( ".", 1 )[1]
            if file_ext in valid_exts and file_ext not in invalid_exts:
                wanted_files.append( file_obj )

    return wanted_files


def CreateVCXProjFilters( project, vcxproj ):

    proj_filters = et.Element( "Project" ) 
    proj_filters.set( "ToolsVersion", "4.0" )
    proj_filters.set( "xmlns", "http://schemas.microsoft.com/developer/msbuild/2003" )

    Create_FolderFilters( proj_filters, project )

    Create_ItemGroupFiltersLibrary( proj_filters, vcxproj )
    
    # these functions here are slow, oof
    # all_files = GetProjectFiles( project.files, [ "h", "hpp", "hxx" ] )
    Create_ItemGroupFilters( proj_filters, vcxproj, project, "ClInclude" )

    # all_files = GetProjectFiles( project.files, [ "cpp", "c", "cxx" ] )
    Create_ItemGroupFilters( proj_filters, vcxproj, project, "ClCompile" )

    # all_files = GetProjectFiles( project.files, [ "rc" ] )
    Create_ItemGroupFilters( proj_filters, vcxproj, project, "ResourceCompile" )

    # all_files = GetProjectFiles( project.files, invalid_exts = [ "cpp", "c", "cxx", "h", "hpp", "hxx", "lib", "rc" ] )
    Create_ItemGroupFilters( proj_filters, vcxproj, project, "None" )

    return proj_filters


def Create_FolderFilters( proj_filters, project ):

    # project.GetFileObjectsInFolder( folder_list )
    # project.GetFileObject( file_path )

    folder_list = project.GetAllFileFolderPaths()

    # default folder for libraries
    if "Link Libraries" not in folder_list:
        folder_list.append( "Link Libraries" )

    item_group = et.SubElement( proj_filters, "ItemGroup" )

    for folder in folder_list:
        elem_folder = et.SubElement( item_group, "Filter" )
        elem_folder.set( "Include", folder )
        unique_identifier = et.SubElement( elem_folder, "UniqueIdentifier" )
        unique_identifier.text = MakeUUID()

    return


def Create_ItemGroupFiltersLibrary( proj_filters, vcxproj ):

    item_groups = vcxproj.findall( "ItemGroup" )

    all_items = []
    for item in item_groups:
        if not all_items:
            all_items = item.findall( "Library" )
        else:
            break
        
    item_group = et.SubElement( proj_filters, "ItemGroup" )

    for item in all_items:
        elem_file = et.SubElement( item_group, "Library" )
        elem_file.set( "Include", item.attrib[ "Include" ] )
        folder = et.SubElement( elem_file, "Filter" )
        folder.text = "Link Libraries"


def Create_ItemGroupFilters( proj_filters, vcxproj, project, filter_name ):

    item_groups = vcxproj.findall( "ItemGroup" )

    all_items = []
    for item in item_groups:
        if not all_items:
            all_items = item.findall( filter_name )
        else:
            break
        
    item_group = et.SubElement( proj_filters, "ItemGroup" )

    # this is a bit slow, not really sure if i can speed it up
    for item in all_items:
        elem_file = et.SubElement( item_group, filter_name )
        elem_file.set( "Include", item.attrib[ "Include" ] )
        folder = et.SubElement( elem_file, "Filter" )

        file_obj = project.GetFileObject( item.attrib[ "Include" ] )

        folder.text = file_obj.folder_path

    return


# --------------------------------------------------------------------------------------------------


def WriteProject( project, xml_file, filters = False ):

    file_path = project.macros[ "$PROJECTDIR" ] + os.sep + project.file_name.rsplit( ".", 1 )[0] + ".vcxproj"

    if filters:
        file_path += ".filters"

    with open( file_path, "w", encoding = "utf-8" ) as project_file:
        project_file.write( AddFormattingToXML( xml_file ) )


def AddFormattingToXML( elem ):
    raw_string = et.tostring(elem, 'utf-8')
    reparsed = minidom.parseString( raw_string )
    return reparsed.toprettyxml(indent="  ")


# --------------------------------------------------------------------------------------------------


# this will need a ton of uuid's,
# the Project Name, and the vcxproj path
def MakeSolutionFile( project_def_list, root_folder, solution_name ):

    cpp_uuid = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"
    filter_uuid = "{2150E333-8FDC-42A3-9474-1A3956D46DE8}"

    solution_name += ".sln"

    print( "Creating Solution File: " + solution_name + "\n" )

    solution_path = os.path.join( root_folder, solution_name )

    with open( solution_path, "w", encoding = "utf-8" ) as solution_file:

        WriteTopOfSolution( solution_file )

        project_uuid_dict = {}
        project_folder_uuid = {}

        configurations = []
        platforms = []

        for project_def in project_def_list:

            for folder in project_def.group_folder_list:
                if folder not in project_folder_uuid:
                    project_folder_uuid[folder] = MakeUUID()

            for script_path in project_def.script_list:

                vcxproj_path = script_path.rsplit(".", 1)[0] + ".vcxproj"
                abs_vcxproj_path = os.path.normpath( root_folder + "/" + vcxproj_path )

                tree = et.parse( abs_vcxproj_path )
                vcxproj = tree.getroot()

                project_name, project_uuid, project_configurations, project_platforms = GetNeededItemsFromProject(vcxproj)

                for project_configuration in project_configurations:
                    if project_configuration not in configurations:
                        configurations.append(project_configuration)

                for project_platform in project_platforms:
                    if project_platform not in platforms:
                        platforms.append(project_platform)

                # shut
                base.CreateNewDictValue(project_uuid_dict, project_def.name, "list" )
                project_uuid_dict[project_def.name].append( project_uuid )

                SLN_WriteProjectLine( solution_file, project_name, vcxproj_path, cpp_uuid, project_uuid )

                # write any project dependencies

                project_uuid_deps = GetProjectDependencies( root_folder, script_path )

                SLN_WriteSection(solution_file, "ProjectDependencies", project_uuid_deps, True, True)

                # Get all the libraries in the vcxproj file
                # open EVERY ITEM IN THE PATH LIST and check if there is the output path is the in the libs list?
                # then check for the same file (no ext) in the project_path_list?

                # or you could just have this output another file, like .pyqpc_deps (dependencies)
                # and then just read that and input it here
                # except, how are you going to know the project path of the files?

                # you might just have to check the projects you are currently using i guess

                # tree = et.parse( os.path.join( root_folder, vcxproj_path + ".vcxproj.filters" ) )
                # vcxproj_filters = tree.getroot()

                # vcxproj_uuid = GetDependencyUUID( vcxproj_filters )

                solution_file.write( "EndProject\n" )

        # Write the folders as projects because vstudio dumb
        # might have to make this a project def, idk
        for folder_name, folder_uuid in project_folder_uuid.items():
            SLN_WriteProjectLine(solution_file, folder_name, folder_name, filter_uuid, folder_uuid)
            solution_file.write("EndProject\n")

        # you do need to make some GlobalSection thing after all the projects, but meh

        # um
        # SLN_WriteGlobalSection(solution_file, section_name, key_value_dict, is_post_solution=False)

        # Write the global stuff
        solution_file.write("Global\n")

        config_plat_list = []
        for config in configurations:
            for plat in platforms:
                config_plat_list.append(config + "|" + plat)

        # SolutionConfigurationPlatforms
        sln_config_plat = {}
        for config_plat in config_plat_list:
            sln_config_plat[config_plat] = config_plat

        SLN_WriteSection(solution_file, "SolutionConfigurationPlatforms", sln_config_plat, False)

        # ProjectConfigurationPlatforms
        proj_config_plat = {}
        for project_uuid_list in project_uuid_dict.values():
            for project_uuid in project_uuid_list:
                for config_plat in config_plat_list:
                    proj_config_plat[project_uuid + "." + config_plat + ".ActiveCfg"] = config_plat
                    # TODO: maybe get some setting for a default project somehow, i think the default is set here
                    proj_config_plat[project_uuid + "." + config_plat + ".Build.0"] = config_plat

        SLN_WriteSection(solution_file, "ProjectConfigurationPlatforms", proj_config_plat, True)

        # write the project folders
        global_folder_uuid_dict = {}
        for project_def in project_def_list:
            if project_def.name not in project_uuid_dict:
                continue

            # projects
            for folder_index, project_folder in enumerate(project_def.group_folder_list):
                if project_def.group_folder_list[-(folder_index+1)] in project_folder_uuid:
                    folder_uuid = project_folder_uuid[project_folder]
                    for project_uuid in project_uuid_dict[project_def.name]:
                        global_folder_uuid_dict[project_uuid] = folder_uuid

            # sub folders
            if len(project_def.group_folder_list) > 1:
                folder_index = -1
                while folder_index < len(project_def.group_folder_list):
                    project_sub_folder = project_def.group_folder_list[folder_index]
                    try:
                        project_folder = project_def.group_folder_list[folder_index-1]
                    except IndexError:
                        break

                    if project_sub_folder in project_folder_uuid:
                        sub_folder_uuid = project_folder_uuid[project_sub_folder]
                        folder_uuid = project_folder_uuid[project_folder]
                        if sub_folder_uuid not in global_folder_uuid_dict:
                            global_folder_uuid_dict[sub_folder_uuid] = folder_uuid
                        folder_index -= 1

        SLN_WriteSection(solution_file, "NestedProjects", global_folder_uuid_dict, False)

        solution_file.write("EndGlobal\n")

    return


def WriteTopOfSolution( solution_file ):

    solution_file.write( "Microsoft Visual Studio Solution File, Format Version 12.00\n" )

    # solution_file.write( "# Visual Studio Version 16\n" )
    solution_file.write( "# Visual Studio Version 16\n#\n" )
    solution_file.write( "# Automatically generated solution:\n" )
    solution_file.write( "# " + ' '.join( sys.argv ) + "\n#\n" )

    solution_file.write( "VisualStudioVersion = 16.0.28917.181\n" )
    solution_file.write( "MinimumVisualStudioVersion = 10.0.40219.1\n" )

    return


# get stuff we need from the vcxproj file, might even need more later for dependencies, oof
def GetNeededItemsFromProject(vcxproj):

    xmlns = "{http://schemas.microsoft.com/developer/msbuild/2003}"

    configurations = []
    platforms_elems = []
    platforms = []
    item_groups = vcxproj.findall( xmlns + "ItemGroup" )

    for property_group in item_groups:
        project_configurations = property_group.findall( xmlns + "ProjectConfiguration" )
        if project_configurations:
            break

    for project_configuration_elem in project_configurations:
        configurations.extend(project_configuration_elem.findall( xmlns + "Configuration" ))
        platforms_elems.extend(project_configuration_elem.findall( xmlns + "Platform" ))

    for index, configuration_elem in enumerate(configurations):
        if configuration_elem.text not in configurations:
            configurations[index] = configuration_elem.text

    for index, platform_elem in enumerate(platforms_elems):
        if platform_elem.text not in platforms:
            platforms.append(platform_elem.text)

    property_groups = vcxproj.findall( xmlns + "PropertyGroup" )

    project_name = None
    project_guid = None
    for property_group in property_groups:

        # checking if it's None because even if this is set to the element return,
        # it would still pass "if not project_name:"
        if project_name == None:
            project_name = property_group.findall( xmlns + "ProjectName" )[0]

        if project_guid == None:
            project_guid = property_group.findall( xmlns + "ProjectGuid" )[0]

        if project_guid != None and project_name != None:
            # return project_name.text, project_guid.text
            project_name = project_name.text
            project_guid = project_guid.text
            break

    return project_name, project_guid, configurations, platforms


def SLN_WriteProjectLine( solution_file, project_name, vcxproj_path, cpp_uuid, vcxproj_uuid ):
    solution_file.write( "Project(\"" + cpp_uuid + "\") = \"" + project_name + \
                         "\", \"" + vcxproj_path + "\", \"" + vcxproj_uuid + "\"\n" )
    return


def SLN_WriteSection(solution_file, section_name, key_value_dict,
                       is_post=False, is_project_section=False):

    if key_value_dict:

        if is_project_section:
            section_type = "Project"
            section_type_prepost = "Project\n"
        else:
            section_type = "Global"
            section_type_prepost = "Solution\n"

        if is_post:
            solution_type = "post" + section_type_prepost
        else:
            solution_type = "pre" + section_type_prepost

        solution_file.write( "\t" + section_type + "Section(" + section_name + ") = " + solution_type )

        for key, value in key_value_dict.items():
            solution_file.write("\t\t" + key + " = " + value + "\n")

        solution_file.write( "\tEnd" + section_type + "Section\n" )


# should change this to look every vcxproj file and
# check if the output file in Lib fits what the project needs
# first check if the config type is a StaticLibrary, then check OutputFile in Lib
def GetProjectDependencies(root_dir, project_path):
    project_dep_file_path = os.path.normpath(root_dir + os.sep + project_path + "_hash_dep" )

    if os.sep in project_path:
        project_path = project_path.rsplit(os.sep, 1)[0]

    if os.path.isabs(project_path):
        project_dir = os.path.normpath(project_path + os.sep)
    else:
        project_dir = os.path.normpath(root_dir + os.sep + project_path + os.sep)

    project_dependencies = {}
    if os.path.isfile(project_dep_file_path):
        with open(project_dep_file_path, mode="r", encoding="utf-8") as dep_file:
            dep_file = dep_file.read().splitlines()

        check = False
        for line in dep_file:
            line = line.split("=")

            if line[0] == '--------------------------------------------------':
                check = True
                continue

            if check:
                vcxproj_path = line[1].rsplit( ".", 1 )[0] + ".vcxproj"
                if os.path.isabs(vcxproj_path):
                    vcxproj_abspath = os.path.normpath(vcxproj_path)
                else:
                    vcxproj_abspath = os.path.normpath(root_dir + os.sep + vcxproj_path)

                tree = et.parse(vcxproj_abspath)
                vcxproj = tree.getroot()

                project_name, project_uuid, project_configurations, project_platforms = GetNeededItemsFromProject(
                    vcxproj)

                # TODO: i should probably check if it's actually the correct project dependency,
                # match the output file with the one the project needs
                # if it doesn't match though, i have no clue what to do

                # very cool vstudio
                project_dependencies[project_uuid] = project_uuid

    return project_dependencies
