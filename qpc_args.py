import sys
import os
import argparse
import shutil
from enum import Enum, auto, EnumMeta
import glob
from qpc_base import Platform, get_default_platforms

PROJECT_GENERATORS = []
for f in glob.glob(os.path.join(os.path.dirname(__file__) + "/project_generators", "*.py")):
    if os.path.isfile(f):
        PROJECT_GENERATORS.append(os.path.basename(f)[:-3])


DEFAULT_BASEFILE = "_qpc_scripts/_default.qpc_base"


# this is here so i can check arguments globally across files
def parse_args():
    platforms = [platform.name.lower() for platform in Platform]

    cmd_parser = argparse.ArgumentParser()

    # maybe change to path? meh
    cmd_parser.add_argument("--rootdir", "-d", default=os.getcwd(), dest="root_dir",
                            help="Set the root directory of the script")
    cmd_parser.add_argument("--basefile", "-b", default=DEFAULT_BASEFILE, dest="base_file", nargs="+",
                            help="Set the root directory of the script")
    cmd_parser.add_argument("--outdir", "-o", default="", dest="out_dir",
                            help="Output directory of qpc scripts with edited folder paths")
    
    # TODO: remove this awful command and use a macro from the project instead
    cmd_parser.add_argument("--project_dir", action="store_true",
                            help="Output project files based on PROJECT_DIR macro, relative to master_file dir")

    cmd_parser.add_argument("--time", "-t", action="store_true", help="Print the time taken to parse")
    cmd_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose console output")
    cmd_parser.add_argument("--force", "-f", action="store_true", help="Force recreate all projects")
    cmd_parser.add_argument("--force_master", "-fm", action="store_true", help="Force recreate master file")
    cmd_parser.add_argument("--hidewarnings", "-w", dest="hide_warnings", action="store_true", help="Suppress all warnings")
    cmd_parser.add_argument("--checkfiles", "-c", dest="check_files", action="store_true", help="Check if any added file exists")
    
    cmd_parser.add_argument("--platforms", "-p", nargs="+", default=get_default_platforms(), choices=platforms,
                            help="Select plaforms to generate for instead of default")
    cmd_parser.add_argument("--generators", "-g", nargs="+", default=(), choices=PROJECT_GENERATORS, help="Project types to generate")
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

    return cmd_parser


# global var
arg_parser = parse_args()
args = arg_parser.parse_args()

args.root_dir = os.path.normpath(args.root_dir) if os.path.isabs(args.root_dir) else \
    os.path.normpath(os.getcwd() + os.sep + args.root_dir)

# args.base_file = os.path.normpath(args.base_file) if os.path.isabs(args.base_file) else \
#     os.path.normpath(args.root_dir + os.sep + args.base_file)

args.out_dir = os.path.normpath(args.out_dir) if os.path.isabs(args.out_dir) else \
    os.path.normpath(args.root_dir + os.sep + args.out_dir)


# could just make a dictionary, where keys are enums and values are your mom?
def _get_enum_from_name(enum_name: str, enum_list: EnumMeta) -> Enum:
    for enum in enum_list:
        if enum.name.lower() == enum_name:
            return enum


# convert stuff in args to the enum value
def _convert_to_enum(arg_list: list, enum_list: EnumMeta) -> list:
    for index, value in enumerate(arg_list):
        arg_list[index] = _get_enum_from_name(value, enum_list)
    return arg_list


args.platforms = _convert_to_enum(args.platforms, Platform)


def get_arg_macros() -> dict:
    arg_macros = {}
    for macro in args.macros:
        arg_macros["$" + macro] = "1"
    return arg_macros
