
import uuid, os, sys
import qpc_base as base

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


def CreateProject(project_list):

    print( "Creating: " + project_list.file_name + ".vcxproj")
    # vcxproject = CreateVCXProj( project )
    vcxproject, include_list, res_list, none_list = CreateVCXProj(project_list)

    # this is a little slow, maybe due to disk write speed?
    WriteProject(project_list, vcxproject)

    # would this be too much printing for the normal output? idk
    print( "Creating: " + project_list.file_name + ".vcxproj.filters")
    vcxproject_filters = CreateVCXProjFilters(project_list, vcxproject, include_list, res_list, none_list)
    WriteProject(project_list, vcxproject_filters, True)

    return


def CreateVCXProj(project_list):

    vcxproj = et.Element("Project")
    vcxproj.set("DefaultTargets", "Build")
    vcxproj.set("ToolsVersion", "4.0")
    # is this even needed?
    vcxproj.set( "xmlns", "http://schemas.microsoft.com/developer/msbuild/2003" )

    # do this first so we don't do it EVERY TIME
    project_list = FixPlatformNames(project_list)

    # Project Configurations
    SetupProjectConfigurations(vcxproj, project_list)
    SetupGlobals(vcxproj, project_list)

    elem_import = et.SubElement( vcxproj, "Import" )
    elem_import.set( "Project", "$(VCTargetsPath)\\Microsoft.Cpp.Default.props" )

    SetupPropertyGroupConfigurations(vcxproj, project_list)

    elem_import = et.SubElement( vcxproj, "Import" )
    elem_import.set( "Project", "$(VCTargetsPath)\\Microsoft.Cpp.props" )

    extension_settings = et.SubElement( vcxproj, "ImportGroup" )
    extension_settings.set( "Label", "ExtensionSettings" )

    SetupPropertySheets(vcxproj, project_list)

    user_macros = et.SubElement( vcxproj, "PropertyGroup" )
    user_macros.set( "Label", "UserMacros" )

    SetupGeneralProperties(vcxproj, project_list)
    SetupItemDefinitionGroups(vcxproj, project_list)

    # --------------------------------------------------------------------
    # Now, add the files

    full_include_list = {}
    full_res_list = {}
    full_none_list = {}

    header_exts = (".h", ".hxx", ".hpp")

    res_exts = (".rc", ".ico", ".cur", ".bmp", ".dlg", ".rc2", ".rct", ".bin", ".rgs",
                ".gif", ".jpg", ".jpeg", ".jpe", ".resx", ".tiff", ".tif", ".png", ".wav")

    none_exts = (*res_exts, ".h", ".hxx", ".hpp")

    # TODO: merge everything together, for now, just add a condition on each one lmao
    for project in project_list.projects:
        condition = "'$(Configuration)|$(Platform)'=='" + project.config_name + "|" + project.platform + "'"

        # maybe do the same below for this?
        CreateSourceFileItemGroup( project.source_files, vcxproj, condition )

        include_list, remaining_files = GetProjectFiles(project.files, header_exts)
        full_include_list = { **full_include_list, **include_list }
        CreateFileItemGroups("ClInclude", include_list, vcxproj, condition)

        res_list, remaining_files = GetProjectFiles( remaining_files, res_exts )
        full_res_list = { **full_res_list, **res_list }
        CreateFileItemGroups("ResourceCompile", res_list, vcxproj, condition)

        none_list = GetProjectFiles( remaining_files, (), none_exts )[0]
        full_none_list = { **full_none_list, **none_list }
        CreateFileItemGroups( "None", none_list, vcxproj, condition )

    # other vstudio stuff idk
    elem_import = et.SubElement( vcxproj, "Import" )
    elem_import.set( "Project", "$(VCTargetsPath)\\Microsoft.Cpp.targets" )
    import_group = et.SubElement( vcxproj, "ImportGroup" )
    import_group.set( "Label", "ExtensionTargets" )

    return vcxproj, full_include_list, full_res_list, full_none_list


# this would change it in the platform itself, but maybe at the end we can change it back
def FixPlatformNames(project_list):
    for project in project_list.projects:
        if project.platform == "win64":
            project.platform = "x64"
    return project_list


