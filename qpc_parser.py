import os
import glob
import qpc_hash
from qpc_reader import read_file, QPCBlock, QPCBlockBase
from qpc_args import args, get_arg_macros
from qpc_base import Platform, PlatformName, get_platform_name, check_file_path_glob
from qpc_project import ProjectContainer, ProjectBase, ProjectDefinition, ProjectGroup, SourceFile, replace_macros
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
        }
    
    elif platform == PlatformName.LINUX:
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
    
    
class BaseInfoPlatform:
    def __init__(self, base_info, platform: Enum):
        self.shared = base_info
        self.platform = platform
        self.macros = {**get_arg_macros(), **get_platform_macros(platform)}
        
        if args.verbose:
            print()
            [print('Set Macro: {0} = "{1}"'.format(name, value)) for name, value in self.macros.items()]
        
        self.groups = {}
        self.all_projects = []
        self.undef_projects = {}
        self.dependency_dict = {}
        self.dependency_dict_unfixed = {}
        self.configurations = []
        self.projects_to_use = []

    def add_macro(self, project_block: QPCBlock):
        self.macros["$" + project_block.values[0].upper()] = replace_macros(project_block.values[1], self.macros)
    
    def add_project(self, project: ProjectDefinition):
        project.update_groups()
        self.all_projects.append(project)

    def is_project_script_added(self, project_path: str) -> bool:
        return bool(self.get_project_def_script(project_path))

    def is_project_added(self, project_name: str) -> bool:
        if project_name in self.shared.unsorted_projects:
            return True
        return bool(self.get_project_def_script(project_name))

    def get_project_def_script(self, project_path: str) -> ProjectDefinition:
        for project in self.all_projects:
            if project_path in project.script_list:
                return project

    def get_project_def_name(self, project_name: str) -> ProjectDefinition:
        for project in self.all_projects:
            if project.name == project_name:
                return project

    def get_project_def(self, project_name: str) -> ProjectDefinition:
        for project in self.all_projects:
            if project.name == project_name or project_name in project.script_list:
                return project
            
    def get_dependency_path(self, key: str):
        if key in self.dependency_dict_unfixed:
            return self.dependency_dict[self.dependency_dict_unfixed[key]]
        elif key in self.dependency_dict:
            return self.dependency_dict[key]
        return key

    def _use_project(self, project: ProjectDefinition, unwanted_projects: dict):
        if self.platform in project.platforms and project.name not in unwanted_projects:
            for added_project in self.projects_to_use:
                if added_project.name == project.name:
                    break
            else:
                self.projects_to_use.append(project)
        
    # get all the _passes the user wants (this is probably the worst part in this whole project)
    def setup_wanted_projects(self) -> None:
        self.projects_to_use = []

        unwanted_projects = {}
        remove_list = []
        add_list = []

        for item in args.add:
            if check_file_path_glob(item):
                add_list.extend(glob.glob(item))
            else:
                add_list.append(item)

        for item in args.remove:
            if check_file_path_glob(item):
                remove_list.extend(glob.glob(item))
            else:
                remove_list.append(item)

        [add_list.remove(item) for item in remove_list if item in add_list]

        for removed_item in remove_list:
            if removed_item in self.shared.groups:
                for project in self.shared.groups[removed_item].projects:
                    if project.name not in unwanted_projects:
                        unwanted_projects[project.name] = project
            
            elif removed_item in self.shared.unsorted_projects:
                if self.shared.unsorted_projects[removed_item] in self.all_projects:
                    unwanted_projects[removed_item] = self.shared.unsorted_projects[removed_item]
            else:
                for project in self.all_projects:
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

                    # TODO: move to another function
                    '''
                    for project in self.shared.groups[added_item].projects:
                        if self.platform in project.platforms and project.name not in unwanted_projects:
                            for added_project in self.projects_to_use:
                                if added_project.name == project.name:
                                    break
                            else:
                                self.projects_to_use.append(project)
                    '''
                elif added_item in self.shared.unsorted_projects:
                    if self.shared.unsorted_projects[added_item] in self.all_projects:
                        self._use_project(self.shared.unsorted_projects[added_item], unwanted_projects)
                else:
                    for project in self.all_projects:
                        if added_item in project.script_list:
                            self._use_project(project, unwanted_projects)
                            break
                    else:
                        print("Project, Group, or Script does not exist: " + added_item)
                    '''
                    for project in self.all_projects:
                        if added_item == project.name or added_item in project.script_list:
                            for added_project in self.projects_to_use:
                                if added_project.name == project.name:
                                    break
                            else:
                                self.projects_to_use.append(project)
                    '''
                    # else:
                    #     print("hey this item doesn't exist: " + added_item)
        else:
            raise Exception("No projects were added to generate for")


