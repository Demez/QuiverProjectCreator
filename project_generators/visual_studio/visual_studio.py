import uuid
import os
import sys
import qpc_hash
from time import perf_counter
from typing import List, Dict
from qpc_args import args
from qpc_base import BaseProjectGenerator, Platform, Arch
from qpc_project import (PrecompiledHeader, ConfigType, Language, Standard,
                         ProjectContainer, ProjectPass, Compile, SourceFileCompile)
from qpc_parser import BaseInfo
from qpc_logging import warning, error, verbose, print_color, Color

try:
    import lxml.etree as et
    HAS_LXML = True
except ImportError:
    HAS_LXML = False
    # only do this on windows, even if running this on linux
    if os.name == "nt":
        print("VSTUDIO WARNING: lxml module not installed, falling back to standard library, this will be MUCH slower")
        print("------------------------------------------------------------------------")
    import xml.etree.ElementTree as et
    from xml.dom import minidom
    

def timer_diff(start_time: float) -> str:
    return str(round(perf_counter() - start_time, 4))


class VisualStudioGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("Visual Studio")
        self._add_platform(Platform.WINDOWS)
        self._add_architectures(Arch.I386, Arch.AMD64)
        self._set_project_folders(True)
        self._set_generate_master_file(True)
        self._set_macro("VSTUDIO")
        
        self.cpp_uuid = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"
        self.filter_uuid = "{2150E333-8FDC-42A3-9474-1A3956D46DE8}"
        self.proj_uuids = {}
        self.folder_uuids = {}
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
            print_color(Color.CYAN, "Creating: " + project.file_name + ".vcxproj")

        vcx_project, source_files, include_list, res_list, none_list = create_vcxproj(project, project_passes)
        write_project(project, out_dir, vcx_project, ".vcxproj")
        
        if args.time:
            print_color(Color.CYAN, timer_diff(start_time) + " - Created: " + project.file_name + ".vcxproj")
        
        if args.time:
            start_time = perf_counter()
        else:
            print_color(Color.CYAN, "Creating: " + project.file_name + ".vcxproj.filters")
            
        vcxproject_filters = create_vcxproj_filters(project, source_files, include_list, res_list, none_list)
        write_project(project, out_dir, vcxproject_filters, ".vcxproj.filters")

        if args.time:
            print_color(Color.CYAN, timer_diff(start_time) + " - Created: " + project.file_name + ".vcxproj.filters")
        
        if not self.has_debug_commands(project_passes):
            return
        
        if args.time:
            start_time = perf_counter()
        else:
            print_color(Color.CYAN, "Creating: " + project.file_name + ".vcxproj.user")
            
        vcxproject_user = create_vcxproj_user(project, project_passes)
        write_project(project, out_dir, vcxproject_user, ".vcxproj.user")

        if args.time:
            print_color(Color.CYAN, timer_diff(start_time) + " - Created: " + project.file_name + ".vcxproj.user")
        
        # return out_dir
        
    @staticmethod
    def has_debug_commands(project_passes: list) -> bool:
        for project in project_passes:
            if bool(project.cfg.debug):
                return True
        return False
    
    def does_project_exist(self, project_out_dir: str) -> bool:
        # base_path = self._get_base_path(project_out_dir)
        split_ext_path = os.path.splitext(project_out_dir)[0]
        if os.path.isfile(split_ext_path + ".vcxproj"):
            verbose(f"File Exists: {split_ext_path}.vcxproj")
            if os.path.isfile(split_ext_path + ".vcxproj.filters"):
                verbose(f"File Exists: {split_ext_path}.vcxproj.filters")
                return True
        return False
    
    def does_master_file_exist(self, master_file_path: str) -> bool:
        base_path, project_name = os.path.split(master_file_path)
        split_ext_path = os.path.splitext(master_file_path)[0]
        base_path += "/"
        return os.path.isfile(split_ext_path + ".sln")

    def get_master_file_path(self, master_file_path: str) -> str:
        return master_file_path + ".sln"
    
    def create_master_file(self, info: BaseInfo, master_file_path: str) -> None:
        print_color(Color.CYAN, "Creating Solution File: " + master_file_path)
    
        # slow?
        self.out_dir_dict = {}
        for qpc_path, hash_path in info.project_hashes.items():
            if qpc_path in info.project_dependencies:
                self.out_dir_dict[qpc_path] = qpc_hash.get_out_dir(hash_path)
                
        info_win = info.get_base_info(Platform.WINDOWS)
    
        with open(master_file_path, "w", encoding="utf-8") as self.solution_file:
            write_solution_header(self.solution_file)

            self.proj_uuids = {}  # project_name: uuid of project - client_hl2: {UUID}
            self.folder_uuids = {}  # folder_name: uuid of folder - Game/Audio: {UUID}

            [self.sln_project_def_loop(project_def, info, info_win) for project_def in info_win.projects]
        
            # Write the folders as projects to write their assigned uuid
            for full_folder, folder_uuid in self.folder_uuids.items():
                folder_name = os.path.basename(full_folder)
                sln_write_project_line(self.solution_file, folder_name, folder_name, self.filter_uuid, folder_uuid)
                self.solution_file.write("EndProject\n")
        
            # Write the global stuff
            self.solution_file.write("Global\n")
            
            config_plat_list = []
            for plat in self._platforms:
                for config in info.get_base_info(plat).configs:
                    for arch in self._architectures:
                        config_plat_list.append(config + "|" + convert_arch(arch))
        
            # SolutionConfigurationPlatforms
            sln_config_plat = {}
            for config_plat in config_plat_list:
                sln_config_plat[config_plat] = config_plat
        
            sln_write_section(self.solution_file, "SolutionConfigurationPlatforms", sln_config_plat, False)
        
            # ProjectConfigurationPlatforms
            proj_config_plat = {}
            for project_uuid in self.proj_uuids.values():
                for config_plat in config_plat_list:
                    proj_config_plat[project_uuid + "." + config_plat + ".ActiveCfg"] = config_plat
                    # TODO: maybe get some setting for a default project somehow, i think the default is set here
                    proj_config_plat[project_uuid + "." + config_plat + ".Build.0"] = config_plat
        
            sln_write_section(self.solution_file, "ProjectConfigurationPlatforms", proj_config_plat, True)
            
            uuid_assigns = {}
            for project_def in info_win.projects:
                if project_def.name not in self.proj_uuids:
                    continue
                
                # assign the project uuid to it's folder uuid
                full_folder = "/".join(info_win.project_folders[project_def.name])
                if full_folder in self.folder_uuids:
                    uuid_assigns[self.proj_uuids[project_def.name]] = self.folder_uuids[full_folder]
            
                # assign sub folders to their parent folders, if we have any sub folders that is
                i = len(info_win.project_folders[project_def.name])
                while i > 1:
                    path = "/".join(info_win.project_folders[project_def.name][:i])
                    
                    sub_folder_uuid = self.folder_uuids[path]
                    parent_uuid = self.folder_uuids[os.path.split(path)[0]]
                    
                    # if the folder was not assigned a parent folder, set it one here
                    if sub_folder_uuid not in uuid_assigns:
                        uuid_assigns[sub_folder_uuid] = parent_uuid
                        
                    i -= 1
        
            sln_write_section(self.solution_file, "NestedProjects", uuid_assigns, False)
            self.solution_file.write("EndGlobal\n")

    def sln_project_def_loop(self, project_def, info, info_win):
        for folder_list in info_win.project_folders.values():
            for index, folder in enumerate(folder_list):
                full_folder = "/".join(folder_list[:index + 1])
                if full_folder not in self.folder_uuids:
                    self.folder_uuids[full_folder] = make_uuid()
                    
        # should we have this run before adding the folders?
        # so if this project is in a unique folder and doesn't exist
        # the folder isn't added? right now, the folder is always added
        if project_def.path not in self.out_dir_dict:
            return
            
        out_dir = self.out_dir_dict[project_def.path]
        if out_dir is None:
            return
        
        # What we're doing here is parsing the vcxproj we created earlier
        # then grabbing the name and the UUID of it
        # tbh, what i should do is allow generators to write stuff in project hash files
        # though im not really sure how i should go about setting that up at the moment
        
        # Also, when generating a new vcxproj without creating a new solution file
        # I might need to grab the UUID from the solution if it exists and is in the solution
        # which does not sound like fun, and generators having access to qpc hashes could make that easy
        # just store the project's uuid in the hash file
            
        vcxproj_path = out_dir + "/" + os.path.splitext(os.path.basename(project_def.path))[0] + ".vcxproj"
        
        if not os.path.isfile(vcxproj_path):
            print("Project does not exist: " + vcxproj_path)
            return
        
        tree = et.parse(vcxproj_path)
        vcxproj = tree.getroot()
        
        project_name, project_uuid = get_name_and_uuid(vcxproj)
        self.proj_uuids[project_def.name] = project_uuid
        sln_write_project_line(self.solution_file, project_name, vcxproj_path, self.cpp_uuid, project_uuid)
        
        # TODO: add dependencies to the container class and then use that here
        #  and have a GetDependencies() function for if the hash check _passes
        # write any container dependencies
        uuid_deps = get_project_dependencies(info.project_hashes, info.project_dependencies[project_def.path])
        sln_write_section(self.solution_file, "ProjectDependencies", uuid_deps, True, True)
        
        self.solution_file.write("EndProject\n")


