import uuid
import os
import sys
import qpc_hash
import lxml.etree as et
from time import perf_counter
from qpc_args import args
from qpc_base import BaseProjectGenerator, Platform, Arch
from qpc_project import PrecompiledHeader, ConfigType, Language, ProjectContainer
from qpc_parser import BaseInfo
from enum import Enum


def timer_diff(start_time: float) -> str:
    return str(round(perf_counter() - start_time, 4))


class VisualStudioGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("Visual Studio")
        self._add_platform(Platform.WINDOWS)
        self._add_architectures(Arch.I386, Arch.AMD64)
        self._set_project_folders(True)
        self._set_generate_master_file(True)
        self._set_macro("VISUAL_STUDIO")
        
        self.cpp_uuid = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"
        self.filter_uuid = "{2150E333-8FDC-42A3-9474-1A3956D46DE8}"
        self.project_uuid_dict = {}
        self.project_folder_uuid = {}
        self.out_dir_dict = {}
        self.solution_file = None

    # TODO: move most of this stuff to a vs_cpp file, so you can also do c# here
    #  though you did have most of the cpp stuff in separate functions, so it should be easy to move and add C# support
    def create_project(self, project: ProjectContainer) -> None:
        project_passes = self._get_passes(project)
        if not project_passes:
            return
        
        out_dir = project.get_out_dir()

        if args.time:
            start_time = perf_counter()
        else:
            print("Creating: " + project.file_name + ".vcxproj")

        vcx_project, include_list, res_list, none_list = create_vcxproj(project, project_passes)
        write_project(project, out_dir, vcx_project, ".vcxproj")
        
        if args.time:
            print(timer_diff(start_time) + " - Created: " + project.file_name + ".vcxproj")
        
        if args.time:
            start_time = perf_counter()
        else:
            print("Creating: " + project.file_name + ".vcxproj.filters")
            
        vcxproject_filters = create_vcxproj_filters(project, project_passes, include_list, res_list, none_list)
        write_project(project, out_dir, vcxproject_filters, ".vcxproj.filters")

        if args.time:
            print(timer_diff(start_time) + " - Created: " + project.file_name + ".vcxproj.filters")
        
        if self.has_debug_commands(project_passes):
            if args.time:
                start_time = perf_counter()
            else:
                print("Creating: " + project.file_name + ".vcxproj.user")
                
            vcxproject_user = create_vcxproj_user(project, project_passes)
            write_project(project, out_dir, vcxproject_user, ".vcxproj.user")

            if args.time:
                print(timer_diff(start_time) + " - Created: " + project.file_name + ".vcxproj.user")
        
        # return out_dir
        
    def has_debug_commands(self, project_passes: list) -> bool:
        for project in project_passes:
            if bool(project.config.debug):
                return True
        return False
    
    def does_project_exist(self, project_out_dir: str) -> bool:
        # base_path = self._get_base_path(project_out_dir)
        split_ext_path = os.path.splitext(project_out_dir)[0]
        return os.path.isfile(split_ext_path + ".vcxproj") and os.path.isfile(split_ext_path + ".vcxproj.filters")
    
    def does_master_file_exist(self, master_file_path: str) -> bool:
        base_path, project_name = os.path.split(master_file_path)
        split_ext_path = os.path.splitext(master_file_path)[0]
        base_path += "/"
        return os.path.isfile(split_ext_path + ".sln")

    def get_master_file_path(self, master_file_path: str) -> str:
        return master_file_path + ".sln"
    
    def create_master_file(self, info: BaseInfo, master_file_path: str) -> None:
        print("Creating Solution File: " + master_file_path)
    
        # slow?
        self.out_dir_dict = {}
        for qpc_path, hash_path in info.project_hashes.items():
            if qpc_path in info.project_dependencies:
                self.out_dir_dict[qpc_path] = qpc_hash.get_out_dir(hash_path)
                
        info_win = info.get_base_info(Platform.WINDOWS)
    
        with open(master_file_path, "w", encoding="utf-8") as self.solution_file:
            write_solution_header(self.solution_file)

            self.project_uuid_dict = {}
            self.project_folder_uuid = {}
            
            [self.sln_project_def_loop(project_def, info) for project_def in info_win.projects]
        
            # Write the folders as base_info because vstudio dumb
            # might have to make this a project def, idk
            for folder_name, folder_uuid in self.project_folder_uuid.items():
                sln_write_project_line(self.solution_file, folder_name, folder_name, self.filter_uuid, folder_uuid)
                self.solution_file.write("EndProject\n")
        
            # Write the global stuff
            self.solution_file.write("Global\n")
            
            config_plat_list = []
            for plat in self._platforms:
                for config in info.get_base_info(plat).configurations:
                    for arch in self._architectures:
                        config_plat_list.append(config + "|" + convert_arch(arch))
        
            # SolutionConfigurationPlatforms
            sln_config_plat = {}
            for config_plat in config_plat_list:
                sln_config_plat[config_plat] = config_plat
        
            sln_write_section(self.solution_file, "SolutionConfigurationPlatforms", sln_config_plat, False)
        
            # ProjectConfigurationPlatforms
            proj_config_plat = {}
            for project_uuid_list in self.project_uuid_dict.values():
                for project_uuid in project_uuid_list:
                    for config_plat in config_plat_list:
                        proj_config_plat[project_uuid + "." + config_plat + ".ActiveCfg"] = config_plat
                        # TODO: maybe get some setting for a default project somehow, i think the default is set here
                        proj_config_plat[project_uuid + "." + config_plat + ".Build.0"] = config_plat
        
            sln_write_section(self.solution_file, "ProjectConfigurationPlatforms", proj_config_plat, True)
        
            # write the project folders
            global_folder_uuid_dict = {}
            for project_def in info_win.projects:
                if project_def.name not in self.project_uuid_dict:
                    continue
            
                # all_projects
                for folder_index, project_folder in enumerate(project_def.folder_list):
                    if project_def.folder_list[-(folder_index + 1)] in self.project_folder_uuid:
                        folder_uuid = self.project_folder_uuid[project_folder]
                        for project_uuid in self.project_uuid_dict[project_def.name]:
                            global_folder_uuid_dict[project_uuid] = folder_uuid
            
                # sub folders, i have no clue how this works anymore and im not touching it unless i have to
                if len(project_def.folder_list) > 1:
                    folder_index = -1
                    while folder_index < len(project_def.folder_list):
                        project_sub_folder = project_def.folder_list[folder_index]
                        try:
                            project_folder = project_def.folder_list[folder_index - 1]
                        except IndexError:
                            break
                    
                        if project_sub_folder in self.project_folder_uuid:
                            sub_folder_uuid = self.project_folder_uuid[project_sub_folder]
                            folder_uuid = self.project_folder_uuid[project_folder]
                            if sub_folder_uuid not in global_folder_uuid_dict:
                                global_folder_uuid_dict[sub_folder_uuid] = folder_uuid
                            folder_index -= 1
        
            sln_write_section(self.solution_file, "NestedProjects", global_folder_uuid_dict, False)
            self.solution_file.write("EndGlobal\n")

    def sln_project_def_loop(self, project_def, info):
        for folder in project_def.folder_list:
            if folder not in self.project_folder_uuid:
                self.project_folder_uuid[folder] = make_uuid()
        
        for script_path in project_def.script_list:
            if script_path in self.out_dir_dict:
                out_dir = self.out_dir_dict[script_path]
            else:
                continue
            if out_dir is None:
                continue
                
            vcxproj_path = out_dir + "/" + os.path.splitext(os.path.basename(script_path))[0] + ".vcxproj"
            
            if not os.path.isfile(vcxproj_path):
                print("Project does not exist: " + vcxproj_path)
                continue
            
            tree = et.parse(vcxproj_path)
            vcxproj = tree.getroot()
            
            project_name, project_uuid = get_name_and_uuid(vcxproj)
            
            if project_def.name not in self.project_uuid_dict:
                self.project_uuid_dict[project_def.name] = []
            self.project_uuid_dict[project_def.name].append(project_uuid)
            
            sln_write_project_line(self.solution_file, project_name, vcxproj_path, self.cpp_uuid, project_uuid)
            
            # TODO: add dependencies to the container class and then use that here
            #  and have a GetDependencies() function for if the hash check _passes
            # write any container dependencies
            uuid_deps = get_project_dependencies(info.project_hashes, info.project_dependencies[script_path])
            sln_write_section(self.solution_file, "ProjectDependencies", uuid_deps, True, True)
            
            self.solution_file.write("EndProject\n")


