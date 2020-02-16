# ---------------------------------------------------------------------
# Quiver Project Creator
# Written by Demez
# ---------------------------------------------------------------------

import os
import sys

from enum import Enum
import qpc_hash
import qpc_reader
from qpc_generator_handler import GeneratorHandler
from qpc_parser import Parser
from qpc_args import args
from qpc_base import PLATFORM_DICT

if args.time:
    from time import perf_counter


def SetProjectTypeMacros(base_macros, project_types_list):
    for name in project_types_list:
        base_macros["$" + name.name.upper()] = "1"
        if args.verbose:
            print('Set Macro: ${0} = "1"'.format(name.upper()))


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


def main():
    os.chdir(args.root_dir)
    
    generator_handler = GeneratorHandler()
    parser = Parser()
    # loop PlatformNames -> BaseSettings, OutputTypes -> Configs -> Platforms
    if args.time:
        start_time = perf_counter()
    for platform_name, platform_list in get_platform_dict().items():
    
        # if args.verbose:
        print("Current Platform: " + platform_name.name)
        
        info = parser.parse_base_info(args.base_file, platform_name)
        # generator_handler.project_generator_modules
        for generator in generator_handler.project_generators:
            platforms = generator.get_supported_platforms()
            has_valid_platforms = PLATFORM_DICT[info.platform].intersection(set(platforms))
            
            if not has_valid_platforms:
                continue
            
            # if args.verbose:
            print("Current Project Generator: " + generator.name)
            
            # info = parser.parse_base_settings(args.base_file, generator_name, platform_name)
            for project_def in info.project_definitions:
                for project_script in project_def.script_list:
                    print()
                    # only run if the hash check fails or if the user force creates the _projects
                    # may look in the hash for where the project output directory is
                    if args.force or \
                            not generator.does_project_exist(project_script) or \
                            not qpc_hash.check_hash(project_script):
                        project = parser.parse_project(project_script, info, platforms)
                        generator.create_project(project)
                        info.project_dependencies[project_script] = project.dependencies

                        qpc_hash.write_hash_file(project_script, project.out_dir, project.hash_dict,
                                                 dependencies=project.dependencies)
                    else:
                        info.project_dependencies[project_script] = qpc_hash.get_project_dependencies(project_script)
                        
                    info.project_hashes[qpc_hash.get_hash_file_path(project_script)] = project_script
    
            if args.time:
                print("\nFinished Parsing Projects for " + generator.name +
                      "\n\tTime: " + str(round(perf_counter() - start_time, 4)) +
                      "\n\tParse Count: " + str(parser.counter))
    
            if args.master_file:
                print()
                # TODO: this won't rebuild the master file if the project groups "includes" are changed
                generator.create_master_file(info, args.master_file)


if __name__ == "__main__":
    # TODO: maybe print more info here if verbose?
    print("----------------------------------------------------------------------------------\n"
          " Quiver Project Creator\n " + ' '.join(sys.argv[1:]) +
          "\n----------------------------------------------------------------------------------")
    
    main()
    
    print("----------------------------------\n"
          " Finished\n"
          "----------------------------------\n")
