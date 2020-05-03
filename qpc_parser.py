import os
import glob
import qpc_hash
from qpc_reader import read_file, QPCBlock, QPCBlockBase
from qpc_args import args, get_arg_macros
from qpc_base import Platform, Arch, check_file_path_glob
from qpc_project import ProjectContainer, ProjectPass, ProjectDefinition, ProjectGroup, BuildEvent, \
                        replace_macros, replace_macros_list
from enum import Enum
from time import perf_counter


# unused, idk if this will ever be useful either
def replace_exact_macros(split_string, macros):
    for macro, macro_value in macros.items():
        for index, item in enumerate(split_string):
            if macro == item:
                split_string[index] = macro_value
    
    return split_string


def get_platform_macros(platform: Enum) -> dict:
    # OS Specific Defines
    if platform == Platform.WINDOWS:
        return {
            "$WINDOWS": "1",
            "$_BIN_EXT": ".dll",
            # "$_DYNAMIC_LIB_EXT": ".dll",
            "$_STATICLIB_EXT": ".lib",
            "$_IMPLIB_EXT": ".lib",
            "$_APP_EXT": ".exe",
            # "$_EXE_EXT": ".exe",
            # "$_DBG_EXT": ".pdb",
        }
    
    elif platform == Platform.LINUX:
        return {
            "$POSIX": "1",
            "$LINUX": "1",
            "$_BIN_EXT": ".so",
            "$_STATICLIB_EXT": ".a",
            "$_IMPLIB_EXT": ".so",
            "$_APP_EXT": "",
            # "$_DBG_EXT": ".dbg",
        }
    
    # TODO: finish setting up MacOS stuff here
    elif platform == Platform.MACOS:
        return {
            "$POSIX": "1",
            "$MACOS": "1",
            "$_BIN_EXT": ".dylib",
            "$_STATICLIB_EXT": ".a",
            "$_IMPLIB_EXT": ".so",
            "$_APP_EXT": "",
            # "$_DBG_EXT": ".dbg",
        }