# since we change it directly, we have to change it back for any other project we are generating for
def RevertPlatformNameChanges(project_list):
    for project in project_list.projects:
        if project.platform == "x64":
            project.platform = "win64"
    return project_list


def SetupProjectConfigurations(vcxproj, project_list):
    item_group = et.SubElement( vcxproj, "ItemGroup" )
    item_group.set( "Label", "ProjectConfigurations" )

    for project in project_list.projects:
        project_configuration = et.SubElement( item_group, "ProjectConfiguration" )
        project_configuration.set( "Include", project.config_name + "|" + project.platform )

        configuration = et.SubElement( project_configuration, "Configuration" )
        configuration.text = project.config_name

        elem_platform = et.SubElement( project_configuration, "Platform" )
        elem_platform.text = project.platform

    return


def SetupGlobals(vcxproj, project_list):

    property_group = et.SubElement( vcxproj, "PropertyGroup" )
    property_group.set( "Label", "Globals" )

    project_name = et.SubElement( property_group, "ProjectName" )
    project_name.text = project_list.macros["$PROJECT_NAME"]

    project_guid = et.SubElement( property_group, "ProjectGuid" )
    project_guid.text = MakeUUID()
    
    return


def SetupPropertyGroupConfigurations(vcxproj, project_list):
    for project in project_list.projects:
        property_group = et.SubElement(vcxproj, "PropertyGroup")
        property_group.set("Condition", "'$(Configuration)|$(Platform)'=='" +
                           project.config_name + "|" + project.platform + "'")
        property_group.set("Label", "Configuration")

        config = project.config

        configuration_type = et.SubElement(property_group, "ConfigurationType")

        if config.general.configuration_type == "application":
            configuration_type.text = "Application"
        elif config.general.configuration_type == "static_library":
            configuration_type.text = "StaticLibrary"
        elif config.general.configuration_type == "dynamic_library":
            configuration_type.text = "DynamicLibrary"

        toolset = et.SubElement(property_group, "PlatformToolset")

        if config.general.toolset_version == "msvc-v142":
            toolset.text = "v142"
        elif config.general.toolset_version == "msvc-v141":
            toolset.text = "v141"
        elif config.general.toolset_version == "msvc-v140":
            toolset.text = "v140"
        elif config.general.toolset_version == "msvc-v120":
            toolset.text = "v120"
        elif config.general.toolset_version == "msvc-v110":
            toolset.text = "v110"
        elif config.general.toolset_version == "msvc-v100":
            toolset.text = "v100"
        else:
            toolset.text = "v142"

        character_set_text = ''
        if "_MBCS" in config.compiler.preprocessor_definitions:
            character_set_text = "Unicode"
            config.compiler.preprocessor_definitions.remove("_MBCS")
        elif "MBCS" in config.compiler.preprocessor_definitions:
            character_set_text = "MultiByte"
            config.compiler.preprocessor_definitions.remove("MBCS")

        if character_set_text:
            character_set = et.SubElement(property_group, "CharacterSet")
            character_set.text = character_set_text

        # "TargetName",
        # "WholeProgramOptimization",

    return


def SetupPropertySheets(vcxproj, project_list):
    for project in project_list.projects:
        import_group = et.SubElement(vcxproj, "ImportGroup")
        import_group.set("Condition", "'$(Configuration)|$(Platform)'=='" +
                         project.config_name + "|" + project.platform + "'")
        import_group.set("Label", "PropertySheets" )

        elem_import = et.SubElement( import_group, "Import" )
        elem_import.set("Project", "$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props")
        elem_import.set("Condition", "exists('$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props')")
        elem_import.set("Label", "LocalAppDataPlatform")

    return