def convert_arch(arch: Arch) -> str:
    if arch == Arch.I386:
        return "Win32"
    elif arch == Arch.AMD64:
        return "x64"


def make_uuid():
    return f"{{{uuid.uuid4()}}}".upper()


def make_cfg_plat_cond(config: str, arch: Arch) -> str:
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
    
    all_sources = {}
    all_includes = {}
    all_resources = {}
    all_none_files = {}
    
    header_exts = {".h", ".hxx", ".hpp"}
    none_exts = {".rc", ".h", ".hxx", ".hpp"}
    
    # gather all files
    for project in project_passes:
        source_files = get_project_files(project.source_files)[0]
        all_sources = {**all_sources, **source_files}
        
        include_list, remaining_files = get_project_files(project.files, header_exts)
        all_includes = {**all_includes, **include_list}
        
        res_list, remaining_files = get_project_files(remaining_files, {".rc"})
        all_resources = {**all_resources, **res_list}
        
        none_list = get_project_files(remaining_files, invalid_exts=none_exts)[0]
        all_none_files = {**all_none_files, **none_list}
        
    # now add files
    create_file_item_groups(project_passes, vcxproj, all_sources, "ClCompile")
    create_file_item_groups(project_passes, vcxproj, all_includes, "ClInclude")
    create_file_item_groups(project_passes, vcxproj, all_resources, "ResourceCompile")
    create_file_item_groups(project_passes, vcxproj, all_none_files, "None")
    
    # other vstudio stuff idk
    et.SubElement(vcxproj, "Import").set("Project", "$(VCTargetsPath)\\Microsoft.Cpp.targets")
    et.SubElement(vcxproj, "ImportGroup").set("Label", "ExtensionTargets")
    
    return vcxproj, all_sources, all_includes, all_resources, all_none_files