def convert_arch(arch: Arch) -> str:
    if arch == Arch.I386:
        return "Win32"
    elif arch == Arch.AMD64:
        return "x64"


def make_uuid():
    return f"{{{uuid.uuid4()}}}".upper()


def make_conf_plat_cond(config: str, arch: Arch) -> str:
    return f"'$(Configuration)|$(Platform)'=='{config}|{convert_arch(arch)}'"


def create_vcxproj(project_list: ProjectContainer, project_passes: list):
    vcxproj = et.Element("Project")
    vcxproj.set("DefaultTargets", "Build")
    vcxproj.set("ToolsVersion", "4.0")
    # is this even needed?
    vcxproj.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")
    
    # Project Configurations
    setup_project_configurations(vcxproj, project_passes)
    setup_globals(vcxproj, project_list)
    
    et.SubElement(vcxproj, "Import").set("Project", "$(VCTargetsPath)\\Microsoft.Cpp.Default.props")
    
    setup_property_group_configurations(vcxproj, project_passes)
    
    et.SubElement(vcxproj, "Import").set("Project", "$(VCTargetsPath)\\Microsoft.Cpp.props")
    et.SubElement(vcxproj, "ImportGroup").set("Label", "ExtensionSettings")
    
    setup_property_sheets(vcxproj)
    
    et.SubElement(vcxproj, "PropertyGroup").set("Label", "UserMacros")
    
    setup_general_properties(vcxproj, project_passes)
    setup_item_definition_groups(vcxproj, project_passes)
    
    # --------------------------------------------------------------------
    # Now, add the files
    
    full_include_list = {}
    full_res_list = {}
    full_none_list = {}
    
    header_exts = {".h", ".hxx", ".hpp"}
    none_exts = {".rc", ".h", ".hxx", ".hpp"}
    
    # TODO: merge everything together, for now, just add a condition on each one lmao
    for project in project_passes:
        condition = make_conf_plat_cond(project.config_name, project.arch)

        # maybe do the same below for this?
        create_source_file_item_group(project.source_files, vcxproj, condition)
        
        include_list, remaining_files = get_project_files(project.files, header_exts)
        full_include_list = {**full_include_list, **include_list}
        create_file_item_groups("ClInclude", include_list, vcxproj, condition)
        
        res_list, remaining_files = get_project_files(remaining_files, {".rc"})
        full_res_list = {**full_res_list, **res_list}
        create_file_item_groups("ResourceCompile", res_list, vcxproj, condition)
        
        none_list = get_project_files(remaining_files, invalid_exts=none_exts)[0]
        full_none_list = {**full_none_list, **none_list}
        create_file_item_groups("None", none_list, vcxproj, condition)
    
    # other vstudio stuff idk
    et.SubElement(vcxproj, "Import").set("Project", "$(VCTargetsPath)\\Microsoft.Cpp.targets")
    et.SubElement(vcxproj, "ImportGroup").set("Label", "ExtensionTargets")
    
    return vcxproj, full_include_list, full_res_list, full_none_list


