import uuid
import os
import sys
import qpc_hash
import xml.etree.ElementTree as et
from qpc_base import args, CreateDirectory, CreateNewDictValue, ConfigurationTypes, \
    Platforms, Compilers, Languages, PosixPath
from xml.dom import minidom
from enum import Enum


def MakeUUID():
    return f"{{{uuid.uuid4()}}}".upper()


def GetOutDir(project_list) -> str:
    out_dir = ""
    if args.project_dir:
        try:
            out_dir = PosixPath(project_list.projects[0].macros["$PROJECT_DIR"])
            # if not out_dir.endswith("/"):
            #    out_dir += "/"
        except KeyError:
            pass
    return out_dir


def CreateProject(project_list):
    out_dir = GetOutDir(project_list)
        
    print("Creating: " + project_list.file_name + ".vcxproj")
    vcxproject, include_list, res_list, none_list = CreateVCXProj(project_list)
    
    # this is a little slow due to AddFormattingToXML()
    WriteProject(project_list, out_dir, vcxproject)
    
    # would this be too much printing for the normal output? idk
    print("Creating: " + project_list.file_name + ".vcxproj.filters")
    vcxproject_filters = CreateVCXProjFilters(project_list, include_list, res_list, none_list)
    WriteProject(project_list, out_dir, vcxproject_filters, True)
    
    return out_dir


def MakeConfPlatCondition(config: str, platform: str) -> str:
    return f"'$(Configuration)|$(Platform)'=='{config}|{GetPlatform(platform)}'"


def GetPlatformRefactor(platform: Enum) -> str:
    if platform == Platforms.WIN32:
        return "Win32"
    elif platform == Platforms.WIN64:
        return "x64"


def GetPlatform(platform: str) -> str:
    if platform.lower() == "win32":
        return "Win32"
    elif platform.lower() == "win64":
        return "x64"


def CreateVCXProj(project_list):
    vcxproj = et.Element("Project")
    vcxproj.set("DefaultTargets", "Build")
    vcxproj.set("ToolsVersion", "4.0")
    # is this even needed?
    vcxproj.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")
    
    # Project Configurations
    SetupProjectConfigurations(vcxproj, project_list)
    SetupGlobals(vcxproj, project_list)
    
    elem_import = et.SubElement(vcxproj, "Import")
    elem_import.set("Project", "$(VCTargetsPath)\\Microsoft.Cpp.Default.props")
    
    SetupPropertyGroupConfigurations(vcxproj, project_list)
    
    elem_import = et.SubElement(vcxproj, "Import")
    elem_import.set("Project", "$(VCTargetsPath)\\Microsoft.Cpp.props")
    
    extension_settings = et.SubElement(vcxproj, "ImportGroup")
    extension_settings.set("Label", "ExtensionSettings")
    
    SetupPropertySheets(vcxproj)
    
    user_macros = et.SubElement(vcxproj, "PropertyGroup")
    user_macros.set("Label", "UserMacros")
    
    SetupGeneralProperties(vcxproj, project_list)
    SetupItemDefinitionGroups(vcxproj, project_list)
    
    # --------------------------------------------------------------------
    # Now, add the files
    
    full_include_list = {}
    full_res_list = {}
    full_none_list = {}
    
    header_exts = {".h", ".hxx", ".hpp"}
    none_exts = {".rc", ".h", ".hxx", ".hpp"}
    
    # TODO: merge everything together, for now, just add a condition on each one lmao
    for project in project_list.projects:
        condition = MakeConfPlatCondition(project.config_name, project.platform)

        # maybe do the same below for this?
        CreateSourceFileItemGroup(project.source_files, vcxproj, condition)
        
        include_list, remaining_files = GetProjectFiles(project.files, header_exts)
        full_include_list = {**full_include_list, **include_list}
        CreateFileItemGroups("ClInclude", include_list, vcxproj, condition)
        
        res_list, remaining_files = GetProjectFiles(remaining_files, {".rc"})
        full_res_list = {**full_res_list, **res_list}
        CreateFileItemGroups("ResourceCompile", res_list, vcxproj, condition)
        
        none_list = GetProjectFiles(remaining_files, invalid_exts=none_exts)[0]
        full_none_list = {**full_none_list, **none_list}
        CreateFileItemGroups("None", none_list, vcxproj, condition)
    
    # other vstudio stuff idk
    elem_import = et.SubElement(vcxproj, "Import")
    elem_import.set("Project", "$(VCTargetsPath)\\Microsoft.Cpp.targets")
    import_group = et.SubElement(vcxproj, "ImportGroup")
    import_group.set("Label", "ExtensionTargets")
    
    return vcxproj, full_include_list, full_res_list, full_none_list