def setup_project_configurations(vcxproj, project_passes: List[ProjectPass]):
    item_group = et.SubElement(vcxproj, "ItemGroup")
    item_group.set("Label", "ProjectConfigurations")
    
    for project in project_passes:
        project_configuration = et.SubElement(item_group, "ProjectConfiguration")
        project_configuration.set("Include", project.cfg_name + "|" + convert_arch(project.arch))
        
        et.SubElement(project_configuration, "Configuration").text = project.cfg_name
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


def setup_property_group_configurations(vcxproj, project_passes: List[ProjectPass]):
    for project in project_passes:
        property_group = et.SubElement(vcxproj, "PropertyGroup")
        property_group.set("Condition", make_cfg_plat_cond(project.cfg_name, project.arch))
        property_group.set("Label", "Configuration")
        
        cfg = project.cfg
        
        configuration_type = et.SubElement(property_group, "ConfigurationType")
        
        if cfg.general.config_type == ConfigType.APPLICATION:
            configuration_type.text = "Application"
        elif cfg.general.config_type == ConfigType.STATIC_LIB:
            configuration_type.text = "StaticLibrary"
        elif cfg.general.config_type == ConfigType.DYNAMIC_LIB:
            configuration_type.text = "DynamicLibrary"
        
        toolset = et.SubElement(property_group, "PlatformToolset")
        
        if cfg.general.compiler:
            if cfg.general.compiler in COMPILER_DICT:
                toolset.text = COMPILER_DICT[cfg.general.compiler]
            else:
                toolset.text = cfg.general.compiler
        else:
            toolset.text = COMPILER_DICT["msvc"]

        character_set = check_char_set(cfg.compile.defines.copy())
        if character_set:
            et.SubElement(property_group, "CharacterSet").text = character_set
        
        # "TargetName",
        # "WholeProgramOptimization",
        
        
def check_char_set(defs: List[str]) -> str:
    if "MBCS" in defs or "_MBCS" in defs:
        if "MBCS" in defs:
            defs.remove("MBCS")
        if "_MBCS" in defs:
            defs.remove("_MBCS")
        return "MultiByte"
    
    elif "UNICODE" in defs or "_UNICODE" in defs:
        if "UNICODE" in defs:
            defs.remove("UNICODE")
        if "_UNICODE" in defs:
            defs.remove("_UNICODE")
        return "Unicode"


def setup_property_sheets(vcxproj):
    import_group = et.SubElement(vcxproj, "ImportGroup")
    import_group.set("Label", "PropertySheets")
    
    elem_import = et.SubElement(import_group, "Import")
    elem_import.set("Project", "$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props")
    elem_import.set("Condition", "exists('$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props')")
    elem_import.set("Label", "LocalAppDataPlatform")


