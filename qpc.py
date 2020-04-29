# ---------------------------------------------------------------------
# Quiver Project Creator
# Written by Demez
# ---------------------------------------------------------------------

import os
import sys

from time import perf_counter
from enum import Enum

import qpc_reader
from qpc_generator_handler import GeneratorHandler
from qpc_parser import Parser, ProjectDefinition
from qpc_args import args, parse_args
from qpc_base import BaseProjectGenerator, PLATFORM_DICT, create_directory, get_platform_name

import qpc_hash
# from qpc_hash import (check_hash, check_master_file_hash, write_project_hash, write_master_file_hash,
#                       get_project_dependencies, get_hash_file_path, QPC_HASH_DIR)


PRINT_LINE = "------------------------------------------------------------------------"


def get_platform_list() -> list:
    platform_names = []
    for platform in args.platforms:
        for platform_name in PLATFORM_DICT:
            if platform in PLATFORM_DICT[platform_name] and platform_name not in platform_names:
                platform_names.append(platform_name)
                break
    return platform_names


def get_platform_dict() -> dict:
    platform_names = {}
    for platform in args.platforms:
        for platform_name in PLATFORM_DICT:
            if platform in PLATFORM_DICT[platform_name]:
                if platform_name not in platform_names:
                    platform_names[platform_name] = [platform]
                else:
                    platform_names[platform_name].append(platform)
                break
    return platform_names


def get_generators_all(platform_list: list) -> list:
    generator_list = []
    
    for generator in GENERATOR_HANDLER.project_generators:
        platforms = generator.get_supported_platforms()
        for platform in platform_list:
            # intersection is if any items in a set is in another set
            has_valid_platforms = PLATFORM_DICT[platform].intersection(set(platforms))
            if has_valid_platforms and generator not in generator_list:
                generator_list.append(generator)
                break
                
    return generator_list


def get_generators(platform: Enum) -> list:
    generator_list = []
    for generator in GENERATOR_HANDLER.project_generators:
        platforms = generator.get_supported_platforms()
        # intersection is if any items in a set is in another set
        has_valid_platforms = PLATFORM_DICT[platform].intersection(set(platforms))
        if has_valid_platforms and generator not in generator_list:
            generator_list.append(generator)
    return generator_list


def check_platforms(platform_list: list, generator_platforms: list) -> set:
    has_valid_platforms = set()
    for platform in platform_list:
        # intersection is if any items in a set is in another set
        has_valid_platforms.update(PLATFORM_DICT[platform].intersection(set(generator_platforms)))
    return has_valid_platforms


def any_generator_need_rebuild(project_script: str, platforms: list, generator_list: list) -> bool:
    for generator in generator_list:
        if check_platforms(platforms, generator.get_supported_platforms()):
            if not generator.does_project_exist(project_script):
                return True
    return False


def generator_needs_rebuild(project_script: str, platforms: list, generator: BaseProjectGenerator, hash_generators: list) -> bool:
    if check_platforms(platforms, generator.get_supported_platforms()):
        if not generator.does_project_exist(project_script):
            return True
        if generator.filename in hash_generators:
            return True
    return False


def check_valid_platforms(generator: BaseProjectGenerator, platform: Enum):
    platforms = generator.get_supported_platforms()
    return PLATFORM_DICT[platform].intersection(set(platforms))


# only run if the hash check fails or if the user force creates projects
# may look in the hash for where the project output directory is in the future
def should_build_project(project_script: str, project_def: ProjectDefinition, generator_list: list) -> bool:
    if args.skip_projects:
        return False
    if args.force:
        return True
    if any_generator_need_rebuild(project_script, project_def.platforms, generator_list):
        return True
    return not qpc_hash.check_hash(project_script)


def should_call_create_project(hash_result: bool, project_script: str, project_def: ProjectDefinition, generator: BaseProjectGenerator) -> bool:
    if args.force:
        return True
    if generator_needs_rebuild(project_script, project_def.platforms, generator):
        return True
    return hash_result


def should_call_create_master_file(file_path: str, info, generator: BaseProjectGenerator, hashes: dict) -> bool:
    if args.force_master:
        return True
    if file_path:
        if not os.path.isfile(file_path):
            return True
        if not qpc_hash.check_master_file_hash(file_path, info, generator, hashes):
            return True
    return False


def main():
    create_directory(qpc_hash.QPC_HASH_DIR)
    os.chdir(args.root_dir)
    
    parser = Parser()
    # loop PlatformNames -> BaseSettings, OutputTypes -> Configs -> Platforms
    if args.time:
        start_time = perf_counter()
        
    platform_dict = get_platform_dict()
    
    info = parser.parse_base_info(args.base_file, tuple(platform_dict.keys()))
    generator_list = get_generators_all(info.platform_list)
    
    for project_def in info.project_list:
        for project_script in project_def.script_list:
            if not args.skip_projects:
                print()
                
            if should_build_project(project_script, project_def, generator_list):
                hash_result = qpc_hash.check_hash(project_script, False)
                hash_generators = qpc_hash.get_project_generator_hash(project_script)

                project_dir, project_filename = os.path.split(project_script)

                if project_dir and project_dir != args.root_dir:
                    os.chdir(project_dir)

                project = parser.parse_project(project_def, project_script, info, generator_list, platform_dict)
                if not project:
                    continue

                if args.force or hash_result:
                    [generator.create_project(project) for generator in generator_list]
                else:
                    # does any generator need to rebuild?
                    for generator in generator_list:
                        if generator_needs_rebuild(project_filename, project_def.platforms, generator, hash_generators):
                            generator.create_project(project)

                if project_dir and project_dir != args.root_dir:
                    os.chdir(args.root_dir)

                info.add_project_dependencies(project_script, list(platform_dict), project.dependencies)
                qpc_hash.write_project_hash(project_script, project)
                    
            else:
                info.add_project_dependencies(
                    project_script, list(platform_dict), qpc_hash.get_project_dependencies(project_script))
                
            info.project_hashes[project_script] = qpc_hash.get_hash_file_path(project_script)

    if args.time:
        print("\nFinished Parsing Projects"
              "\n\tTime: " + str(round(perf_counter() - start_time, 4)) +
              "\n\tParse Count: " + str(parser.counter))

    [generator.projects_finished() for generator in generator_list]

    if args.master_file:
        print(PRINT_LINE)
        # TODO: this won't rebuild the master file if the project groups "includes" are changed
        for generator in generator_list:
            if not generator.generates_master_file():
                continue
                
            file_path = generator.get_master_file_path(args.master_file)
            generator_platforms = set()
            [generator_platforms.add(get_platform_name(platform)) for platform in generator.get_supported_platforms()]
            project_hashes = info.get_hashes_plat(*generator_platforms)
            
            if should_call_create_master_file(file_path, info, generator, project_hashes):
                generator.create_master_file(info, file_path, platform_dict)
                qpc_hash.write_master_file_hash(file_path, info, generator.get_supported_platforms(), generator.path)


if __name__ == "__main__":
    # TODO: maybe print more info here if verbose?
    print(PRINT_LINE + "\n"
          " Quiver Project Creator\n " + ' '.join(sys.argv[1:]) +
          "\n" + PRINT_LINE)

    # doing this so we only allow valid generator options
    GENERATOR_HANDLER = GeneratorHandler()
    parse_args(GENERATOR_HANDLER.get_generator_args())
    GENERATOR_HANDLER.post_args_init()
    main()
    
    print("" + PRINT_LINE + "\n"
          " Finished\n" +
          PRINT_LINE)