class BaseInfo:
    def __init__(self, platform_list: tuple):
        self.platform_list = platform_list
        self.project_list = {}
        self.unsorted_projects = {}
        self.groups = {}
        self.info_list = [BaseInfoPlatform(self, platform) for platform in platform_list]
        
        self.project_hashes = {}
        self.project_dependencies = {}

    def get_base_info(self, platform: Enum) -> BaseInfoPlatform:
        if platform in Platform:
            return self.get_base_info_plat_name(get_platform_name(platform))

    def get_base_info_plat_name(self, platform_name: Enum) -> BaseInfoPlatform:
        for base_info in self.info_list:
            if base_info.platform == platform_name:
                return base_info

    def get_configs(self) -> list:
        configurations = set()
        [configurations.update(info.configurations) for info in self.info_list]
        return list(configurations)

    # get all the _passes the user wants (this is probably the worst part in this whole project)
    def get_wanted_projects(self) -> tuple:
        self.project_list = {}  # dict keeps order, set doesn't as of 3.8, both faster than lists
        for base_info in self.info_list:
            base_info.setup_wanted_projects()
            for project in base_info.projects_to_use:
                if project not in self.project_list:
                    self.project_list[project] = None
        self.project_list = tuple(self.project_list.keys())
        return self.project_list