class BaseInfoPlatform:
    def __init__(self, base_info, platform: Enum):
        self.shared = base_info
        self.platform = platform
        self.macros = {**get_arg_macros(), **get_platform_macros(platform)}
        
        if args.verbose:
            print()
            [print('Set Macro: {0} = "{1}"'.format(name, value)) for name, value in self.macros.items()]
        
        self._projects_all = []
        # self._projects_undefined = {}
        
        # this stores all everything in dependency_paths in a base file
        # and also has path fixes on it if used with a include with a path to change to
        self.dependency_dict = {}
        # if any path was modified above, then it's also added here with the original path
        self.dependency_dict_original = {}
        
        # for generators and parts of qpc to use:
        self.configurations = []
        self.projects = []
        
        self.project_dependencies = {}

    def add_project(self, project_name: str, *project_paths) -> None:
        # TODO: check if script path is already used
        project_def = self.shared.add_project(project_name)
        project_def.platforms.add(self.platform)
    
        for script_path in project_paths:
            script_path = replace_macros(script_path, self.macros)
            if not project_def.add_script(script_path) and not args.hide_warnings:
                print("Script does not exist: " + script_path)

        project_def.update_groups()
        self._projects_all.append(project_def)
        
    def add_project_to_group(self, project_name: str, project_group: ProjectGroup, folder_list: list):
        project_def = self.get_project(project_name)
        if project_def:
            if not project_def.folder_list:
                project_def.folder_list = tuple(folder_list)
            project_group.project_defined(project_def)
        else:
            project_def = ProjectDefinition(project_name, *folder_list)
            self._projects_all.append(project_def)
        project_def.add_group(project_group)
        
    def init_args(self):
        for project_path in args.add:
            if check_file_path_glob(project_path):
                for found_file in glob.glob(project_path):
                    self.add_project(os.path.splitext(os.path.basename(found_file))[0], found_file)
            elif os.path.isfile(project_path):
                self.add_project(os.path.splitext(os.path.basename(project_path))[0], project_path)
            elif not self.is_project_added(project_path) and project_path not in self.shared.groups:
                print("Project, Group, or File does not exist: " + project_path)

        if not self.configurations:
            self.configurations.append("Default")

    def add_macro(self, project_block: QPCBlock):
        self.macros["$" + project_block.values[0]] = replace_macros(project_block.values[1], self.macros)

    def is_project_script_added(self, project_path: str) -> bool:
        return bool(self.get_project_by_script(project_path))

    def is_project_added(self, project_name: str) -> bool:
        return bool(self.get_project_by_script(project_name))

    def get_project_by_script(self, project_path: str) -> ProjectDefinition:
        for project in self._projects_all:
            if project_path in project.script_list:
                return project

    def get_project_by_name(self, project_name: str) -> ProjectDefinition:
        for project in self._projects_all:
            if project.name == project_name:
                return project

    def get_project(self, project_name: str) -> ProjectDefinition:
        for project in self._projects_all:
            if project.name == project_name or project_name in project.script_list:
                return project
            
    def get_dependency_path(self, key: str):
        if key in self.dependency_dict_original:
            return self.dependency_dict[self.dependency_dict_original[key]]
        elif key in self.dependency_dict:
            return self.dependency_dict[key]
        return key

    def _use_project(self, project: ProjectDefinition, unwanted_projects: dict):
        if self.platform in project.platforms and project.name not in unwanted_projects:
            for added_project in self.projects:
                if added_project.name == project.name:
                    break
            else:
                self.projects.append(project)
        
    # get all the _passes the user wants (this is probably the worst part in this whole project)
    def setup_wanted_projects(self, add_list: list, remove_list: list, unwanted_projects: dict) -> None:
        self.projects = []

        for removed_item in remove_list:
            if removed_item in self.shared.groups:
                for project in self.shared.groups[removed_item].projects:
                    if project.name not in unwanted_projects:
                        unwanted_projects[project.name] = project
            
            elif removed_item in self.shared.projects_all:
                if self.shared.projects_all[removed_item] in self._projects_all:
                    unwanted_projects[removed_item] = self.shared.projects_all[removed_item]
            else:
                for project in self._projects_all:
                    if removed_item in project.script_list:
                        unwanted_projects[project.name] = project
                        break
                else:
                    print("Project, Group, or Script does not exist: " + removed_item)
        
        # TODO: clean up this mess
        if add_list:
            for added_item in add_list:
                if added_item in self.shared.groups:
                    for project in self.shared.groups[added_item].projects:
                        self._use_project(project, unwanted_projects)
                        
                elif added_item in self.shared.projects_all:
                    if self.shared.projects_all[added_item] in self._projects_all:
                        self._use_project(self.shared.projects_all[added_item], unwanted_projects)
                else:
                    for project in self._projects_all:
                        if added_item in project.script_list:
                            self._use_project(project, unwanted_projects)
                            break
                    else:
                        print("Project, Group, or Script does not exist: " + added_item)
        else:
            raise Exception("No projects were added to generate for")


