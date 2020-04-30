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
from qpc_base import BaseProjectGenerator, create_directory, Platform, Arch

import qpc_hash


PRINT_LINE = "------------------------------------------------------------------------"


def get_platform_list() -> list:
    platforms = []
    for platform in args.platforms:
        if platform in Platform and platform not in platforms:
            platforms.append(platform)
            break
    return platforms


def get_generators_all() -> list:
    generator_list = []
    
    for generator in GENERATOR_HANDLER.project_generators:
        platforms = generator.get_supported_platforms()
        # intersection is if any items in a set is in another set
        has_valid_platforms = set(args.platforms).intersection(set(platforms))
        if has_valid_platforms:
            generator_list.append(generator)
                
    return generator_list


# unused?
def get_generators_other(platform: Enum) -> list:
    generator_list = []
    for generator in GENERATOR_HANDLER.project_generators:
        platforms = generator.get_supported_platforms()
        # intersection is if any items in a set is in another set
        has_valid_platforms = platform in platforms
        if has_valid_platforms and generator not in generator_list:
            generator_list.append(generator)
    return generator_list


def check_platforms(platform_list: set, generator_platforms: list) -> set:
    # intersection is if any items in a set is in another set
    return platform_list.intersection(set(generator_platforms))


def get_generator_need_rebuild(project_script: str, generator_list: list) -> list:
    generators = []
    for generator in generator_list:
        if not generator.does_project_exist(project_script):
            generators.append(generator)
    return generators


def get_generators(platforms: set, generator_list: list) -> list:
    valid_generators = []
    for generator in generator_list:
        if check_platforms(platforms, generator.get_supported_platforms()):
            valid_generators.append(generator)
    return valid_generators


def generator_needs_rebuild(project_script: str, generator: BaseProjectGenerator, rebuild_info: dict) -> bool:
    if not generator.does_project_exist(project_script):
        return True
    if generator.filename in rebuild_info["generators"]:
        return True
    return False


# only run if the hash check fails or if the user force creates projects
# may look in the hash for where the project output directory is in the future
def should_build_project(project_script: str, generator_list: list) -> bool:
    if args.skip_projects:
        return False
    if args.force:
        return True
    return not qpc_hash.check_hash(project_script)


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
    if args.time:
        start_time = perf_counter()
    
    info = parser.parse_base_info(args.base_file)
    generator_list = get_generators_all()
    
    for project_def in info.projects:
        for project_script in project_def.script_list:
                
            valid_generators = get_generators(project_def.platforms, generator_list)

            if not valid_generators:
                continue
            
            if not args.skip_projects:
                print()

            generators_rebuild = get_generator_need_rebuild(project_script, valid_generators)
            if generators_rebuild or should_build_project(project_script, valid_generators):
                rebuild_info = qpc_hash.get_rebuild_info(project_script, generators_rebuild)

                project_dir, project_filename = os.path.split(project_script)

                if project_dir and project_dir != args.root_dir:
                    os.chdir(project_dir)

                project = parser.parse_project(project_def, project_script, info, valid_generators)
                if not project:
                    continue

                if args.force or rebuild_info["rebuild_all"]:
                    [generator.create_project(project) for generator in valid_generators]
                else:
                    # does any generator need to rebuild?
                    for generator in valid_generators:
                        if generator_needs_rebuild(project_filename, generator, rebuild_info):
                            generator.create_project(project)

                if project_dir and project_dir != args.root_dir:
                    os.chdir(args.root_dir)

                info.add_project_dependencies(project_script, project.dependencies)
                qpc_hash.write_project_hash(project_script, project, valid_generators)
                    
            else:
                info.add_project_dependencies(project_script, qpc_hash.get_project_dependencies(project_script))
                
            info.project_hashes[project_script] = qpc_hash.get_hash_file_path(project_script)

    if args.time:
        print("\nFinished Parsing Projects"
              "\n\tTime: " + str(round(perf_counter() - start_time, 4)) +
              "\n\tParse Count: " + str(parser.counter))

    [generator.projects_finished() for generator in generator_list]

    if args.master_file:
        print(PRINT_LINE)
        for generator in generator_list:
            if not generator.generates_master_file():
                continue
                
            file_path = generator.get_master_file_path(args.master_file)
            generator_platforms = set()
            [generator_platforms.add(platform) for platform in generator.get_supported_platforms()]
            project_hashes = info.get_hashes(*generator_platforms)
            
            if should_call_create_master_file(file_path, info, generator, project_hashes):
                generator.create_master_file(info, file_path)
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
    qpc_hash.post_args_init()
    main()
    
    print("" + PRINT_LINE + "\n"
          " Finished\n" +
          PRINT_LINE)