def SetupGeneralProperties(vcxproj, project_list):

    property_group = et.SubElement( vcxproj, "PropertyGroup" )

    version = et.SubElement( property_group, "_ProjectFileVersion" )
    version.text = "10.0.30319.1"
    
    for project in project_list.projects:
        condition = "'$(Configuration)|$(Platform)'=='" + project.config_name + "|" + project.platform + "'"
        config = project.config

        property_group = et.SubElement( vcxproj, "PropertyGroup" )
        property_group.set( "Condition", condition )

        out_dir = et.SubElement(property_group, "OutDir")
        out_dir.text = config.general.out_dir + os.sep

        int_dir = et.SubElement(property_group, "IntDir")
        int_dir.text = config.general.int_dir + os.sep

        target_ext = et.SubElement(property_group, "TargetExt")

        if config.general.configuration_type == "application":
            target_ext.text = project_list.macros["$_APP_EXT"]

        elif config.general.configuration_type == "static_library":
            target_ext.text = project_list.macros["$_STATICLIB_EXT"]

        elif config.general.configuration_type == "dynamic_library":
            target_ext.text = project_list.macros["$_BIN_EXT"]

        include_paths = et.SubElement(property_group, "IncludePath")
        include_paths.text = ';'.join(config.general.include_directories) + ";$(IncludePath)"

        library_paths = et.SubElement(property_group, "LibraryPath")
        library_paths.text = ';'.join(config.general.library_directories) + ";$(LibraryPath)"

        # "linker": [
        #   "IgnoreImportLibrary",
        #    "LinkIncremental",
        #    "GenerateManifest",

        # IgnoreImportLibrary

        # "pre_build_event": [ "PreBuildEventUseInBuild" ],
        # "pre_link_event": [ "PreLinkEventUseInBuild" ],
        # "post_build_event": [ "PostBuildEventUseInBuild" ],

    return


def SetupItemDefinitionGroups(vcxproj, project_list):
    for project in project_list.projects:
        condition = "'$(Configuration)|$(Platform)'=='" + project.config_name + "|" + project.platform + "'"
        cfg = project.config

        item_def_group = et.SubElement( vcxproj, "ItemDefinitionGroup" )
        item_def_group.set( "Condition", condition )

        # ------------------------------------------------------------------
        # pre_build - PreBuildEvent

        # pre_build_event = et.SubElement( item_def_group, "PreBuildEvent" )
    
        # ------------------------------------------------------------------
        # compiler - ClCompile
        AddCompilerOptions( item_def_group, cfg.compiler, cfg.general )
    
        # ------------------------------------------------------------------
        # resources? - ResourceCompile
        # resources = et.SubElement( item_def_group, "ResourceCompile" )

        # "PreprocessorDefinitions",
        # "Culture",
    
        # ------------------------------------------------------------------
        # pre_link - PreLinkEvent
        # pre_link_event = et.SubElement( item_def_group, "PreLinkEvent" )

        # ------------------------------------------------------------------
        # linker - Link or Lib
        if cfg.general.configuration_type in ("dynamic_library", "application"):
            link_lib = et.SubElement( item_def_group, "Link" )
        elif cfg.general.configuration_type == "static_library":
            link_lib = et.SubElement( item_def_group, "Lib" )
        else:
            raise Exception("how tf did you manage to get here with the wrong configuration type?")

        et.SubElement(link_lib, "AdditionalOptions").text = ' '.join(cfg.linker.options)
        et.SubElement(link_lib, "AdditionalDependencies").text = ';'.join(cfg.linker.libraries) + \
                                                                 ";%(AdditionalDependencies)"

        if cfg.linker.output_file:
            if cfg.general.configuration_type == "dynamic_library":
                et.SubElement(link_lib, "OutputFile").text = cfg.linker.output_file + project.macros["$_BIN_EXT"]
            elif cfg.general.configuration_type == "static_library":
                et.SubElement(link_lib, "OutputFile").text = cfg.linker.output_file + project.macros["$_STATICLIB_EXT"]
            elif cfg.general.configuration_type == "application":
                et.SubElement(link_lib, "OutputFile").text = cfg.linker.output_file + project.macros["$_APP_EXT"]

        if cfg.linker.debug_file:
            et.SubElement(link_lib, "ProgramDatabaseFile").text = cfg.linker.debug_file + ".pdb"

        if cfg.linker.import_library:
            et.SubElement(link_lib, "ImportLibrary").text = cfg.linker.import_library + project.macros["$_IMPLIB_EXT"]

        # what does "IgnoreAllDefaultLibraries" do differently than this? is it a boolean? idk
        et.SubElement(link_lib, "IgnoreSpecificDefaultLibraries").text = ';'.join(cfg.linker.ignore_libraries) + \
                                                                         ";%(IgnoreSpecificDefaultLibraries)"

        # TODO: convert options in the linker.options list to options here
        #  remove any option name from this list once you convert that option
        # "ShowProgress"
        # "SuppressStartupBanner"
        # "GenerateDebugInformation"
        # "GenerateMapFile"
        # "MapFileName"
        # "SubSystem"
        # "OptimizeReferences"
        # "EnableCOMDATFolding"
        # "BaseAddress"
        # "TargetMachine"
        # "LinkErrorReporting"
        # "RandomizedBaseAddress"
        # "ImageHasSafeExceptionHandlers"

        # ------------------------------------------------------------------
        # ManifestTool - Manifest
        # manifest = et.SubElement( item_def_group, "Manifest" )
        # option = et.SubElement( manifest, "SuppressStartupBanner" )
        # option.text = GetConfigOptionValue( config, "SuppressStartupBanner", "$ManifestTool" )

        # ------------------------------------------------------------------
        # XMLDocumentGenerator - Xdcmake
        # xdcmake = et.SubElement( item_def_group, "Xdcmake" )
        # option = et.SubElement( xdcmake, "SuppressStartupBanner" )
        # option.text = GetConfigOptionValue( config, "SuppressStartupBanner", "$XMLDocumentGenerator" )

        # ------------------------------------------------------------------
        # BrowseInformation - Bscmake
        # bscmake = et.SubElement( item_def_group, "Bscmake" )
        # browse_info_options = {
        #     "$BrowseInformation" : [
        #         "SuppressStartupBanner",
        #         "OutputFile",
        #     ],
        # }

        # AddOptionListToElement( browse_info_options, bscmake, config )

        # ------------------------------------------------------------------
        # PostBuildEvent

        post_build = et.SubElement( item_def_group, "PostBuildEvent" )

        et.SubElement(post_build, "Command").text = ' '.join(cfg.post_build.command_line)
        # et.SubElement(post_build, "Message").text = cfg.post_build.message
        et.SubElement(post_build, "PostBuildEventUseInBuild").text = cfg.post_build.use_in_build

        # ------------------------------------------------------------------
        # CustomBuildStep
        # custom_build_step = et.SubElement( item_def_group, "CustomBuildStep" )

    return