def setup_project_configurations(vcxproj, project_passes: list):
    item_group = et.SubElement(vcxproj, "ItemGroup")
    item_group.set("Label", "ProjectConfigurations")
    
    for project in project_passes:
        project_configuration = et.SubElement(item_group, "ProjectConfiguration")
        project_configuration.set("Include", project.config_name + "|" + convert_arch(project.arch))
        
        et.SubElement(project_configuration, "Configuration").text = project.config_name
        et.SubElement(project_configuration, "Platform").text = convert_arch(project.arch)


def setup_globals(vcxproj, project_list):
    property_group = et.SubElement(vcxproj, "PropertyGroup")
    property_group.set("Label", "Globals")
    
    et.SubElement(property_group, "ProjectName").text = project_list.get_display_name()
    et.SubElement(property_group, "ProjectGuid").text = make_uuid()
    
    
COMPILER_DICT = {
    "msvc":         "v142",  # latest
    "msvc_142":     "v142",
    "msvc_141":     "v141",
    "msvc_140":     "v140",
    "msvc_120":     "v120",
    "msvc_100":     "v100",
    "msvc_140_xp":  "v140_xp",
    "msvc_120_xp":  "v120_xp",
    "clang_cl":     "ClangCL",
}


def setup_property_group_configurations(vcxproj, project_passes: list):
    for project in project_passes:
        property_group = et.SubElement(vcxproj, "PropertyGroup")
        property_group.set("Condition", make_conf_plat_cond(project.config_name, project.arch))
        property_group.set("Label", "Configuration")
        
        config = project.config
        
        configuration_type = et.SubElement(property_group, "ConfigurationType")
        
        if config.general.configuration_type == ConfigType.APPLICATION:
            configuration_type.text = "Application"
        elif config.general.configuration_type == ConfigType.STATIC_LIBRARY:
            configuration_type.text = "StaticLibrary"
        elif config.general.configuration_type == ConfigType.DYNAMIC_LIBRARY:
            configuration_type.text = "DynamicLibrary"
        
        toolset = et.SubElement(property_group, "PlatformToolset")
        
        if config.general.compiler and config.general.compiler in COMPILER_DICT:
            toolset.text = COMPILER_DICT[config.general.compiler]
        else:
            toolset.text = COMPILER_DICT["msvc"]

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