def setup_general_properties(vcxproj, project_passes: List[ProjectPass]):
    property_group = et.SubElement(vcxproj, "PropertyGroup")
    et.SubElement(property_group, "_ProjectFileVersion").text = "10.0.30319.1"
    
    for project in project_passes:
        condition = make_cfg_plat_cond(project.cfg_name, project.arch)
        cfg = project.cfg
        
        property_group = et.SubElement(vcxproj, "PropertyGroup")
        property_group.set("Condition", condition)
        
        out_dir = et.SubElement(property_group, "OutDir")
        out_dir.text = cfg.general.out_dir + os.sep
        
        int_dir = et.SubElement(property_group, "IntDir")
        int_dir.text = cfg.general.build_dir + os.sep
        
        et.SubElement(property_group, "TargetName").text = cfg.general.out_name
        
        include_paths = et.SubElement(property_group, "IncludePath")
        include_paths.text = ';'.join(cfg.compile.inc_dirs)
        
        if cfg.compile.default_inc_dirs:
            include_paths.text += ";$(IncludePath)"
        
        library_paths = et.SubElement(property_group, "LibraryPath")
        library_paths.text = ';'.join(cfg.link.lib_dirs)
        
        if cfg.link.default_lib_dirs:
            library_paths.text += ";$(LibraryPath)"

        # also why does WholeProgramOptimization go here and in ClCompile


def setup_item_definition_groups(vcxproj: et.Element, project_passes: List[ProjectPass]):
    for project in project_passes:
        condition = make_cfg_plat_cond(project.cfg_name, project.arch)
        cfg = project.cfg
        
        item_def_group = et.SubElement(vcxproj, "ItemDefinitionGroup")
        item_def_group.set("Condition", condition)
        
        # ------------------------------------------------------------------
        # compile - ClCompile
        add_compiler_options(et.SubElement(item_def_group, "ClCompile"), cfg.compile, cfg.general)
        
        # ------------------------------------------------------------------
        # linker - Link or Lib
        if cfg.general.config_type == ConfigType.STATIC_LIB:
            link_lib = et.SubElement(item_def_group, "Lib")
        else:
            link_lib = et.SubElement(item_def_group, "Link")

        if cfg.link.options:
            # copying here so we don't remove from the project object, would break for the next project type
            remaining_options = [*cfg.link.options]
    
            index = 0
            # for index, option in enumerate(compile.options):
            while len(remaining_options) > index:
                option = remaining_options[index]
                option_key, option_value = command_to_link_option(option)
                if option_key and option_value:
                    et.SubElement(link_lib, option_key).text = option_value
                    remaining_options.remove(option)
                else:
                    index += 1
    
            # now add any unchanged options
            et.SubElement(link_lib, "AdditionalOptions").text = ' '.join(remaining_options)
        
        libs = [lib if lib.endswith(".lib") else lib + ".lib" for lib in cfg.link.libs]
        et.SubElement(link_lib, "AdditionalDependencies").text = ';'.join(libs) + ";%(AdditionalDependencies)"

        if cfg.link.output_file:
            et.SubElement(link_lib, "OutputFile").text = cfg.link.output_file

        if cfg.link.debug_file:
            et.SubElement(link_lib, "ProgramDatabaseFile").text = os.path.splitext(cfg.link.debug_file)[0] + ".pdb"
        
        if cfg.link.import_lib:
            et.SubElement(link_lib, "ImportLibrary").text = cfg.link.import_lib

        if cfg.link.entry_point:
            et.SubElement(link_lib, "EntryPointSymbol").text = cfg.link.entry_point
        
        # what does "IgnoreAllDefaultLibraries" do differently than this? is it a boolean? idk
        et.SubElement(link_lib, "IgnoreSpecificDefaultLibraries").text = ';'.join(cfg.link.ignore_libs) + \
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
            
            
PRECOMPILED_HEADER_DICT = {
    PrecompiledHeader.NONE: "NotUsing",
    PrecompiledHeader.USE: "Use",
    PrecompiledHeader.CREATE: "Create"
}