def SetupProjectConfigurations(vcxproj, project_list):
    item_group = et.SubElement(vcxproj, "ItemGroup")
    item_group.set("Label", "ProjectConfigurations")
    
    for project in project_list.projects:
        project_configuration = et.SubElement(item_group, "ProjectConfiguration")
        project_configuration.set("Include", project.config_name + "|" + GetPlatform(project.platform))
        
        configuration = et.SubElement(project_configuration, "Configuration")
        configuration.text = project.config_name
        
        elem_platform = et.SubElement(project_configuration, "Platform")
        elem_platform.text = GetPlatform(project.platform)


def SetupGlobals(vcxproj, project_list):
    property_group = et.SubElement(vcxproj, "PropertyGroup")
    property_group.set("Label", "Globals")
    
    et.SubElement(property_group, "ProjectName").text = project_list.GetProjectName()
    et.SubElement(property_group, "ProjectGuid").text = MakeUUID()


def SetupPropertyGroupConfigurations(vcxproj, project_list):
    for project in project_list.projects:
        property_group = et.SubElement(vcxproj, "PropertyGroup")
        property_group.set("Condition", MakeConfPlatCondition(project.config_name, project.platform))
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
        
        if config.general.toolset_version == "msvc_142":
            toolset.text = "v142"
        elif config.general.toolset_version == "msvc_141":
            toolset.text = "v141"
        elif config.general.toolset_version == "msvc_140":
            toolset.text = "v140"
        elif config.general.toolset_version == "msvc_120":
            toolset.text = "v120"
        elif config.general.toolset_version == "msvc_110":
            toolset.text = "v110"
        elif config.general.toolset_version == "msvc_100":
            toolset.text = "v100"
        else:
            toolset.text = "v142"
        
        defs = config.compiler.preprocessor_definitions
        if "MBCS" in defs or "_MBCS" in defs:
            et.SubElement(property_group, "CharacterSet").text = "MultiByte"
            if "MBCS" in defs:
                defs.remove("MBCS")
            if "_MBCS" in defs:
                defs.remove("_MBCS")
                
        elif "UNICODE" in defs or "_UNICODE" in defs:
            et.SubElement(property_group, "CharacterSet").text = "Unicode"
            if "UNICODE" in defs:
                defs.remove("UNICODE")
            if "_UNICODE" in defs:
                defs.remove("_UNICODE")
        
        # "TargetName",
        # "WholeProgramOptimization",


def SetupPropertySheets(vcxproj):
    import_group = et.SubElement(vcxproj, "ImportGroup")
    import_group.set("Label", "PropertySheets")
    
    elem_import = et.SubElement(import_group, "Import")
    elem_import.set("Project", "$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props")
    elem_import.set("Condition", "exists('$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props')")
    elem_import.set("Label", "LocalAppDataPlatform")