class BaseInfo:
    def __init__(self):
        self.projects_all = {}
        self.projects = {}  # maybe remove?
        self.groups = {}
        # maybe add something for archs?
        self.info_list = [BaseInfoPlatform(self, platform) for platform in args.platforms]
        
        self.project_hashes = {}
        self.project_dependencies = {}
        
    def finish_parsing(self):
        [info_plat.init_args() for info_plat in self.info_list]
        self._prepare_projects()

    # this probably shouldn't be used, use below instead and rename to this
    def _prepare_projects(self) -> tuple:
        self.projects = {}  # dict keeps order, set doesn't as of 3.8, both faster than lists

        unwanted_projects = {}
        remove_list = []
        add_list = []
        
        def add_item(item_list: list, _item: str):
            if check_file_path_glob(_item):
                item_list.extend(glob.glob(_item))
            else:
                item_list.append(_item)

        [add_item(add_list, item) for item in args.add]
        [add_item(remove_list, item) for item in args.remove]
        [add_list.remove(item) for item in remove_list if item in add_list]
        
        for base_info in self.info_list:
            base_info.setup_wanted_projects(add_list, remove_list, unwanted_projects.copy())
            for project in base_info.projects:
                if project not in self.projects:
                    self.projects[project] = None
        self.projects = tuple(self.projects.keys())
        return self.projects
    
    def add_project(self, project_name: str) -> ProjectDefinition:
        if project_name in self.projects_all:
            project_def = self.projects_all[project_name]
        else:
            project_def = ProjectDefinition(project_name)
            self.projects_all[project_name] = project_def
        return project_def

    def get_base_info(self, platform: Platform) -> BaseInfoPlatform:
        if platform in Platform:
            for base_info in self.info_list:
                if base_info.platform == platform:
                    return base_info

    def get_configs(self) -> list:
        configurations = set()
        [configurations.update(info.configurations) for info in self.info_list]
        return list(configurations)
    
    def get_projects(self, *platforms) -> tuple:
        project_list = {}  # dict keeps order, set doesn't as of 3.8, both faster than lists
        for base_info in self.info_list:
            if base_info.platform not in platforms:
                continue
            for project in base_info.projects:
                if project not in project_list:
                    project_list[project] = None
        project_list = tuple(project_list.keys())
        return project_list
    
    def add_project_dependencies(self, project_script: str, dependencies: list):
        self.project_dependencies[project_script] = dependencies  # might remove
        for base_info in self.info_list:
            # if base_info.platform in args.platforms:  # what is this needed for again?
            base_info.project_dependencies[project_script] = dependencies
    
    def get_project_dependencies(self, *platforms) -> dict:
        all_dependencies = {}
        for base_info in self.info_list:
            if base_info.platform in platforms:
                all_dependencies.update(base_info.project_dependencies)
        return all_dependencies
    
    def get_hashes(self, *platforms) -> dict:
        all_hashes = {}
        for base_info in self.info_list:
            if base_info.platform in platforms:
                for project in base_info.projects:
                    for script in project.script_list:
                        if script in self.project_hashes:
                            all_hashes[script] = self.project_hashes[script]
        return all_hashes