def add_compiler_options(compiler_elem: et.SubElement, compile: Compile, general=None):
    added_option = False
    
    if type(compile) == SourceFileCompile and not compile.build:
        added_option = True
        et.SubElement(compiler_elem, "ExcludedFromBuild").text = str(not compile.build).lower()
    
    if compile.defines:
        added_option = True
        preprocessor_definitions = et.SubElement(compiler_elem, "PreprocessorDefinitions")
        preprocessor_definitions.text = ';'.join(compile.defines) + ";%(PreprocessorDefinitions)"
    
    if compile.pch:
        added_option = True
        et.SubElement(compiler_elem, "PrecompiledHeader").text = PRECOMPILED_HEADER_DICT[compile.pch]
    
    if compile.pch_file:
        added_option = True
        et.SubElement(compiler_elem, "PrecompiledHeaderFile").text = compile.pch_file
    
    if compile.pch_out:
        added_option = True
        et.SubElement(compiler_elem, "PrecompiledHeaderOutputFile").text = compile.pch_out

    # these are needed, because for some reason visual studio use shit stuff for default info
    if general:  # basically if not file
        added_option = True
        
        if general.language:
            if general.language == Language.CPP:
                et.SubElement(compiler_elem, "CompileAs").text = "CompileAsCpp"
            else:
                et.SubElement(compiler_elem, "CompileAs").text = "CompileAsC"
        
        if general.standard:
            standard = "stdcpplatest" if general.standard == Standard.CPP20 else f"std{general.standard.name.lower()}"
            et.SubElement(compiler_elem, "LanguageStandard").text = standard
    
    if compile.options:
        added_option = True
        warnings_list = []
        # copying here so we don't remove from the project object, would break for the next project type
        remaining_options = [*compile.options]

        index = 0
        # for index, option in enumerate(compile.options):
        while len(remaining_options) > index:
            option = remaining_options[index]
            if option.startswith("/ignore:"):
                warnings_list.append(option[8:])
                remaining_options.remove(option)
            else:
                option_key, option_value = command_to_compiler_option(option)
                if option_key and option_value:
                    et.SubElement(compiler_elem, option_key).text = option_value
                    remaining_options.remove(option)
                else:
                    index += 1
        
        if warnings_list:
            disable_warnings = et.SubElement(compiler_elem, "DisableSpecificWarnings")
            disable_warnings.text = ';'.join(warnings_list)
        
        # now add any unchanged options
        et.SubElement(compiler_elem, "AdditionalOptions").text = ' '.join(remaining_options)
    
    return added_option