def SetupGeneralProperties(vcxproj, project_list):
    property_group = et.SubElement(vcxproj, "PropertyGroup")
    et.SubElement(property_group, "_ProjectFileVersion").text = "10.0.30319.1"
    
    for project in project_list.projects:
        condition = MakeConfPlatCondition(project.config_name, project.platform)
        config = project.config
        
        property_group = et.SubElement(vcxproj, "PropertyGroup")
        property_group.set("Condition", condition)
        
        out_dir = et.SubElement(property_group, "OutDir")
        out_dir.text = config.general.out_dir + os.sep
        
        int_dir = et.SubElement(property_group, "IntDir")
        int_dir.text = config.general.int_dir + os.sep
        
        target_name = et.SubElement(property_group, "TargetName")
        if config.general.out_name:
            target_name.text = config.general.out_name
        else:
            target_name.text = project_list.GetProjectName()
        
        target_ext = et.SubElement(property_group, "TargetExt")
        
        if config.general.configuration_type == "application":
            target_ext.text = project_list.macros["$_APP_EXT"]
        
        elif config.general.configuration_type == "static_library":
            target_ext.text = project_list.macros["$_STATICLIB_EXT"]
        
        elif config.general.configuration_type == "dynamic_library":
            target_ext.text = project_list.macros["$_BIN_EXT"]
        
        include_paths = et.SubElement(property_group, "IncludePath")
        include_paths.text = ';'.join(config.general.include_directories)
        
        if config.general.default_include_directories:
            include_paths.text += ";$(IncludePath)"
        
        library_paths = et.SubElement(property_group, "LibraryPath")
        library_paths.text = ';'.join(config.general.library_directories)
        
        if config.general.default_library_directories:
            library_paths.text += ";$(LibraryPath)"

        # also why does WholeProgramOptimization go here and in ClCompile


def SetupItemDefinitionGroups(vcxproj, project_list):
    for project in project_list.projects:
        condition = MakeConfPlatCondition(project.config_name, project.platform)
        cfg = project.config
        
        item_def_group = et.SubElement(vcxproj, "ItemDefinitionGroup")
        item_def_group.set("Condition", condition)
        
        # ------------------------------------------------------------------
        # compiler - ClCompile
        AddCompilerOptions(et.SubElement(item_def_group, "ClCompile"), cfg.compiler, cfg.general)
        
        # ------------------------------------------------------------------
        # linker - Link or Lib
        if cfg.general.configuration_type == "static_library":
            link_lib = et.SubElement(item_def_group, "Lib")
        else:
            link_lib = et.SubElement(item_def_group, "Link")
        
        et.SubElement(link_lib, "AdditionalOptions").text = ' '.join(cfg.linker.options)
        et.SubElement(link_lib, "AdditionalDependencies").text = ';'.join(cfg.linker.libraries) + \
                                                                 ";%(AdditionalDependencies)"

        if cfg.linker.output_file:
            output_file = os.path.splitext(cfg.linker.output_file)[0]
            if cfg.general.configuration_type == "dynamic_library":
                et.SubElement(link_lib, "OutputFile").text = output_file + project.macros["$_BIN_EXT"]
            elif cfg.general.configuration_type == "static_library":
                et.SubElement(link_lib, "OutputFile").text = output_file + project.macros["$_STATICLIB_EXT"]
            elif cfg.general.configuration_type == "application":
                et.SubElement(link_lib, "OutputFile").text = output_file + project.macros["$_APP_EXT"]

        if cfg.linker.debug_file:
            et.SubElement(link_lib, "ProgramDatabaseFile").text = os.path.splitext(cfg.linker.debug_file)[0] + ".pdb"
        
        if cfg.linker.import_library:
            et.SubElement(link_lib, "ImportLibrary").text = os.path.splitext(cfg.linker.import_library)[0] + \
                                                            project.macros["$_IMPLIB_EXT"]
        
        if cfg.linker.entry_point:
            et.SubElement(link_lib, "EntryPointSymbol").text = cfg.linker.entry_point
        
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
        # pre_build, post_build, pre_link
        # PreBuildEvent, PostBuildEvent PreLinkEvent
        
        if cfg.pre_build:
            et.SubElement(et.SubElement(item_def_group, "PreBuildEvent"), "Command").text = ' '.join(cfg.pre_build)

        if cfg.post_build:
            et.SubElement(et.SubElement(item_def_group, "PostBuildEvent"), "Command").text = ' '.join(cfg.post_build)

        if cfg.pre_link:
            et.SubElement(et.SubElement(item_def_group, "PreLinkEvent"), "Command").text = ' '.join(cfg.pre_link)


