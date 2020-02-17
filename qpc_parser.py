import os
import re
import qpc_hash
from qpc_reader import read_file, QPCBlock, QPCBlockBase
from qpc_args import args
from qpc_base import Platform, PlatformName, posix_path
from qpc_project import Project, ProjectPass, ProjectDefinition, ProjectGroup, replace_macros, replace_macros_list
import qpc_generator_handler
from enum import EnumMeta, Enum, auto

if args.time:
    from time import perf_counter


# unused, idk if this will ever be useful either
def replace_exact_macros(split_string, macros):
    for macro, macro_value in macros.items():
        for index, item in enumerate(split_string):
            if macro == item:
                split_string[index] = macro_value
    
    return split_string


def get_base_macros(platform: Enum) -> dict:
    # OS Specific Defines
    arg_macros = {}
    for macro in args.macros:
        arg_macros["$" + macro] = "1"
    
    # if platform in {Platforms.WIN32, Platforms.WIN64}:
    if platform == PlatformName.WINDOWS:
        return {
            "$WINDOWS": "1",
            "$_BIN_EXT": ".dll",
            # "$_DYNAMIC_LIB_EXT": ".dll",
            "$_STATICLIB_EXT": ".lib",
            "$_IMPLIB_EXT": ".lib",
            "$_APP_EXT": ".exe",
            # "$_EXE_EXT": ".exe",
            # "$_DBG_EXT": ".pdb",
            **arg_macros,
        }
    
    # elif platform in {Platforms.LINUX32, Platforms.LINUX64}:
    elif platform == PlatformName.LINUX:
        return {
            "$POSIX": "1",
            "$LINUX": "1",
            "$_BIN_EXT": ".so",
            "$_STATICLIB_EXT": ".a",
            "$_IMPLIB_EXT": ".so",
            "$_APP_EXT": "",
            # "$_DBG_EXT": ".dbg",
            **arg_macros,
        }
    
    # TODO: finish setting up MacOS stuff here
    elif platform == PlatformName.MACOS:
        return {
            "$POSIX": "1",
            "$MACOS": "1",
            "$_BIN_EXT": ".dylib",
            "$_STATICLIB_EXT": ".a",
            "$_IMPLIB_EXT": ".so",
            "$_APP_EXT": "",
            # "$_DBG_EXT": ".dbg",
        }


class BaseInfo:
    def __init__(self, base_file_path: str, platform: Enum):
        self.path = base_file_path
        self.platform = platform
        self.macros = get_base_macros(platform)

        if args.verbose:
            print()
            [print('Set Macro: {0} = "{1}"'.format(name, value)) for name, value in self.macros.items()]
        
        self.groups = {}
        self._projects = []
        self.dependency_dict = {}
        self.configurations = set()
        self.project_definitions = []
        
        self.project_hashes = {}
        self.project_dependencies = {}

    def add_macro(self, project_block: QPCBlock):
        self.macros["$" + project_block.values[0].upper()] = replace_macros(project_block.values[1], self.macros)
        
    def add_project(self, project: ProjectDefinition):
        self._projects.append(project)

    # get all the projects the user wants (this is probably the worst part in this whole project)
    def setup_projects(self):
        self.project_definitions = []
    
        unwanted_projects = {}
        for removed_item in args.remove:
            if removed_item in self.groups:
                for project in self.groups[removed_item].projects:
                    if project.name not in unwanted_projects:
                        unwanted_projects[project.name] = project
        
            else:
                for project in self._projects:
                    if project.name == removed_item:
                        unwanted_projects[project.name] = project
                        break
    
        # TODO: clean up this mess
        if args.add:
            for added_item in args.add:
                if added_item in self.groups:
                    if added_item not in args.remove:
                    
                        # TODO: move to another function
                        for project in self.groups[added_item].projects:
                            if project.name not in unwanted_projects:
                                for added_project in self.project_definitions:
                                    if added_project.name == project.name:
                                        break
                                else:
                                    self.project_definitions.append(project)
            
                else:
                    if added_item not in args.remove:
                        for project in self._projects:
                            if added_item == project.name:
                                for added_project in self.project_definitions:
                                    if added_project.name == project.name:
                                        break
                                else:
                                    self.project_definitions.append(project)
                                    continue
                    # else:
                    # print("hey this item doesn't exist: " + added_item)
        else:
            raise Exception("No base_settings were added to generate for")