COMPILER_OPTIONS = {
    # GENERAL PANEL
    "DebugInformationFormat": {
        "/Zi": "ProgramDatabase",
        "/ZI": "EditAndContinue",
        "/Z7": "OldStyle",
    },
    
    "SupportJustMyCode":            {"/JMC": "true"},
    
    "CompileAsManaged": {
        "/clr": "true",
        "/clr:safe": "Safe",
        "/clr:pure": "Pure",
    },
    
    "CompileAsWinRT":               {"/ZW": "true"},
    
    "SuppressStartupBanner": {
        # we don't have a way to turn this off, actually, because nologo is the default...
        "/nologo": "true",
        # ... so let's make a hack with a nonexistant switch.
        "/logo": "false",
    },
    "WarningLevel": {
        "/W0": "TurnOffAllWarnings",
        "/W1": "Level1", "/W2": "Level2", "/W3": "Level3", "/W4": "Level4",
        "/Wall": "EnableAllWarnings",
    },
    "TreatWarningAsError": {
        "/WX-": "false",
        "/WX": "true",
    },
    "DiagnosticsFormat": {
        "/diagnostics:caret": "Caret",
        "/diagnostics:column": "Column",
        "/diagnostics:classic": "Classic",
    },
    
    "SDLCheck":                     {"/sdl-": "false", "/sdl": "true"},
    "MultiProcessorCompilation":    {"/MP": "true"},

    # OPTIMIZATION PANEL
    "Optimization": {
        "/Od": "Disabled",
        "/O1": "MinSpace",
        "/O2": "MaxSpeed",
        "/Ox": "Full"
    },
    "InlineFunctionExpansion": {
        "/Ob0": "Disabled",
        "/Ob1": "OnlyExplicitInline",
        "/Ob2": "AnySuitable",
    },
    "IntrinsicFunctions":           {"/Oi": "true"},
    "FavorSizeOrSpeed":             {"/Os": "Size", "/Ot": "Speed"},
    "OmitFramePointers":            {"/Oy-": "false", "/Oy": "true"},
    "EnableFiberSafeOptimizations": {"/GT": "true"},
    "WholeProgramOptimization":     {"/GL": "true"},  # also goes in Configuration PropertyGroup? tf

    # PREPROCESSOR PANEL
    "UndefineAllPreprocessorDefinitions": {"/u": "true"}, # who would. EVER. use this????
    "IgnoreStandardIncludePath":    {"/X": "true"},
    "PreprocessToFile":             {"/P": "true"},
    "PreprocessSuppressLineNumbers": {"/EP": "true"},
    "PreprocessKeepComments":       {"/C": "true"},

    # CODE GENERATION PANEL
    "StringPooling":                {"/GF-": "false", "/GF": "true"},
    "MinimalRebuild":               {"/Gm-": "false", "/Gm": "true"},
    "ExceptionHandling": {
        "/EHa": "Async",
        "/EHsc": "Sync",
        "/EHs": "SyncCThrow",
        "": "false"
    },
    "SmallerTypeCheck":             {"/RTCc": "true"},
    "BasicRuntimeChecks": {
        "/RTCs": "StackFrameRuntimeCheck",
        "/RTCu": "UninitializedLocalUsageCheck",
        "/RTC1": "EnableFastChecks", # synonyms
        "/RTCsu": "EnableFastChecks", # synonyms
        "": "Default"
    },
    "RuntimeLibrary": {
        "/MT": "MultiThreaded",
        "/MTd": "MultiThreadedDebug",
        "/MD": "MultiThreadedDLL",
        "/MDd": "MultiThreadedDebugDLL",
    },
    "StructMemberAlignment": {
        "/Zp1": "1Byte",
        "/Zp2": "2Bytes",
        "/Zp4": "4Bytes",
        "/Zp8": "8Bytes",
        "/Zp16": "16Bytes",
    },
    "BufferSecurityCheck":          {"/GS-": "false", "/GS": "true"},
    "ControlFlowGuard":             {"/guard:cf": "Guard"},
    "FunctionLevelLinking":         {"/Gy-": "false", "/Gy": "true"},
    "EnableParallelCodeGeneration": {"/Qpar-": "false", "/Qpar": "true"},
    "EnableEnhancedInstructionSet": {
        "/arch:SSE": "StreamingSIMDExtensions",
        "/arch:SSE2": "StreamingSIMDExtensions2",
        "/arch:AVX": "AdvancedVectorExtensions",
        "/arch:AVX2": "StreamingSIMDExtensions2",
        "/arch:IA32": "NoExtensions"
    },
    "FloatingPointModel": {
        "/fp:precise": "Precise",
        "/fp:strict": "Strict",
        "/fp:fast": "Fast"
    },
    "FloatingPointExceptions":      {"/fp:except-": "false", "/fp:except": "true"},
    "CreateHotpatchableImage":      {"/hotpatch": "true"},
    "SpectreMitigation":            {"/Qspectre": "Spectre"}, # NOTE!!!! this goes in the PROPERTYGROUP section in the project!!!

    # LANGUAGE PANEL
    "DisableLanguageExtensions":    {"/Za": "true"},
    "ConformanceMode":              {"/permissive-": "true", "": "false"},
    "TreatWChar_tAsBuiltInType":    {"/Zc:wchar_t-": "false", "/Zc:wchar_t": "true"},
    "ForceConformanceInForLoopScope": {"/Zc:forScope-": "false", "/Zc:forScope": "true"},
    "RemoveUnreferencedCodeData":   {"/Zc:inline-": "false", "/Zc:inline": "true"}, # another hack to disable this, since adding the option is the default and there's no actual inline-
    "EnforceTypeConversionRules":   {"/Zc:rvalueCast-": "false", "/Zc:rvalueCast": "true"},
    "RuntimeTypeInfo":              {"/GR-": "false", "/GR": "true"},
    "OpenMPSupport":                {"/openmp-": "false", "/openmp": "true"},
        # language standard is handled by QPC
    "EnableModules":                {"/experimental:module": "true"},
    
    
    
    # PRECOMPILED HEADERS are handled seperately by QPC builtins

    # OUTPUT FILES PANEL
        # note: we also need to support file paths for this stuff eventually... right now they just use IntDir
    "ExpandAttributedSource":       {"/Fx": "true"},
    "AssemblerOutput": {
        "/FA": "AssemblyCode",
        "/FAc": "AssemblyAndMachineCode",
        "/FAs": "AssemblyAndSourceCode",
        "/FAcs": "All"
    },
    "UseUnicodeForAssemblerListing": {"/FAu": "true"},
    "GenerateXMLDocumentationFiles": {"/doc": "true"},

    # BROWSE INFORMATION PANEL
        # note: we also need to support file paths for this stuff eventually... right now they just use IntDir
    "BrowseInformation":            {"/FR": "true"},

    # ADVANCED PANEL
    "CallingConvention": {
        "/Gd": "Cdecl", # the default
        "/Gr": "FastCall",
        "/Gz": "StdCall",
        "/Gv": "VectorCall"
    },
        # Compile As is handled by QPC
    "ShowIncludes":                 {"/showincludes": "true"},
    "UseFullPaths":                 {"/FC-": "false", "/FC": "true"}, # /FC- is another nonexistant hack
    "OmitDefaultLibName":           {"/ZI": "true"},
    "ErrorReporting": {
        "/errorReport:none": "None",
        "/errorReport:prompt": "Prompt",
        "/errorReport:queue": "Queue",
        "/errorReport:send": "Send"
    }
}