# TODO: this needs to have some default visual studio settings,
#  because visual studio can't fucking pick default settings when none is set for them in the vcxproj
def AddCompilerOptions(compiler_elem, compiler, general=None):
    added_option = False
    
    if compiler.preprocessor_definitions:
        added_option = True
        preprocessor_definitions = et.SubElement(compiler_elem, "PreprocessorDefinitions")
        preprocessor_definitions.text = ';'.join(compiler.preprocessor_definitions) + \
                                        ";%(PreprocessorDefinitions)"
    
    if compiler.precompiled_header:
        added_option = True
        et.SubElement(compiler_elem, "PrecompiledHeader").text = \
            {"none": "NotUsing", "use": "Use", "create": "Create"}[compiler.precompiled_header]
    
    if compiler.precompiled_header_file:
        added_option = True
        et.SubElement(compiler_elem, "PrecompiledHeaderFile").text = compiler.precompiled_header_file
    
    if compiler.precompiled_header_output_file:
        added_option = True
        et.SubElement(compiler_elem, "PrecompiledHeaderOutputFile").text = compiler.precompiled_header_output_file
    
    if general and general.language:
        added_option = True
        et.SubElement(compiler_elem, "CompileAs").text = {"c": "CompileAsC", "cpp": "CompileAsCpp"}[general.language]
        
    # these are needed, because for some reason visual studio use shit stuff for default settings
    if general:  # basically if not file
        added_option = True
        basic_runtime_checks = et.SubElement(compiler_elem, "BasicRuntimeChecks")
        basic_runtime_checks.text = "Default"
    
    if compiler.options:
        added_option = True
        warnings_list = []
        # copying here so we don't remove from the project object, would break for the next project type
        remaining_options = [*compiler.options]

        index = 0
        # for index, option in enumerate(compiler.options):
        while len(remaining_options) > index:
            option = remaining_options[index]
            if option.startswith("/ignore:"):
                warnings_list.append(option[8:])
                remaining_options.remove(option)
            else:
                option_key, option_value = CommandToCompilerOption(option)
                if option_key and option_value:
                    
                    if general:
                        if option_key == "BasicRuntimeChecks":
                            basic_runtime_checks.text = option_value
                        else:
                            et.SubElement(compiler_elem, option_key).text = option_value
                    else:
                        et.SubElement(compiler_elem, option_key).text = option_value
                    remaining_options.remove(option)
                else:
                    index += 1
        
        if warnings_list:
            disable_warnings = et.SubElement(compiler_elem, "DisableSpecificWarnings")
            disable_warnings.text = ';'.join(warnings_list)
        
        # now add any unchanged options
        et.SubElement(compiler_elem, "AdditionalOptions").text = ' '.join(remaining_options)
    
    # TODO: convert options in the compiler.options list to options here
    #  remove any option name from this list once you convert that option
    # "InlineFunctionExpansion"
    # "IntrinsicFunctions"
    # "StringPooling"
    # "MinimalRebuild"
    # "BufferSecurityCheck"
    # "FunctionLevelLinking"
    # "EnableEnhancedInstructionSet"
    # "ForceConformanceInForLoopScope"
    # "RuntimeTypeInfo"
    # "OpenMPSupport"
    # "ExpandAttributedSource"
    # "AssemblerOutput"
    # "AssemblerListingLocation"
    # "ObjectFileName"
    # "ProgramDataBaseFileName"
    # "GenerateXMLDocumentationFiles"
    # "BrowseInformation"
    # "DebugInformationFormat"
    # "BrowseInformationFile"
    # "ErrorReporting"
    
    return added_option


