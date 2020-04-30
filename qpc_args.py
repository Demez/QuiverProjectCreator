import sys
import os
import argparse
import shutil
from enum import Enum, auto, EnumMeta
import glob
from qpc_base import Platform, Arch, get_default_platform, get_default_archs


args = argparse.Namespace()
DEFAULT_BASEFILE = "_qpc_scripts/_default.qpc_base"


# this is here so i can check arguments globally across files
def parse_args(generators: list) -> None:
    platforms = [platform.name.lower() for platform in Platform]
    archs = [arch.name.lower() for arch in Arch]

    cmd_parser = argparse.ArgumentParser()

    # maybe change to path? meh
    cmd_parser.add_argument("--rootdir", "-d", default=os.getcwd(), dest="root_dir",
                            help="Set the root directory of the script")
    cmd_parser.add_argument("--basefile", "-b", dest="base_file",  # nargs="+",
                            help="Set the root directory of the script")
    cmd_parser.add_argument("--outdir", "-o", default="", dest="out_dir",
                            help="Output directory of qpc scripts with edited folder paths")
    
    # TODO: test this
    # cmd_parser.add_argument("--projectdir", action="store_true",
    #                         help="Output container files based on PROJECT_DIR macro, relative to root dir probably")

    cmd_parser.add_argument("--time", "-t", action="store_true", help="Print the time taken to parse")
    cmd_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose console output")
    cmd_parser.add_argument("--force", "-f", action="store_true", help="Force recreate all projects")
    cmd_parser.add_argument("--force_master", "-fm", action="store_true", help="Force recreate master file")
    cmd_parser.add_argument("--hidewarnings", "-w", dest="hide_warnings", action="store_true", help="Suppress all warnings")
    cmd_parser.add_argument("--checkfiles", "-cf", dest="check_files", action="store_true", help="Check if any added file exists")
    cmd_parser.add_argument("--skipprojects", "-sp", dest="skip_projects", action="store_true", help="Don't generate projects")

    cmd_parser.add_argument("--configs", "-c", nargs="+", help="Select configurations, added to configs set in base files")
    cmd_parser.add_argument("--platforms", "-p", nargs="+", default=(get_default_platform(),), choices=platforms,
                            help="Select platforms to generate for instead of the default")
    cmd_parser.add_argument("--archs", "-ar", nargs="+", default=get_default_archs(), choices=archs,
                            help="Select architectures to generate for instead of the default")
    cmd_parser.add_argument("--generators", "-g", nargs="+", default=(), choices=generators, help="Project types to generate")
    cmd_parser.add_argument("--add", "-a", nargs="+", default=(), help="Add projects or groups to generate")
    cmd_parser.add_argument("--remove", "-r", default=(), nargs="+", help="Remove projects or groups from generating")
    cmd_parser.add_argument("--macros", "-m", nargs="+", default=(), help="Macros to define and set to '1' in projects")

    # TODO: figure out how vpc handles these and recreate it here
    #  might come waaay later since it"s very low priority
    # cmd_parser.add_argument("-at", "--add_tree", nargs="+", help="Add a project and all projects that depend on it")
    # cmd_parser.add_argument("-ad", "--add_depend", nargs="+", help="Add a project and all projects that it depends on")
    # Use /h spew final target build set only (no .vcproj created). - what?

    cmd_parser.add_argument("--masterfile", "-mf", dest="master_file",
                            help='Create a master file for building all projects with')

    global args
    args.__dict__.update(cmd_parser.parse_args().__dict__)

    args.root_dir = os.path.normpath(args.root_dir) if os.path.isabs(args.root_dir) else \
        os.path.normpath(os.getcwd() + os.sep + args.root_dir)

    # args.base_file = os.path.normpath(args.base_file) if os.path.isabs(args.base_file) else \
    #     os.path.normpath(args.root_dir + os.sep + args.base_file)

    args.out_dir = os.path.normpath(args.out_dir) if os.path.isabs(args.out_dir) else \
        os.path.normpath(args.root_dir + os.sep + args.out_dir)

    args.platforms = _convert_to_enum(args.platforms, Platform)
    args.archs = _convert_to_enum(args.archs, Arch)


# could just make a dictionary, where keys are enums and values are your mom?
def _get_enum_from_name(enum_name: str, enum_list: EnumMeta) -> Enum:
    for enum in enum_list:
        if enum.name.lower() == enum_name:
            return enum


# convert stuff in args to the enum value
def _convert_to_enum(arg_list: list, enum_list: EnumMeta) -> list:
    if type(arg_list) == tuple:
        return arg_list
    for index, value in enumerate(arg_list):
        arg_list[index] = _get_enum_from_name(value, enum_list)
    return arg_list


def get_arg_macros() -> dict:
    arg_macros = {}
    for macro in args.macros:
        arg_macros["$" + macro] = "1"
    return arg_macros