def setup_property_sheets(vcxproj):
    import_group = et.SubElement(vcxproj, "ImportGroup")
    import_group.set("Label", "PropertySheets")
    
    elem_import = et.SubElement(import_group, "Import")
    elem_import.set("Project", "$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props")
    elem_import.set("Condition", "exists('$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props')")
    elem_import.set("Label", "LocalAppDataPlatform")


def setup_general_properties(vcxproj, project_passes: list):
    property_group = et.SubElement(vcxproj, "PropertyGroup")
    et.SubElement(property_group, "_ProjectFileVersion").text = "10.0.30319.1"
    
    for project in project_passes:
        condition = make_conf_plat_cond(project.config_name, project.arch)
        config = project.config
        
        property_group = et.SubElement(vcxproj, "PropertyGroup")
        property_group.set("Condition", condition)
        
        out_dir = et.SubElement(property_group, "OutDir")
        out_dir.text = config.general.out_dir + os.sep
        
        int_dir = et.SubElement(property_group, "IntDir")
        int_dir.text = config.general.build_dir + os.sep
        
        et.SubElement(property_group, "TargetName").text = config.general.out_name
        
        target_ext = et.SubElement(property_group, "TargetExt")
        
        if config.general.configuration_type == ConfigType.APPLICATION:
            target_ext.text = project.macros["$_APP_EXT"]
        
        elif config.general.configuration_type == ConfigType.STATIC_LIBRARY:
            target_ext.text = project.macros["$_STATICLIB_EXT"]
        
        elif config.general.configuration_type == ConfigType.DYNAMIC_LIBRARY:
            target_ext.text = project.macros["$_BIN_EXT"]
        
        include_paths = et.SubElement(property_group, "IncludePath")
        include_paths.text = ';'.join(config.general.include_directories)
        
        if config.general.default_include_directories:
            include_paths.text += ";$(IncludePath)"
        
        library_paths = et.SubElement(property_group, "LibraryPath")
        library_paths.text = ';'.join(config.general.library_directories)
        
        if config.general.default_library_directories:
            library_paths.text += ";$(LibraryPath)"

        # also why does WholeProgramOptimization go here and in ClCompile