# TODO: maybe finish this? idk, at least add anything that would be preventing compilation (think i already have)
COMPILER_OPTIONS = {
    "WarningLevel": {
        "/W0": "TurnOffAllWarnings",
        "/W1": "Level1", "/W2": "Level2", "/W3": "Level3", "/W4": "Level4",
        "/Wall": "EnableAllWarnings",
    },
    "RuntimeLibrary": {
        "/MT": "MultiThreaded",
        "/MTd": "MultiThreadedDebug",
        "/MD": "MultiThreadedDLL",
        "/MDd": "MultiThreadedDebugDLL",
    },
    "DebugInformationFormat": {
        "/Zi": "ProgramDatabase",
        "/ZI": "EditAndContinue",
        "/Z7": "OldStyle",
        # "/": "None",
    },
    "Optimization":                 {"/Od": "Disabled", "/O1": "MinSpace", "/O2": "MaxSpeed", "/Ox": "Full"},
    "MultiProcessorCompilation":    {"/MP": "true"},
    "WholeProgramOptimization":     {"/GL": "true"},  # also goes in Configuration PropertyGroup? tf
    "UseFullPaths":                 {"/FC": "true"},
    "ShowIncludes":                 {"/showincludes": "true"},
    "FavorSizeOrSpeed":             {"/Os": "Size",             "/Ot": "Speed"},
    "TreatWarningAsError":          {"/WX-": "false",           "/WX": "true"},
    "TreatWChar_tAsBuiltInType":    {"/Zc:wchar_t-": "false",   "/Zc:wchar_t": "true"},
    "FloatingPointModel":           {"/fp:precise": "Precise", "/fp:strict": "Strict", "/fp:fast": "Fast"},
    "ExceptionHandling":            {"/EHa": "Async", "/EHsc": "Sync", "/EHs": "SyncCThrow", "": "false"},
}


def CommandToCompilerOption(value: str) -> tuple:
    for compiler_key, value_commands in COMPILER_OPTIONS.items():
        if value in value_commands:
            return compiler_key, value_commands[value]
    return None, None


def CreateSourceFileItemGroup(file_list, parent_elem, condition):
    if file_list:
        item_group = et.SubElement(parent_elem, "ItemGroup")
        item_group.set("Condition", condition)
        for file_path, values in file_list.items():
            elem_file = et.SubElement(item_group, "ClCompile")
            elem_file.set("Include", file_path)
            AddCompilerOptions(elem_file, values.compiler)


def CreateFileItemGroups(file_type, file_dict, parent_elem, condition):
    if file_dict:
        item_group = et.SubElement(parent_elem, "ItemGroup")
        item_group.set("Condition", condition)
        for file_path in file_dict:
            elem_file = et.SubElement(item_group, file_type)
            elem_file.set("Include", file_path)


# TODO: maybe move this to the project class and rename to GetFilesByExt?
def GetProjectFiles(project_files, valid_exts=None, invalid_exts=None):
    if not valid_exts:
        valid_exts = ()
    if not invalid_exts:
        invalid_exts = ()
    
    # now get only add any file that has any of the valid file extensions and none of the invalid ones
    wanted_files = {}
    unwanted_files = {}
    for file_path, folder_path in project_files.items():
        if file_path not in wanted_files:
            file_ext = os.path.splitext(file_path)[1].casefold()
            if file_ext not in invalid_exts:
                if valid_exts and file_ext not in valid_exts:
                    unwanted_files[file_path] = folder_path
                else:
                    wanted_files[file_path] = folder_path
    
    return wanted_files, unwanted_files


def CreateVCXProjFilters(project_list, include_list, res_list, none_list):
    proj_filters = et.Element("Project")
    proj_filters.set("ToolsVersion", "4.0")
    proj_filters.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")
    
    Create_FolderFilters(proj_filters, project_list)
    
    for project in project_list.projects:
        # these functions here are slow, oof
        Create_SourceFileItemGroupFilters(proj_filters, project.source_files, "ClCompile")
    
    Create_ItemGroupFilters(proj_filters, include_list, "ClInclude")
    Create_ItemGroupFilters(proj_filters, res_list, "ResourceCompile")
    Create_ItemGroupFilters(proj_filters, none_list, "None")
    
    return proj_filters


def Create_FolderFilters(proj_filters, project_list):
    folder_list = project_list.GetAllEditorFolderPaths()
    if folder_list:
        item_group = et.SubElement(proj_filters, "ItemGroup")
        for folder in folder_list:
            elem_folder = et.SubElement(item_group, "Filter")
            elem_folder.set("Include", folder)
            unique_identifier = et.SubElement(elem_folder, "UniqueIdentifier")
            unique_identifier.text = MakeUUID()


def Create_SourceFileItemGroupFilters(proj_filters, files_dict, filter_name):
    item_group = et.SubElement(proj_filters, "ItemGroup")
    for file_path, source_file in files_dict.items():
        elem_file = et.SubElement(item_group, filter_name)
        elem_file.set("Include", file_path)
        if source_file.folder:
            folder = et.SubElement(elem_file, "Filter")
            folder.text = source_file.folder