class Parser:
    def __init__(self):
        self.counter = 0
        self.read_files = {}

    # TODO: bug discovered with this,
    #  if i include the groups before the base_info, it won't add any base_info
    # def parse_base_settings(self, base_file_path: str, output_type: str, platform: Enum) -> BaseInfo:
    def parse_base_info(self, base_file_path: str, platform_list: tuple) -> BaseInfo:
        info = BaseInfo(platform_list)

        if base_file_path:
            if args.verbose:
                print("\nReading: " + args.base_file)

            base_file = self.read_file(base_file_path)
            if not base_file:
                print("Base File does not exist: " + base_file_path)
            else:
                if args.verbose:
                    print("\nParsing: " + args.base_file)

                [self._parse_base_info_include(info_plat, base_file) for info_plat in info.info_list]

        [self._parse_base_info_args(info_plat) for info_plat in info.info_list]

        info.get_wanted_projects()
        return info

    def _parse_base_info_args(self, info: BaseInfoPlatform) -> None:
        for project_path in args.add:
            if check_file_path_glob(project_path):
                for found_file in glob.glob(project_path):
                    self._add_project_base(info, os.path.splitext(os.path.basename(found_file))[0], found_file)
            elif os.path.isfile(project_path):
                self._add_project_base(info, os.path.splitext(os.path.basename(project_path))[0], project_path)
            elif not info.is_project_added(project_path) and project_path not in info.shared.groups:
                print("Project, Group, or File does not exist: " + project_path)

        if not info.configurations:
            info.configurations.append("Default")
    
    def _parse_base_info_include(self, info: BaseInfoPlatform, base_file: QPCBlockBase, include_dir: str = "") -> None:
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
                            info.dependency_dict_unfixed[dependency.values[0]] = dependency.key

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
                
                    self._parse_base_info_include(info, include_file, new_include_dir)
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
    def _add_project_base(info: BaseInfoPlatform, project_name: str, *project_paths) -> None:
        # TODO: check if script path is already used
        if project_name in info.shared.unsorted_projects:
            project_def = info.shared.unsorted_projects[project_name]
        else:
            project_def = ProjectDefinition(project_name)
            info.shared.unsorted_projects[project_name] = project_def
        project_def.platforms.add(info.platform)

        # could have values next to it as well now
        for script_path in project_paths:
            script_path = replace_macros(script_path, info.macros)
            project_def.add_script(script_path)

        info.add_project(project_def)
                
    def _base_project_define(self, block: QPCBlock, info: BaseInfoPlatform, include_dir: str = ""):
        if include_dir:
            include_dir += "/"
        scripts = [include_dir + replace_macros(item.key, info.macros) for item in block.items if item.solve_condition(info.macros)]
        scripts += [include_dir + replace_macros(script, info.macros) for script in block.values[1:]]
        self._add_project_base(info, block.values[0], *scripts)

    @staticmethod
    def _check_plat_condition(condition: str) -> bool:
        cond = condition.lower()
        return PlatformName.WINDOWS.name.lower() in cond or PlatformName.LINUX.name.lower() in cond or \
            PlatformName.POSIX.name.lower() in cond or PlatformName.MACOS.name.lower() in cond
    
    def _parse_project_group_items(self, project_group: ProjectGroup, info: BaseInfoPlatform,
                                   project_block: QPCBlock, folder_list: list) -> None:
        for item in project_block.items:
            if item.solve_condition(info.macros):
                
                if item.key == "folder":
                    folder_list.append(item.values[0])
                    self._parse_project_group_items(project_group, info, item, folder_list)
                    folder_list.remove(item.values[0])
                else:
                    project_group.add_project(item.key, folder_list, info.shared.unsorted_projects)
    
    def parse_project(self, project_def: ProjectDefinition, project_script: str,
                      info: BaseInfo, generator_list: list, platform_dict: dict) -> ProjectContainer:
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
        project_container = ProjectContainer(project_name, project_script, info, project_def, generator_list, platform_dict)
        
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
    
    def _parse_project(self, project_file: QPCBlockBase, project: ProjectBase, indent: str = "") -> None:
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
                    if include_file:
                        self._parse_project(include_file, project, indent + "    ")
                        if args.verbose:
                            print(indent + "    " + "Finished Parsing")
                    
                elif not args.hide_warnings:
                    project_block.warning("Unknown key: ")
    
    def _include_file(self, include_path: str, project: ProjectBase, project_path: str, indent: str) -> QPCBlockBase:
        project.hash_list[include_path] = qpc_hash.make_hash(include_path)
        include_file = self.read_file(include_path)
    
        if not include_file:
            print("File does not exist:\n\tScript: {0}\n\tFile: {1}".format(project_path, include_path))
            return None
    
        if args.verbose:
            print(indent + "Parsing: " + include_path)
    
        return include_file
    
    def _parse_files(self, files_block: QPCBlock, project: ProjectBase, folder_list: list) -> None:
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
    def _source_file(files_block: QPCBlock, project: ProjectBase, file_path: str):
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
            try:
                script = read_file(script_path)
                self.read_files[script_path] = script
                return script
            except FileNotFoundError:
                pass
    
    # awful
    @staticmethod
    def _parse_config(project_block: QPCBlock, project: ProjectBase) -> None:
        if project_block.solve_condition(project.macros):
            for group_block in project_block.items:
                if group_block.solve_condition(project.macros):
                    for option_block in group_block.items:
                        if option_block.solve_condition(project.macros):
                            project.config.parse_config_option(group_block, option_block)

    # gets everything that's the same across all project _passes, and puts them into container.shared
    def _merge_project_passes(self, container: ProjectContainer) -> None:
        macros = []
        configs = []
        files = []
        source_files = []
        # dependencies = []
        
        for proj_pass in container._passes:
            macros.append(proj_pass.macros)
            configs.append(proj_pass.config)
            files.append(proj_pass.files)
            source_files.append(proj_pass.source_files)
            # source_files.append(proj_pass.dependencies)
            
        self._compare_configs(container, configs)
        
    def _compare_configs(self, container: ProjectContainer, configs: list) -> None:
        general = []
        compiler = []
        linker = []
        pre_build = []
        pre_link = []
        post_build = []
    
        for config in configs:
            general.append(config.general)
            compiler.append(config.compiler)
            linker.append(config.linker)
            pre_build.append(config.pre_build)
            pre_link.append(config.pre_link)
            post_build.append(config.post_build)
            
        self._compare_config_general(container, general)
        pass
        
    def _compare_config_general(self, container: ProjectContainer, general_list: list) -> None:
        for general in general_list:
            test = all()
            break
        pass