class Parser:
    def __init__(self):
        self.counter = 0
        self.read_files = {}

    # TODO: bug discovered with this,
    #  if i include the groups before the base_info, it won't add any base_info
    # def parse_base_settings(self, base_file_path: str, output_type: str, platform: Enum) -> BaseInfo:
    def parse_base_info(self, base_file_path: str) -> BaseInfo:
        info = BaseInfo()

        if base_file_path:
            if args.verbose:
                print("\nReading: " + args.base_file)

            base_file = self.read_file(base_file_path)
            if not base_file:
                print("Base File does not exist: " + base_file_path)
            else:
                if args.verbose:
                    print("\nParsing: " + args.base_file)

                [self._parse_base_info_recurse(info_plat, base_file) for info_plat in info.info_list]

        info.finish_parsing()
        return info
    
    def _parse_base_info_recurse(self, info: BaseInfoPlatform, base_file: QPCBlockBase, include_dir: str = "") -> None:
        for project_block in base_file:
        
            if not project_block.solve_condition(info.macros):
                continue
        
            elif project_block.key == "macro":
                info.add_macro(project_block)
        
            elif project_block.key == "configurations":
                configs = project_block.get_item_list_condition(info.macros)
                [info.configurations.append(config) for config in configs if config not in info.configurations]
        
            # very rushed thing that could of been done with macros tbh
            elif project_block.key == "dependency_paths":
                temp_dir = include_dir + "/" if include_dir else ""
                for dependency in project_block.items:
                    if dependency.values and dependency.solve_condition(info.macros):
                        info.dependency_dict[dependency.key] = temp_dir + dependency.values[0]
                        if temp_dir:
                            info.dependency_dict_original[dependency.values[0]] = dependency.key

            elif not project_block.values:
                continue

            elif project_block.key == "project":
                self._base_project_define(project_block, info, include_dir)

            elif project_block.key == "group":
                self._base_group_define(project_block, info)

            elif project_block.key == "include":
                # "Ah shit, here we go again."
                file_path = os.path.normpath(replace_macros(project_block.values[0], info.macros))
                new_include_dir = include_dir
                
                if len(project_block.values) >= 2:
                    new_include_dir += "/" + project_block.values[1] if include_dir else project_block.values[1]
                    new_include_dir = replace_macros(new_include_dir, info.macros)
                    current_dir = os.getcwd()
                    if os.path.isdir(new_include_dir):
                        os.chdir(new_include_dir)
                
                if args.verbose:
                    print("Reading: " + file_path)
            
                try:
                    include_file = read_file(file_path)
            
                    if args.verbose:
                        print("Parsing... ")
                
                    self._parse_base_info_recurse(info, include_file, new_include_dir)
                except FileNotFoundError:
                    project_block.warning("File Does Not Exist: ")
                    
                if len(project_block.values) >= 2:
                    os.chdir(current_dir)

            elif not args.hide_warnings:
                project_block.warning("Unknown Key: ")
            
    def _base_group_define(self, group_block: QPCBlock, info: BaseInfoPlatform):
        for group in group_block.values:
            # do we have a group with this name already?
            if group in info.shared.groups:
                project_group = info.shared.groups[group]
            else:
                project_group = ProjectGroup(group)
                info.shared.groups[project_group.name] = project_group
            self._parse_project_group_items(project_group, info, group_block, [])
            
    @staticmethod
    def _base_project_define(block: QPCBlock, info: BaseInfoPlatform, include_dir: str = ""):
        if include_dir:
            include_dir += "/"
        scripts = [include_dir + replace_macros(item.key, info.macros) for item in block.items if item.solve_condition(info.macros)]
        scripts += [include_dir + replace_macros(script, info.macros) for script in block.values[1:]]
        info.add_project(block.values[0], *scripts)

    @staticmethod
    def _check_plat_condition(condition: str) -> bool:
        cond = condition.lower()
        if "windows" in cond or "linux" in cond or "macos" in cond or "posix" in cond:
            return True
    
    def _parse_project_group_items(self, project_group: ProjectGroup, info: BaseInfoPlatform,
                                   project_block: QPCBlock, folder_list: list) -> None:
        for item in project_block.items:
            if item.solve_condition(info.macros):
                
                if item.key == "folder":
                    folder_list.append(item.values[0])
                    self._parse_project_group_items(project_group, info, item, folder_list)
                    folder_list.remove(item.values[0])
                else:
                    info.add_project_to_group(item.key, project_group, folder_list)
                    # project_group.add_project(item.key, folder_list, info.shared.unsorted_projects)
    
    def parse_project(self, project_def: ProjectDefinition, project_script: str, info: BaseInfo, generator_list: list) -> ProjectContainer:
        if args.time:
            start_time = perf_counter()
        else:
            print("Parsing: " + project_script)

        project_filename = os.path.split(project_script)[1]
        project_block = self.read_file(project_filename)

        if project_block is None:
            print("Script does not exist: " + project_script)
            return

        project_name = os.path.splitext(project_filename)[0]
        project_container = ProjectContainer(project_name, project_script, info, project_def, generator_list)
        
        for project_pass in project_container._passes:
            project_pass.hash_list[project_filename] = qpc_hash.make_hash(project_filename)
            self._parse_project(project_block, project_pass)
            self.counter += 1

        # self._merge_project_passes(project_container)
    
        if args.verbose:
            print("Parsed: " + project_container.get_display_name())

        if args.time:
            print(str(round(perf_counter() - start_time, 4)) + " - Parsed: " + project_script)
            
        return project_container
    
    def _parse_project(self, project_file: QPCBlockBase, project: ProjectPass, indent: str = "") -> None:
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
            
                elif project_block.key == "build_event":
                    self._parse_build_event(project_block, project)
                    
                elif project_block.key == "include":
                    # Ah shit, here we go again.
                    include_path = project.replace_macros(project_block.values[0])
                    include_file = self._include_file(include_path, project, project_file.file_path, indent + "    ")
                    if include_file:
                        try:
                            self._parse_project(include_file, project, indent + "    ")
                        except RecursionError:
                            raise RecursionError("Recursive Includes found:\n" + project_block.get_formatted_info())
                        if args.verbose:
                            print(indent + "    " + "Finished Parsing")
                    
                elif not args.hide_warnings:
                    project_block.warning("Unknown key: ")
    
    def _include_file(self, include_path: str, project: ProjectPass, project_path: str, indent: str) -> QPCBlockBase:
        project.hash_list[include_path] = qpc_hash.make_hash(include_path)
        include_file = self.read_file(include_path)
    
        if not include_file:
            print("File does not exist:\n\tScript: {0}\n\tFile: {1}".format(project_path, include_path))
            return None
    
        if args.verbose:
            print(indent + "Parsing: " + include_path)
    
        return include_file
        
    @staticmethod
    def _parse_build_event(project_block: QPCBlock, project: ProjectPass):
        if not project_block.values and not args.hide_warnings:
            project_block.warning("build_event has no name")
    
        # is this a definition?
        elif project_block.items:
            # check to see if it's already defined
            if project_block.values[0] in project.build_events:
                if not args.hide_warnings:
                    project_block.warning("build_event already defined, redefining")
            
            build_event = BuildEvent(*replace_macros_list(project.macros, *project_block.values))
            
            for item in project_block.items:
                command_list = replace_macros_list(project.macros, *item.get_item_list_condition(project.macros))
                if item.key == "pre_build":
                    build_event.pre_build.extend(command_list)
                elif item.key == "pre_link":
                    build_event.pre_link.extend(command_list)
                elif item.key == "post_build":
                    build_event.post_build.extend(command_list)
                elif not args.hide_warnings:
                    project_block.warning("invalid event in build_event:"
                                          "options are pre_build, pre_link, and post_build")
                    
            project.build_events[project_block.values[0]] = build_event
    
        # it's not, we are calling a build event
        elif project_block.values[0] in project.build_events:
            project.call_build_event(*project_block.values)
        elif not args.hide_warnings:
            project_block.warning("undefined build_event")
    
    def _parse_files(self, files_block: QPCBlock, project: ProjectPass, folder_list: list) -> None:
        if files_block.solve_condition(project.macros):
            for block in files_block.items:
                if not block.solve_condition(project.macros):
                    continue
                
                if block.key == "folder":
                    folder_list.append(block.values[0])
                    self._parse_files(block, project, folder_list)
                    folder_list.remove(block.values[0])
                elif block.key == "-":
                    project.remove_file(folder_list, block)
                else:
                    project.add_file(folder_list, block)
                
                    if block.items:
                        for file_path in block.get_list():
                            if check_file_path_glob(file_path):
                                [self._source_file(block, project, found_file) for found_file in glob.glob(file_path)]
                            else:
                                self._source_file(block, project, file_path)
                       
    @staticmethod
    def _source_file(files_block: QPCBlock, project: ProjectPass, file_path: str):
        source_file = project.get_source_file(file_path)
        if not source_file:
            return
    
        for config_block in files_block.items:
            if config_block.solve_condition(project.macros):
            
                if config_block.key == "configuration":
                    # if not args.hide_warnings:
                    #     config_block.warning("Legacy Source File compiler info syntax\n"
                    #                          "Remove \"configuration { compiler {\", ")
                    for group_block in config_block.items:
                    
                        if group_block.key != "compiler":
                            group_block.error("Invalid Group, can only use compiler")
                            continue
                    
                        if group_block.solve_condition(project.macros):
                            for option_block in group_block.items:
                                if option_block.solve_condition(project.macros):
                                    source_file.compiler.parse_option(project.macros, option_block)
                else:
                    # new, cleaner way, just assume it's compiler
                    source_file.compiler.parse_option(project.macros, config_block)

    def read_file(self, script_path: str) -> QPCBlockBase:
        if script_path in self.read_files:
            return self.read_files[script_path]
        else:
            try:
                script = read_file(script_path)
                self.read_files[script_path] = script
                return script
            except FileNotFoundError:
                pass
    
    # awful
    @staticmethod
    def _parse_config(project_block: QPCBlock, project: ProjectPass) -> None:
        if project_block.solve_condition(project.macros):
            for group_block in project_block.items:
                if group_block.solve_condition(project.macros):
                    for option_block in group_block.items:
                        if option_block.solve_condition(project.macros):
                            project.config.parse_config_option(group_block, option_block)