def Create_ItemGroupFilters(proj_filters, files_dict, filter_name):
    item_group = et.SubElement(proj_filters, "ItemGroup")
    for file_path, folder_path in files_dict.items():
        elem_file = et.SubElement(item_group, filter_name)
        elem_file.set("Include", file_path)
        if folder_path:
            folder = et.SubElement(elem_file, "Filter")
            folder.text = folder_path


# --------------------------------------------------------------------------------------------------


def WriteProject(project_list, out_dir, xml_file, filters=False):
    if out_dir and not out_dir.endswith("/"):
        out_dir += "/"
    file_path = out_dir + os.path.splitext(project_list.file_name)[0] + ".vcxproj"
    
    if filters:
        file_path += ".filters"
        
    # directory = os.path.split(file_path)
    CreateDirectory(out_dir)
    
    with open(file_path, "w", encoding="utf-8") as project_file:
        project_file.write(AddFormattingToXML(xml_file))


def AddFormattingToXML(elem):
    return minidom.parseString(et.tostring(elem, 'utf-8')).toprettyxml(indent="  ")


# --------------------------------------------------------------------------------------------------

# sln keys:
# https://www.codeproject.com/Reference/720512/List-of-Visual-Studio-Project-Type-GUIDs

def MakeSolutionFile(project_def_list, project_list, solution_path,
                     configurations: list, platforms: list, project_dependencies: dict):
    cpp_uuid = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"
    filter_uuid = "{2150E333-8FDC-42A3-9474-1A3956D46DE8}"
    
    solution_path += ".sln"
    
    print("Creating Solution File: " + solution_path + "\n")
    
    out_dir_dict = {}
    for hash_path, qpc_path in project_list.items():
        out_dir_dict[qpc_path] = qpc_hash.GetOutDir(hash_path)
    
    with open(solution_path, "w", encoding="utf-8") as solution_file:
        WriteTopOfSolution(solution_file)
        
        project_uuid_dict = {}
        project_folder_uuid = {}
        
        for project_def in project_def_list:
            
            for folder in project_def.group_folder_list:
                if folder not in project_folder_uuid:
                    project_folder_uuid[folder] = MakeUUID()
            
            for script_path in project_def.script_list:
                try:
                    out_dir = out_dir_dict[script_path]
                except KeyError:
                    print("Project script is not in project_list? wtf")
                    continue
                vcxproj_path = out_dir + "/" + os.path.splitext(os.path.basename(script_path))[0] + ".vcxproj"
                
                if not os.path.isfile(vcxproj_path):
                    print("Project does not exist: " + vcxproj_path)
                    continue
                
                tree = et.parse(vcxproj_path)
                vcxproj = tree.getroot()
                
                project_name, project_uuid = GetNameAndUUIDFromProject(vcxproj)
                
                # shut
                CreateNewDictValue(project_uuid_dict, project_def.name, "list")
                project_uuid_dict[project_def.name].append(project_uuid)
                
                SLN_WriteProjectLine(solution_file, project_name, vcxproj_path, cpp_uuid, project_uuid)
                
                # TODO: add dependencies to the project class and then use that here
                #  and have a GetDependencies() function for if the hash check passes
                # write any project dependencies
                project_uuid_deps = GetProjectDependencies(project_list, project_dependencies[script_path])
                SLN_WriteSection(solution_file, "ProjectDependencies", project_uuid_deps, True, True)
                
                solution_file.write("EndProject\n")
        
        # Write the folders as projects because vstudio dumb
        # might have to make this a project def, idk
        for folder_name, folder_uuid in project_folder_uuid.items():
            SLN_WriteProjectLine(solution_file, folder_name, folder_name, filter_uuid, folder_uuid)
            solution_file.write("EndProject\n")
        
        # Write the global stuff
        solution_file.write("Global\n")
        
        config_plat_list = []
        for config in configurations:
            for plat in platforms:
                config_plat_list.append(config + "|" + GetPlatform(plat))
        
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
                if project_def.group_folder_list[-(folder_index + 1)] in project_folder_uuid:
                    folder_uuid = project_folder_uuid[project_folder]
                    for project_uuid in project_uuid_dict[project_def.name]:
                        global_folder_uuid_dict[project_uuid] = folder_uuid
            
            # sub folders
            if len(project_def.group_folder_list) > 1:
                folder_index = -1
                while folder_index < len(project_def.group_folder_list):
                    project_sub_folder = project_def.group_folder_list[folder_index]
                    try:
                        project_folder = project_def.group_folder_list[folder_index - 1]
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