LINK_OPTIONS = {
    "TargetMachine": {
        "/MACHINE:ARM":         "MachineARM",
        "/MACHINE:EBC":         "MachineEBC",
        "/MACHINE:IA64":        "MachineIA64",
        "/MACHINE:MIPS":        "MachineIA64",
        "/MACHINE:MIPS16":      "MachineMIPS16",
        "/MACHINE:MIPSFPU":     "MachineMIPSFPU",
        "/MACHINE:MIPSFPU16":   "MachineMIPSFPU16",
        "/MACHINE:SH4":         "MachineSH4",
        "/MACHINE:THUMB":       "MachineTHUMB",
        "/MACHINE:X64":         "MachineX64",
        "/MACHINE:X86":         "MachineX86",
    },
    "ShowProgress": {
        "/VERBOSE":         "LinkVerbose",
        "/VERBOSE:Lib":     "LinkVerboseLib",
        "/VERBOSE:ICF":     "LinkVerboseICF",
        "/VERBOSE:REF":     "LinkVerboseREF",
        "/VERBOSE:SAFESEH": "LinkVerboseSAFESEH",
        "/VERBOSE:CLR":     "LinkVerboseCLR",
    },
    "ForceFileOutput": {
        "/FORCE":               "Enabled",
        "/FORCE:MULTIPLE":      "MultiplyDefinedSymbolOnly",
        "/FORCE:UNRESOLVED":    "UndefinedSymbolOnly",
    },
    "CreateHotPatchableImage": {
        "/FUNCTIONPADMIN":      "Enabled",
        "/FUNCTIONPADMIN:5":    "X86Image",
        "/FUNCTIONPADMIN:6":    "X64Image",
        "/FUNCTIONPADMIN:16":   "ItaniumImage",
    },
    "SubSystem": {
        "/SUBSYSTEM:CONSOLE":                   "Console",
        "/SUBSYSTEM:WINDOWS":                   "Windows",
        "/SUBSYSTEM:NATIVE":                    "Native",
        "/SUBSYSTEM:EFI_APPLICATION":           "EFI Application",
        "/SUBSYSTEM:EFI_BOOT_SERVICE_DRIVER":   "EFI Boot Service Driver",
        "/SUBSYSTEM:EFI_ROM":                   "EFI ROM",
        "/SUBSYSTEM:EFI_RUNTIME_DRIVER":        "EFI Runtime",
        "/SUBSYSTEM:WINDOWSCE":                 "WindowsCE",
        "/SUBSYSTEM:POSIX":                     "POSIX",
    },
    "LinkTimeCodeGeneration": {
        "/ltcg":                "UseLinkTimeCodeGeneration",
        "/ltcg:pginstrument":   "PGInstrument",
        "/ltcg:pgoptimize":     "PGOptimization",
        "/ltcg:pgupdate":       "PGUpdate",
    },
    "CLRThreadAttribute": {
        "/CLRTHREADATTRIBUTE:NONE": "DefaultThreadingAttribute",
        "/CLRTHREADATTRIBUTE:MTA":  "MTAThreadingAttribute",
        "/CLRTHREADATTRIBUTE:STA":  "STAThreadingAttribute",
    },
    "CLRImageType": {
        "/CLRIMAGETYPE:IJW":    "ForceIJWImage",
        "/CLRIMAGETYPE:PURE":   "ForcePureILImage",
        "/CLRIMAGETYPE:SAFE":   "ForceSafeILImage",
    },
    "LinkErrorReporting": {
        "/ERRORREPORT:PROMPT":  "PromptImmediately",
        "/ERRORREPORT:QUEUE":   "QueueForNextLogin",
        "/ERRORREPORT:SEND":    "SendErrorReport",
        "/ERRORREPORT:NONE":    "NoErrorReport",
    },
    "CLRSupportLastError": {
        "/CLRSupportLastError":             "Enabled",
        "/CLRSupportLastError:NO":          "Disabled",
        "/CLRSupportLastError:SYSTEMDLL":   "SystemDlls",
    },
    "AssemblyDebug": {
        "/ASSEMBLYDEBUG:DISABLE":   "false",
        "/ASSEMBLYDEBUG":           "true",
    },
    "LargeAddressAware": {
        "/LARGEADDRESSAWARE:NO":    "false",
        "/LARGEADDRESSAWARE":       "true",
    },
    "FixedBaseAddress": {
        "/FIXED:NO":    "false",
        "/FIXED":       "true",
    },
    "OptimizeReferences": {
        "/OPT:NOREF":   "false",
        "/OPT:REF":     "true",
    },
    "EnableCOMDATFolding": {
        "/OPT:NOICF":   "false",
        "/OPT:ICF":     "true",
    },
}


