
# import sys
import os
import argparse
import shutil
import enum


class ConfigurationTypes(enum.Enum):
    static_library = "static_library"
    dynamic_library = "dynamic_library"
    application = "application"


def FindItemsWithStartingChar( search_list, item ):
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


def GetAllDictValues( d ):
    found_values = []
    for k, v in d.items():
        if isinstance(v,dict):
            found_values.extend( GetAllDictValues(v) )
        else:
            # return found_values
            found_values.append( v )
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


# this is here so i can check arguments globally across files
def ParseArgs():
    valid_project_types = ("vstudio", "vscode", "makefile", "vpc_convert")

    cmd_parser = argparse.ArgumentParser(prefix_chars="/")

    # maybe change to path? meh
    cmd_parser.add_argument('/rootdir', '/dir', default=os.getcwd(), dest="root_dir",
                            help='Set the root directory of the script')
    cmd_parser.add_argument('/basefile', default=os.getcwd() + "/_qpc_scripts/_default.qpc_base",
                            dest="base_file", help='Set the root directory of the script')
    cmd_parser.add_argument('/outdir', default="", dest="out_dir",
                            help='Output directory of qpc scripts with edited folder paths')
    
    # TODO: maybe change this command to make it a little better and not a hardcoded macro
    cmd_parser.add_argument('/project_dir', action='store_true',
                            help='Output project files based on PROJECT_DIR macro, relative to master_file dir')

    cmd_parser.add_argument('/time', '/t', action='store_true', help='Print the time taken to parse')
    cmd_parser.add_argument('/verbose', '/v', action='store_true', help='Enable verbose console output')
    cmd_parser.add_argument('/force', '/f', action='store_true', help='Force recreate all projects')
    cmd_parser.add_argument('/hidewarnings', '/hide', dest="hide_warnings", action='store_true',
                            help="Suppress all warnings")
    cmd_parser.add_argument('/checkfiles', '/check', dest="check_files", action='store_true',
                            help="Check if any file that's added actually exists")

    cmd_parser.add_argument('/types', nargs="+", default=(), choices=valid_project_types, help='Project types to generate')
    cmd_parser.add_argument('/add', nargs="+", default=(), help='Add projects or groups to generate')
    cmd_parser.add_argument('/remove', "/rm", default=(), nargs="+", help='Remove projects or groups from generating')
    cmd_parser.add_argument('/macros', nargs="+", default=(), help='Macros to define and set to "1" in projects')

    # TODO: figure out how vpc handles these and recreate it here
    #  might come waaay later since it's very low priority
    # cmd_parser.add_argument('/add_tree', nargs="+", help='Add a project and all projects that depend on it')
    # cmd_parser.add_argument('/add_depend', nargs="+", help='Add a project and all projects that it depends on')
    # Use /h spew final target build set only (no .vcproj created). - what?

    cmd_parser.add_argument('/masterfile', '/master', dest="master_file",
                            help='Create a master file for building all projects with')

    return cmd_parser


# global var
arg_parser = ParseArgs()
args = arg_parser.parse_args()

if os.path.isabs(args.root_dir):
    args.root_dir = os.path.normpath(args.root_dir)
else:
    args.root_dir = os.path.normpath(os.getcwd() + os.sep + args.root_dir)

if os.path.isabs(args.out_dir):
    args.out_dir = os.path.normpath(args.out_dir)
else:
    args.out_dir = os.path.normpath(os.getcwd() + os.sep + args.out_dir)