def WriteTopOfSolution(solution_file):
    solution_file.write("Microsoft Visual Studio Solution File, Format Version 12.00\n")
    
    # solution_file.write( "# Visual Studio Version 16\n" )
    solution_file.write("# Automatically generated solution by Quiver Project Creator\n")
    solution_file.write("# Command Line: " + ' '.join(sys.argv[1:]) + "\n#\n")
    
    solution_file.write("VisualStudioVersion = 16.0.28917.181\n")
    solution_file.write("MinimumVisualStudioVersion = 10.0.40219.1\n")


# get stuff we need from the vcxproj file, might even need more later for dependencies, oof
def GetNameAndUUIDFromProject(vcxproj):
    xmlns = "{http://schemas.microsoft.com/developer/msbuild/2003}"
    
    # configurations = []
    # platforms_elems = []
    # platforms = []
    item_groups = vcxproj.findall(xmlns + "ItemGroup")
    
    property_groups = vcxproj.findall(xmlns + "PropertyGroup")
    
    project_name = None
    project_guid = None
    for property_group in property_groups:
        
        # checking if it's None because even if this is set to the element return,
        # it would still pass "if not project_name:"
        if project_name is None:
            project_name = property_group.findall(xmlns + "ProjectName")[0]
        
        if project_guid is None:
            project_guid = property_group.findall(xmlns + "ProjectGuid")[0]
        
        if project_guid is not None and project_name is not None:
            # return project_name.text, project_guid.text
            project_name = project_name.text
            project_guid = project_guid.text
            break
    
    return project_name, project_guid


def SLN_WriteProjectLine(solution_file, project_name, vcxproj_path, cpp_uuid, vcxproj_uuid):
    solution_file.write(
        'Project("{0}") = "{1}", "{2}", "{3}"\n'.format(cpp_uuid, project_name, vcxproj_path, vcxproj_uuid))


def SLN_WriteSection(solution_file, section_name, key_value_dict, is_post=False, is_project_section=False):
    if key_value_dict:
        if is_project_section:
            section_type = "Project"
            section_type_prepost = "Project\n"
        else:
            section_type = "Global"
            section_type_prepost = "Solution\n"
        solution_type = "post" + section_type_prepost if is_post else "pre" + section_type_prepost

        solution_file.write("\t{0}Section({1}) = {2}".format(section_type, section_name, solution_type))
        for key, value in key_value_dict.items():
            solution_file.write("\t\t{0} = {1}\n".format(key, value))
        solution_file.write("\tEnd{0}Section\n".format(section_type))


# unused, remove later
# should change this to look every vcxproj file and
# check if the output file in Lib fits what the project needs
# first check if the config type is a StaticLibrary, then check OutputFile in Lib
def GetProjectDependencies(project_dict: dict, project_dependency_paths: list) -> dict:
    project_list = set(project_dict.values())
    project_dependencies = {}
    for dependency_path in project_dependency_paths:
        if dependency_path in project_list:
            vcxproj_path = os.path.splitext(dependency_path)[0] + ".vcxproj"
            if os.path.isabs(vcxproj_path):
                vcxproj_abspath = os.path.normpath(vcxproj_path)
            else:
                vcxproj_abspath = os.path.normpath(args.root_dir + os.sep + vcxproj_path)
    
            try:
                vcxproj = et.parse(vcxproj_abspath).getroot()
                project_name, project_uuid = GetNameAndUUIDFromProject(vcxproj)
        
                # very cool vstudio
                project_dependencies[project_uuid] = project_uuid
            except FileNotFoundError as F:
                print(str(F))

    return project_dependencies