def setup_item_definition_groups(vcxproj: et.Element, project_passes: list):
    for project in project_passes:
        condition = make_conf_plat_cond(project.config_name, project.arch)
        cfg = project.config
        
        item_def_group = et.SubElement(vcxproj, "ItemDefinitionGroup")
        item_def_group.set("Condition", condition)
        
        # ------------------------------------------------------------------
        # compiler - ClCompile
        add_compiler_options(et.SubElement(item_def_group, "ClCompile"), cfg.compiler, cfg.general)
        
        # ------------------------------------------------------------------
        # linker - Link or Lib
        if cfg.general.configuration_type == ConfigType.STATIC_LIBRARY:
            link_lib = et.SubElement(item_def_group, "Lib")
        else:
            link_lib = et.SubElement(item_def_group, "Link")
        
        et.SubElement(link_lib, "AdditionalOptions").text = ' '.join(cfg.linker.options)
        et.SubElement(link_lib, "AdditionalDependencies").text = ';'.join(cfg.linker.libraries) + \
                                                                 ";%(AdditionalDependencies)"

        if cfg.linker.output_file:
            output_file = os.path.splitext(cfg.linker.output_file)[0]
            if cfg.general.configuration_type == ConfigType.DYNAMIC_LIBRARY:
                et.SubElement(link_lib, "OutputFile").text = output_file + project.macros["$_BIN_EXT"]
            elif cfg.general.configuration_type == ConfigType.STATIC_LIBRARY:
                et.SubElement(link_lib, "OutputFile").text = output_file + project.macros["$_STATICLIB_EXT"]
            elif cfg.general.configuration_type == ConfigType.APPLICATION:
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
            et.SubElement(et.SubElement(item_def_group, "PreBuildEvent"), "Command").text = '\n'.join(cfg.pre_build)

        if cfg.post_build:
            et.SubElement(et.SubElement(item_def_group, "PostBuildEvent"), "Command").text = '\n'.join(cfg.post_build)

        if cfg.pre_link:
            et.SubElement(et.SubElement(item_def_group, "PreLinkEvent"), "Command").text = '\n'.join(cfg.pre_link)
            
            
PRECOMPILED_HEADER_DICT =  {
    PrecompiledHeader.NONE: "NotUsing",
    PrecompiledHeader.USE: "Use",
    PrecompiledHeader.CREATE: "Create"
}


def add_compiler_options(compiler_elem: et.SubElement, compiler, general=None):
    added_option = False
    
    if compiler.preprocessor_definitions:
        added_option = True
        preprocessor_definitions = et.SubElement(compiler_elem, "PreprocessorDefinitions")
        preprocessor_definitions.text = ';'.join(compiler.preprocessor_definitions) + \
                                        ";%(PreprocessorDefinitions)"
    
    if compiler.precompiled_header:
        added_option = True
        et.SubElement(compiler_elem, "PrecompiledHeader").text = PRECOMPILED_HEADER_DICT[compiler.precompiled_header]
    
    if compiler.precompiled_header_file:
        added_option = True
        et.SubElement(compiler_elem, "PrecompiledHeaderFile").text = compiler.precompiled_header_file
    
    if compiler.precompiled_header_output_file:
        added_option = True
        et.SubElement(compiler_elem, "PrecompiledHeaderOutputFile").text = compiler.precompiled_header_output_file
    
    if general and general.language:
        added_option = True
        if general.language == Language.CPP:
            et.SubElement(compiler_elem, "CompileAs").text = "CompileAsCpp"
        else:
            et.SubElement(compiler_elem, "CompileAs").text = "CompileAsC"
        
    # these are needed, because for some reason visual studio use shit stuff for default info
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
                option_key, option_value = command_to_compiler_option(option)
                if option_key and option_value:
                    
                    if general and option_key == "BasicRuntimeChecks":
                        basic_runtime_checks.text = option_value
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


def command_to_compiler_option(value: str) -> tuple:
    for compiler_key, value_commands in COMPILER_OPTIONS.items():
        if value in value_commands:
            return compiler_key, value_commands[value]
    return None, None