def command_to_option(option_dict: dict, value: str) -> tuple:
    for compiler_key, value_commands in option_dict.items():
        if value in value_commands:
            return compiler_key, value_commands[value]
    return None, None


def command_to_compiler_option(value: str) -> tuple:
    return command_to_option(COMPILER_OPTIONS, value)


def command_to_link_option(value: str) -> tuple:
    return command_to_option(LINK_OPTIONS, value)


# blech
def create_file_item_groups(passes: List[ProjectPass], parent_elem: et.Element, file_dict: dict, file_type: str):
    if not file_dict:
        return
    
    item_group = et.SubElement(parent_elem, "ItemGroup")
    for file_path in file_dict:
        elem_file = et.SubElement(item_group, file_type)
        elem_file.set("Include", file_path)

        for project in passes:
            project_files = project.source_files if file_type == "ClCompile" else project.files
            condition = make_cfg_plat_cond(project.cfg_name, project.arch)
            if file_path not in project_files:
                exclude_elem = et.SubElement(elem_file, "ExcludedFromBuild")
                exclude_elem.text = "true"
                exclude_elem.set("Condition", condition)
                    
            elif file_type == "ClCompile":
                item_group_compiler_options(elem_file, project, file_path)
                
        # clean the option conditions in the worst possible way
        # create a dictionary where the the values is a list of all elements with that tag
        option_elem_dict: Dict[str, List[et.Element]] = {}
        for elem in elem_file:
            if elem.tag not in option_elem_dict:
                option_elem_dict[elem.tag]: List[et.Element] = []
            option_elem_dict[elem.tag].append(elem)
            
        for option, elem_list in option_elem_dict.items():
            # check to see if we have an option for every possible config
            if len(elem_list) == len(passes):
                value = elem_list[0].text
                for elem in elem_list[1:]:
                    # if the value is different across configs, skip to the next option
                    if elem.text != value:
                        break
                else:
                    # all values of each option are the same
                    # so remove all elements after the first one
                    for elem in elem_list[1:]:
                        elem.getparent().remove(elem)
                    # then remove the condition attribute that was added earlier
                    del elem_list[0].attrib["Condition"]
                
                
def item_group_compiler_options(elem_file: et.Element, project: ProjectPass, file_path: str):
    prev_elements = [element for element in elem_file]
    add_compiler_options(elem_file, project.source_files[file_path].compiler)
    condition = make_cfg_plat_cond(project.cfg_name, project.arch)
    for element in elem_file:
        if element in prev_elements:
            continue
        element.set("Condition", condition)


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


def create_vcxproj_filters(project_list: ProjectContainer, source_files: Dict[str, SourceFileCompile],
                           include_list: dict, res_list: dict, none_list: dict) -> et.Element:
    proj_filters = et.Element("Project")
    proj_filters.set("ToolsVersion", "4.0")
    proj_filters.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")
    
    create_folder_filters(proj_filters, project_list)
    
    create_source_file_item_group_filters(proj_filters, source_files, "ClCompile")
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
        project_file.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
        project_file.write(xml_to_string(xml_file))


def xml_to_string(elem) -> str:
    if HAS_LXML:
        return et.tostring(elem, pretty_print=True).decode("utf-8")
    else:
        # this is ugly and slow,
        # i could probably implement some indenting myself for this later and use tostringlist instead
        raw_string = et.tostring(elem, "utf-8")
        reparsed = minidom.parseString(raw_string)
        return reparsed.toprettyxml(indent="  ")


# --------------------------------------------------------------------------------------------------


def create_vcxproj_user(project: ProjectContainer, project_passes: List[ProjectPass]) -> et.Element:
    file_path = os.path.splitext(project.file_name)[0] + ".vcxproj.user"
    if os.path.isfile(file_path):
        vcxproj = et.parse(file_path).getroot()
    else:
        vcxproj = et.Element("Project")
        vcxproj.set("ToolsVersion", "Current")
        vcxproj.set("xmlns", "http://schemas.microsoft.com/developer/msbuild/2003")
    
    for project_pass in project_passes:
        condition = make_cfg_plat_cond(project_pass.cfg_name, project_pass.arch)
        create_debug_group(vcxproj, project_pass.cfg.debug, condition)
    
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
    
    # configs = []
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
