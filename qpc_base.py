
# import sys
import os
import argparse
import shutil
from enum import Enum, auto


class ConfigurationTypes(Enum):
    STATIC_LIB = auto(),
    SHARED_LIB = auto(),
    DYNAMIC_LIB = auto(),
    APPLICATION = auto(),


class Languages(Enum):
    CPP = auto(),
    C = auto()


class Platforms(Enum):
    WIN32 = auto(),
    WIN64 = auto(),
    LINUX32 = auto(),
    LINUX64 = auto(),
    MACOS = auto()


# could make a class for a compiler, with the versions listed,
# probably a bad idea, as it won't really work for qpc
class Compilers(Enum):
    MSVC_142 = auto(),
    MSVC_141 = auto(),
    MSVC_140 = auto(),
    MSVC_120 = auto(),
    MSVC_100 = auto(),

    CLANG_9 = auto(),
    CLANG_8 = auto(),

    # GCC_10 = auto(),
    GCC_9 = auto(),
    GCC_8 = auto(),
    GCC_7 = auto(),
    GCC_6 = auto(),


class OutputTypes(Enum):
    VPC_CONVERT = auto(),
    VISUAL_STUDIO = auto(),
    MAKEFILE = auto()


# os.path.normpath is not doing this on linux for me, fun
def FixPathSeparator(string: str) -> str:
    if os.name == "nt":
        return string  # .replace("/", "\\")
    else:
        return string.replace("\\", "/")


# just use this for everything probably, works just fine on windows
def PosixPath(string: str) -> str:
    return string.replace("\\", "/")


def FindItemsWithStartingChar(search_list, item):
    found_args = []
    index = 0

    for arg in search_list:
        if search_list[index].startswith( item ):
            arg_value = arg.split( item )[1]
            found_args.append( arg_value )
        index += 1

    if found_args:
        return found_args
    else:
        return None


# TODO: update with try and except
def FindItem( value_list, item, return_value=False ):
    if item in value_list:
        if return_value:
            return value_list[ value_list.index( item ) ]
        else:
            return True
    else:
        return False


# TODO: update with try and except
def FindItemValue( value_list, item, return_value=False ):
    if item in value_list:
        if return_value:
            return value_list[ value_list.index( item ) + 1 ]
        else:
            return True
    else:
        return False


def CreateNewDictValue( dictionary, key, value_type ):
    try:
        dictionary[ key ]
    except KeyError:
        if value_type == "dict":
            dictionary[ key ] = {}
        elif value_type == "list":
            dictionary[ key ] = []
        elif value_type == "str":
            dictionary[ key ] = ""


def CreateNewDictValueBetter(dictionary: dict, key, value_type):
    try:
        dictionary[key]
    except KeyError:
        dictionary[key] = value_type()


def GetAllDictValues(d: dict):
    found_values = []
    for k, v in d.items():
        if isinstance(v, dict):
            found_values.extend(GetAllDictValues(v))
        else:
            # return found_values
            found_values.append(v)
    return found_values


def CreateDirectory(directory):
    try:
        os.makedirs(directory)
        if args.verbose:
            print("Created Directory: " + directory)
    except FileExistsError:
        pass
    except FileNotFoundError:
        pass
    

def CopyFile(src_file, out_file):
    if os.path.isfile(src_file):
        out_dir = os.path.split(out_file)[0]
        CreateDirectory(out_dir)
        shutil.copyfile(src_file, out_file)


DEFAULT_BASEFILE = os.getcwd() + "/_qpc_scripts/_default.qpc_base"


# this is here so i can check arguments globally across files
def ParseArgs():
    valid_project_types = ("vstudio", "makefile", "vpc_convert")

    cmd_parser = argparse.ArgumentParser()

    # maybe change to path? meh
    cmd_parser.add_argument("--rootdir", "-d", default=os.getcwd(), dest="root_dir",
                            help="Set the root directory of the script")
    cmd_parser.add_argument("--basefile", "-b", default=DEFAULT_BASEFILE, dest="base_file",
                            help="Set the root directory of the script")
    cmd_parser.add_argument("--outdir", "-o", default="", dest="out_dir",
                            help="Output directory of qpc scripts with edited folder paths")
    
    # TODO: remove this awful command and use a macro from the project instead
    cmd_parser.add_argument("--project_dir", action="store_true",
                            help="Output project files based on PROJECT_DIR macro, relative to master_file dir")

    cmd_parser.add_argument("--time", action="store_true", help="Print the time taken to parse")
    cmd_parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose console output")
    cmd_parser.add_argument("--force", "-f", action="store_true", help="Force recreate all projects")
    cmd_parser.add_argument("--force_master", "-fm", action="store_true", help="Force recreate master file")
    cmd_parser.add_argument("--hidewarnings", "-w", dest="hide_warnings", action="store_true", help="Suppress all warnings")
    cmd_parser.add_argument("--checkfiles", "-c", dest="check_files", action="store_true", help="Check if any added file exists")
    
    # cmd_parser.add_argument("--platforms", "-p", nargs="+", help="Select plaforms to generate for instead of default")
    cmd_parser.add_argument("--types", "-t", nargs="+", default=(), choices=valid_project_types, help="Project types to generate")
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
arg_parser = ParseArgs()
args = arg_parser.parse_args()

args.root_dir = os.path.normpath(args.root_dir) if os.path.isabs(args.root_dir) else \
    os.path.normpath(os.getcwd() + os.sep + args.root_dir)

args.out_dir = os.path.normpath(args.out_dir) if os.path.isabs(args.out_dir) else \
    os.path.normpath(os.getcwd() + os.sep + args.out_dir)


# convert stuff in args to the enum value
def _ConvertOutputTypes():
    pass


class GlobalSettings:
    def __init__(self):
        pass