def create_source_file_item_group(file_list, parent_elem, condition):
    if file_list:
        item_group = et.SubElement(parent_elem, "ItemGroup")
        item_group.set("Condition", condition)
        for file_path, values in file_list.items():
            elem_file = et.SubElement(item_group, "ClCompile")
            elem_file.set("Include", file_path)
            add_compiler_options(elem_file, values.compiler)


def create_file_item_groups(file_type, file_dict, parent_elem, condition):
    if file_dict:
        item_group = et.SubElement(parent_elem, "ItemGroup")
        item_group.set("Condition", condition)
        for file_path in file_dict:
            elem_file = et.SubElement(item_group, file_type)
            elem_file.set("Include", file_path)


# TODO: maybe move this to the project class and rename to get_files_by_ext?
def get_project_files(project_files, valid_exts=None, invalid_exts=None):
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


def create_vcxproj_filters(project_list: ProjectContainer, project_passes: list,
                           include_list: dict, res_list: dict, none_list: dict) -> et.Element:
    proj_filters = et.Element("Project")
    proj_filters.set("ToolsVersion", "4.0")
    proj_filters.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")
    
    create_folder_filters(proj_filters, project_list)
    
    for project in project_passes:
        # these functions here are slow, oof
        create_source_file_item_group_filters(proj_filters, project.source_files, "ClCompile")
    
    create_item_group_filters(proj_filters, include_list, "ClInclude")
    create_item_group_filters(proj_filters, res_list,     "ResourceCompile")
    create_item_group_filters(proj_filters, none_list,    "None")
    
    return proj_filters


def create_folder_filters(proj_filters, project_list):
    folder_list = project_list.get_editor_folders("\\")
    if folder_list:
        item_group = et.SubElement(proj_filters, "ItemGroup")
        for folder in folder_list:
            elem_folder = et.SubElement(item_group, "Filter")
            elem_folder.set("Include", folder)
            unique_identifier = et.SubElement(elem_folder, "UniqueIdentifier")
            unique_identifier.text = make_uuid()


def create_source_file_item_group_filters(proj_filters, files_dict, filter_name):
    item_group = et.SubElement(proj_filters, "ItemGroup")
    for file_path, source_file in files_dict.items():
        elem_file = et.SubElement(item_group, filter_name)
        elem_file.set("Include", file_path)
        if source_file.folder:
            folder = et.SubElement(elem_file, "Filter")
            folder.text = source_file.folder.replace("/", "\\")


def create_item_group_filters(proj_filters, files_dict, filter_name):
    item_group = et.SubElement(proj_filters, "ItemGroup")
    for file_path, folder_path in files_dict.items():
        elem_file = et.SubElement(item_group, filter_name)
        elem_file.set("Include", file_path)
        if folder_path:
            folder = et.SubElement(elem_file, "Filter")
            folder.text = folder_path.replace("/", "\\")


def create_directory(directory: str) -> None:
    try:
        os.makedirs(directory)
        if args.verbose:
            print("Created Directory: " + directory)
    except FileExistsError:
        pass
    except FileNotFoundError:
        pass


def write_project(project: ProjectContainer, out_dir: str, xml_file: et.Element, ext: str) -> None:
    if out_dir and not out_dir.endswith("/"):
        out_dir += "/"
    file_path = out_dir + os.path.splitext(project.file_name)[0] + ext
        
    # directory = os.path.split(file_path)
    create_directory(out_dir)
    
    with open(file_path, "w", encoding="utf-8") as project_file:
        project_file.write(xml_to_string(xml_file))


def xml_to_string(elem) -> str:
    return et.tostring(elem, pretty_print=True).decode("utf-8")


# --------------------------------------------------------------------------------------------------


def create_vcxproj_user(project: ProjectContainer, project_passes: list) -> et.Element:
    file_path = os.path.splitext(project.file_name)[0] + ".vcxproj.user"
    if os.path.isfile(file_path):
        vcxproj = et.parse(file_path).getroot()
    else:
        vcxproj = et.Element("Project")
        vcxproj.set("ToolsVersion", "Current")
        vcxproj.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")
    
    for project_pass in project_passes:
        condition = make_conf_plat_cond(project_pass.config_name, project_pass.arch)
        create_debug_group(vcxproj, project_pass.config.debug, condition)
    
    return vcxproj