# TODO: this creates an empty element if we add a source file with no options in it
def AddCompilerOptions( element, compiler, general=None ):
    compiler_elem = et.SubElement(element, "ClCompile")
    added_option = False

    if compiler.preprocessor_definitions:
        added_option = True
        preprocessor_definitions = et.SubElement(compiler_elem, "PreprocessorDefinitions")
        preprocessor_definitions.text = ';'.join(compiler.preprocessor_definitions) + \
                                        ";%(PreprocessorDefinitions)"

    if general:
        if general.language:
            compile_as = et.SubElement(compiler_elem, "CompileAs")
            if general.language == "c":
                compile_as.text = "CompileAsC"
            elif general.language == "cpp":
                compile_as.text = "CompileAsCpp"

    if compiler.options:
        added_option = True
        warnings_list = []

        for index, option in enumerate(compiler.options):
            if option.startswith("/ignore:"):
                warnings_list.append(option[8:])
                compiler.options[index] = ''  # can't remove it in this for loop

        if warnings_list:
            disable_warnings = et.SubElement(compiler_elem, "DisableSpecificWarnings")
            disable_warnings.text = ';'.join(warnings_list)

        # now add any unchanged options
        et.SubElement(compiler_elem, "AdditionalOptions").text = ' '.join(compiler.options)

    # TODO: convert options in the compiler.options list to options here
    #  remove any option name from this list once you convert that option
    # "Optimization"
    # "InlineFunctionExpansion"
    # "IntrinsicFunctions"
    # "FavorSizeOrSpeed"
    # "PreprocessorDefinitions"
    # "StringPooling"
    # "MinimalRebuild"
    # "ExceptionHandling"
    # "BasicRuntimeChecks"
    # "RuntimeLibrary"
    # "BufferSecurityCheck"
    # "FunctionLevelLinking"
    # "EnableEnhancedInstructionSet"
    # "FloatingPointModel"
    # "TreatWChar_tAsBuiltInType"
    # "ForceConformanceInForLoopScope"
    # "RuntimeTypeInfo"
    # "OpenMPSupport"
    # "PrecompiledHeader"
    # "PrecompiledHeaderFile"
    # "PrecompiledHeaderOutputFile"
    # "ExpandAttributedSource"
    # "AssemblerOutput"
    # "AssemblerListingLocation"
    # "ObjectFileName"
    # "ProgramDataBaseFileName"
    # "GenerateXMLDocumentationFiles"
    # "BrowseInformation"
    # "WarningLevel"
    # "TreatWarningAsError"
    # "DebugInformationFormat"
    # "UseFullPaths"
    # "MultiProcessorCompilation"
    # "BrowseInformationFile"
    # "ErrorReporting"

    if not added_option:
        element.remove(compiler_elem)
    return