class Parser:
    def __init__(self):
        self.counter = 0
        self.read_files = {}

    # TODO: bug discovered with this,
    #  if i include the groups before the base_settings, it won't add any base_settings
    # def parse_base_settings(self, base_file_path: str, output_type: str, platform: Enum) -> BaseInfo:
    def parse_base_info(self, base_file_path: str, platform: Enum) -> BaseInfo:
        info = BaseInfo(base_file_path, platform)
    
        if args.verbose:
            print("\nReading: " + args.base_file)
            
        base_file = self.read_file(base_file_path)
    
        if args.verbose:
            print("\nParsing: " + args.base_file)
        
        self._parse_base_info_include(info, base_file)
        info.setup_projects()
        return info
    
    def _parse_base_info_include(self, info: BaseInfo, base_file: QPCBlockBase) -> BaseInfo:
        for project_block in base_file:
        
            if not project_block.solve_condition(info.macros):
                continue
        
            if project_block.key == "project":
                project_def = ProjectDefinition(project_block.values[0])
            
                # could have values next to it as well now
                for script_path in project_block.values[1:]:
                    script_path = replace_macros(script_path, info.macros)
                    project_def.AddScript(script_path)
            
                for item in project_block.items:
                    if item.solve_condition(info.macros):
                        project_def.AddScript(replace_macros(item.key, info.macros))
            
                info.add_project(project_def)
        
            elif project_block.key == "group":
                for group in project_block.values:
                    # do we have a group with this name already?
                    project_group = info.groups[group] if group in info.groups else ProjectGroup(group)
                    self._parse_project_group_items(project_group, info, project_block, [])
                    info.groups[project_group.name] = project_group
        
            elif project_block.key == "macro":
                info.add_macro(project_block)
        
            elif project_block.key == "configurations":
                info.configurations.update(project_block.get_item_list_condition(info.macros))
        
            # very rushed thing that could of been done with macros tbh
            elif project_block.key == "dependency_paths":
                for dependency in project_block.items:
                    if dependency.values and dependency.solve_condition(info.macros):
                        info.dependency_dict[dependency.key] = dependency.values[0]
        
            elif project_block.key == "include":
                # "Ah shit, here we go again."
                file_path = os.path.normpath(replace_macros(project_block.values[0], info.macros))
            
                if args.verbose:
                    print("Reading: " + file_path)
            
                include_file = read_file(file_path)
            
                if args.verbose:
                    print("Parsing... ")
            
                self._parse_base_info_include(info, include_file)

            elif not args.hide_warnings:
                project_block.warning("Unknown Key: ")
    
        # return configurations, dependency_convert
    
        return info
    
    def _parse_project_group_items(self, project_group, settings: BaseInfo, project_block, folder_list: list):
        for item in project_block.items:
            if item.solve_condition(settings.macros):
                
                if item.key == "folder":
                    folder_list.append(item.values[0])
                    self._parse_project_group_items(project_group, settings, item, folder_list)
                    folder_list.remove(item.values[0])
                else:
                    for project in settings._projects:
                        if project.name == item.key:
                            project_group.AddProject(project.name, project.script_list, folder_list)
    
    def parse_project(self, project_script: str, settings: BaseInfo, platforms: list) -> Project:
        if args.time:
            start_time = perf_counter()
        else:
            print("Parsing: " + project_script)

        project_filename = os.path.split(project_script)[1]
        project_block = self.read_file(project_filename)

        project_name = os.path.splitext(project_filename)[0]
        project = Project(project_name, project_script, settings)
        
        for config in settings.configurations:
            for platform in platforms:
                project_pass = ProjectPass(project, config, platform)
                project_list = self._parse_project_pass(project_block, project_pass)
                project.add_parsed_project_pass(project_list)
                self.counter += 1
    
        if args.verbose:
            print("Parsed: " + project.get_display_name())

        if args.time:
            print(str(round(perf_counter() - start_time, 4)) + " - Parsed: " + project_script)
            
        return project
    
    def _parse_project_pass(self, project_file: QPCBlockBase, project: ProjectPass, indent: str = "") -> ProjectPass:
        for project_block in project_file:
            if project_block.solve_condition(project.macros):
            
                if project_block.key == "macro":
                    project.add_macro(*project.replace_macros_list(*project_block.values))
            
                elif project_block.key == "configuration":
                    self._parse_config(project_block, project)
            
                elif project_block.key == "files":
                    self._parse_files(project_block, project, [])
            
                elif project_block.key == "dependencies":
                    for block in project_block.items:
                        if block.key == "-":
                            project.remove_dependencies(*block.values)
                        else:
                            project.add_dependencies(block.key, *block.values)
            
                elif project_block.key == "include":
                    # Ah shit, here we go again.
                    include_path = project.replace_macros(project_block.values[0])
                    include_file = self._include_file(include_path, project, project_file.file_path, indent + "    ")
                    self._parse_project_pass(include_file, project, indent + "    ")
                    if args.verbose:
                        print(indent + "    " + "Finished Parsing")
            
                elif not args.hide_warnings:
                    project_block.warning("Unknown key: ")
        return project
    
    def _include_file(self, include_path: str, project: ProjectPass, project_path: str, indent: str) -> QPCBlockBase:
        project.hash_list[include_path] = qpc_hash.make_hash(include_path)
        include_file = self.read_file(include_path)
    
        if not include_file:
            raise FileNotFoundError(
                "File does not exist:\n\tScript: {0}\n\tFile: {1}".format(project_path, include_path))
    
        if args.verbose:
            print(indent + "Parsing: " + include_path)
    
        return include_file
    
    def _parse_files(self, files_block: QPCBlock, project: ProjectPass, folder_list: list) -> None:
        if files_block.solve_condition(project.macros):
            for block in files_block.items:
                if block.solve_condition(project.macros):
                
                    if block.key == "folder":
                        folder_list.append(block.values[0])
                        self._parse_files(block, project, folder_list)
                        folder_list.remove(block.values[0])
                    elif block.key == "-":
                        project.remove_file(block)
                    else:
                        project.add_file(folder_list, block)
                    
                        if block.items:
                            for file_path in block.get_list():
                                source_file = project.get_source_file(file_path)
                            
                                # TODO: set this to directly edit the configuration options
                                #  remove need to write out configuration {}
                                #  also this is messy
                            
                                for config_block in block.items:
                                    if config_block.solve_condition(project.macros):
                                    
                                        if config_block.key == "configuration":
                                            if not args.hide_warnings:
                                                config_block.warning("Legacy Source File compiler info syntax\n"
                                                                     "Remove \"configuration { compiler {\", "
                                                                     "no need for it anymore")
                                            for group_block in config_block.items:
                                            
                                                if group_block.key != "compiler":
                                                    group_block.error("Invalid Group, can only use compiler")
                                                    continue
                                            
                                                if group_block.solve_condition(project.macros):
                                                    for option_block in group_block.items:
                                                        if option_block.solve_condition(project.macros):
                                                            source_file.compiler.parse_option(project.macros,
                                                                                              option_block)
                                        else:
                                            # new, cleaner way, just assume it's compiler
                                            source_file.compiler.parse_option(project.macros, config_block)
    
    def get_parsed_projects(self) -> list:
        pass

    def read_file(self, script_path: str) -> QPCBlockBase:
        if script_path in self.read_files:
            return self.read_files[script_path]
        else:
            script = read_file(script_path)
            self.read_files[script_path] = script
            return script
    
    # awful
    @staticmethod
    def _parse_config(project_block: QPCBlock, project: ProjectPass) -> None:
        if project_block.solve_condition(project.macros):
            for group_block in project_block.items:
                if group_block.solve_condition(project.macros):
                    for option_block in group_block.items:
                        if option_block.solve_condition(project.macros):
                            project.config.parse_config_option(group_block, option_block)