# debug is Debug in qpc_project.py
def create_debug_group(vcxproj: et.Element, debug, condition):
    xmlns = "{http://schemas.microsoft.com/developer/msbuild/2003}"
    
    property_group_list = vcxproj.findall(xmlns + "PropertyGroup")
    for property_group in property_group_list:
        found_cond = property_group.get("Condition")
        if found_cond == condition:
            break
    else:
        property_group = et.SubElement(vcxproj, "PropertyGroup")
        property_group.set("Condition", condition)

    command = property_group.findall(xmlns + "LocalDebuggerCommand")
    working_dir = property_group.findall(xmlns + "LocalDebuggerWorkingDirectory")
    arguments = property_group.findall(xmlns + "LocalDebuggerCommandArguments")
    debug_flavor = property_group.findall(xmlns + "DebuggerFlavor")
    
    if debug.command:
        if command:
            command[0].text = debug.command
        else:
            et.SubElement(property_group, "LocalDebuggerCommand").text = debug.command
    
    if debug.working_dir:
        if working_dir:
            working_dir[0].text = debug.working_dir
        else:
            et.SubElement(property_group, "LocalDebuggerWorkingDirectory").text = debug.working_dir
        
    if debug.arguments:
        if arguments:
            arguments[0].text = debug.arguments
        else:
            et.SubElement(property_group, "LocalDebuggerCommandArguments").text = debug.arguments
        
    # idk if this is even needed
    if not debug_flavor:
        et.SubElement(property_group, "DebuggerFlavor").text = "WindowsLocalDebugger"


# --------------------------------------------------------------------------------------------------

# sln keys:
# https://www.codeproject.com/Reference/720512/List-of-Visual-Studio-Project-Type-GUIDs


def write_solution_header(solution_file):
    solution_file.write("Microsoft Visual Studio Solution File, Format Version 12.00\n")
    
    # solution_file.write( "# Visual Studio Version 16\n" )
    solution_file.write("# Automatically generated solution by Quiver Project Creator\n")
    solution_file.write("# Command Line: " + ' '.join(sys.argv[1:]) + "\n#\n")
    
    solution_file.write("VisualStudioVersion = 16.0.28917.181\n")
    solution_file.write("MinimumVisualStudioVersion = 10.0.40219.1\n")


# get stuff we need from the vcxproj file, might even need more later for dependencies, oof
def get_name_and_uuid(vcxproj):
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


def sln_write_project_line(solution_file, project_name, vcxproj_path, cpp_uuid, vcxproj_uuid):
    solution_file.write(
        'Project("{0}") = "{1}", "{2}", "{3}"\n'.format(cpp_uuid, project_name, vcxproj_path, vcxproj_uuid))


def sln_write_section(solution_file, section_name, key_value_dict, is_post=False, is_project_section=False):
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


def get_project_dependencies(project_dict: dict, project_dependency_paths: set) -> dict:
    project_list = set(project_dict.keys())
    project_dependencies = {}
    for dependency_path in project_dependency_paths:
        if dependency_path in project_list:
            vcxproj_path = os.path.splitext(dependency_path)[0] + ".vcxproj"
            if os.path.isabs(vcxproj_path):
                vcxproj_abspath = os.path.normpath(vcxproj_path)
            else:
                vcxproj_abspath = os.path.normpath(args.root_dir + os.sep + vcxproj_path)
                
            if not os.path.isfile(vcxproj_abspath):
                # probably was not built for this platform
                continue
    
            try:
                vcxproj = et.parse(vcxproj_abspath).getroot()
                project_name, project_uuid = get_name_and_uuid(vcxproj)
        
                # very cool vstudio
                project_dependencies[project_uuid] = project_uuid
            except FileNotFoundError as F:
                print(str(F))
            except Exception as F:
                print(F)

    return project_dependencies