def CreateSourceFileItemGroup(file_list, parent_elem, condition):
    if file_list:
        item_group = et.SubElement(parent_elem, "ItemGroup")
        item_group.set( "Condition", condition )
        for file_path, values in file_list.items():
            elem_file = et.SubElement(item_group, "ClCompile")
            elem_file.set("Include", file_path)
            AddCompilerOptions(elem_file, values.compiler)


def CreateFileItemGroups(file_type, file_dict, parent_elem, condition):
    if file_dict:
        item_group = et.SubElement(parent_elem, "ItemGroup")
        item_group.set( "Condition", condition )
        for file_path in file_dict:
            elem_file = et.SubElement(item_group, file_type)
            elem_file.set("Include", file_path)


# TODO: maybe move this to the project class and rename to GetFilesByExt?
def GetProjectFiles( project_files, valid_exts=None, invalid_exts=None ):

    if not valid_exts:
        valid_exts = ()
    if not invalid_exts:
        invalid_exts = ()

    # now get only add any file that has any of the valid file extensions and none of the invalid ones
    wanted_files = {}
    unwanted_files = {}
    for file_path, folder_tuple in project_files.items():
        if file_path not in wanted_files:
            file_ext = os.path.splitext(file_path)[1]
            if file_ext not in invalid_exts:
                if file_ext not in valid_exts:
                    unwanted_files[file_path] = folder_tuple
                else:
                    wanted_files[file_path] = folder_tuple

    return wanted_files, unwanted_files


def CreateVCXProjFilters(project_list, vcxproj, include_list, res_list, none_list):

    proj_filters = et.Element( "Project" ) 
    proj_filters.set( "ToolsVersion", "4.0" )
    proj_filters.set( "xmlns", "http://schemas.microsoft.com/developer/msbuild/2003" )

    Create_FolderFilters(proj_filters, project_list)

    # Create_ItemGroupFiltersLibrary( proj_filters, vcxproj )

    for project in project_list.projects:
        # these functions here are slow, oof
        Create_SourceFileItemGroupFilters( proj_filters, project.source_files, "ClCompile")
    Create_ItemGroupFilters( proj_filters, include_list, "ClInclude" )
    Create_ItemGroupFilters( proj_filters, res_list, "ResourceCompile" )
    Create_ItemGroupFilters( proj_filters, none_list, "None" )

    return proj_filters


def Create_FolderFilters(proj_filters, project_list):
    folder_list = project_list.GetAllFileFolderPaths()
    if folder_list:
        item_group = et.SubElement( proj_filters, "ItemGroup" )
        for folder in folder_list:
            elem_folder = et.SubElement( item_group, "Filter" )
            elem_folder.set( "Include", folder )
            unique_identifier = et.SubElement( elem_folder, "UniqueIdentifier" )
            unique_identifier.text = MakeUUID()
    return


def Create_SourceFileItemGroupFilters(proj_filters, files_dict, filter_name):
    item_group = et.SubElement(proj_filters, "ItemGroup")
    for file_path, source_file in files_dict.items():
        elem_file = et.SubElement(item_group, filter_name)
        elem_file.set("Include", file_path)
        if source_file.folder:
            folder = et.SubElement(elem_file, "Filter")
            folder.text = source_file.folder

    return


def Create_ItemGroupFilters( proj_filters, files_dict, filter_name ):
    item_group = et.SubElement( proj_filters, "ItemGroup" )
    for file_path, folder_path in files_dict.items():
        elem_file = et.SubElement( item_group, filter_name )
        elem_file.set( "Include", file_path )
        if folder_path:
            folder = et.SubElement( elem_file, "Filter" )
            folder.text = folder_path

    return


# --------------------------------------------------------------------------------------------------


def WriteProject(project_list, xml_file, filters=False):

    file_path = project_list.macros["$PROJECT_DIR"] + os.sep + os.path.splitext(project_list.file_name)[0] + ".vcxproj"

    if filters:
        file_path += ".filters"

    with open( file_path, "w", encoding = "utf-8" ) as project_file:
        project_file.write( AddFormattingToXML( xml_file ) )


def AddFormattingToXML( elem ):
    return minidom.parseString( et.tostring(elem, 'utf-8') ).toprettyxml(indent="  ")


# --------------------------------------------------------------------------------------------------


# this will need a ton of uuid's,
# the Project Name, and the vcxproj path
def MakeSolutionFile( project_def_list, root_folder, solution_name, configurations, platforms ):

    cpp_uuid = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"
    filter_uuid = "{2150E333-8FDC-42A3-9474-1A3956D46DE8}"

    solution_name += ".sln"

    print( "Creating Solution File: " + solution_name + "\n" )

    solution_path = os.path.join( root_folder, solution_name )

    with open( solution_path, "w", encoding = "utf-8" ) as solution_file:

        WriteTopOfSolution( solution_file )

        project_uuid_dict = {}
        project_folder_uuid = {}

        for project_def in project_def_list:

            for folder in project_def.group_folder_list:
                if folder not in project_folder_uuid:
                    project_folder_uuid[folder] = MakeUUID()

            for script_path in project_def.script_list:

                vcxproj_path = script_path.rsplit(".", 1)[0] + ".vcxproj"
                abs_vcxproj_path = os.path.normpath( root_folder + "/" + vcxproj_path )

                tree = et.parse( abs_vcxproj_path )
                vcxproj = tree.getroot()

                project_name, project_uuid = GetNeededItemsFromProject(vcxproj)

                # shut
                base.CreateNewDictValue(project_uuid_dict, project_def.name, "list" )
                project_uuid_dict[project_def.name].append( project_uuid )

                SLN_WriteProjectLine( solution_file, project_name, vcxproj_path, cpp_uuid, project_uuid )

                # TODO: add dependencies to the project class and then use that here
                #  and have a GetDependencies() function for if the hash check passes
                # write any project dependencies
                # project_uuid_deps = GetProjectDependencies( root_folder, script_path )
                # SLN_WriteSection(solution_file, "ProjectDependencies", project_uuid_deps, True, True)

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
                if plat == "win64":
                    plat = "x64"
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
    solution_file.write( "# Automatically generated solution by Quiver Project Creator\n" )
    solution_file.write( "# Command Line: " + ' '.join( sys.argv[1:] ) + "\n#\n" )

    solution_file.write( "VisualStudioVersion = 16.0.28917.181\n" )
    solution_file.write( "MinimumVisualStudioVersion = 10.0.40219.1\n" )

    return


# get stuff we need from the vcxproj file, might even need more later for dependencies, oof
def GetNeededItemsFromProject(vcxproj):

    xmlns = "{http://schemas.microsoft.com/developer/msbuild/2003}"

    # configurations = []
    # platforms_elems = []
    # platforms = []
    item_groups = vcxproj.findall( xmlns + "ItemGroup" )

    '''
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
    '''
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

    return project_name, project_guid  #, configurations, platforms


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
