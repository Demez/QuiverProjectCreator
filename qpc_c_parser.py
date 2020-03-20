# ==================================================================================================
# This file has a ton of optimizations for avoiding disk usage as much as possible
# It can be a bit messy
# ==================================================================================================

import re
import os.path
from qpc_args import args

include_pattern = re.compile(br"^[ \t]*#include[ \t]+[\"<]([a-zA-Z0-9\-_\./\\]+)[>\"]")

INCLUDE_DICT_DIR = {}
INCLUDE_DICT = {}
# HEADER_DICT = {}
HEADER_PATHS = set()
INVALID_PATHS = set()  # so we don't check the disk for paths that don't exist a million times

INCLUDE_LIST_DIR = {}  # does os.listdir on these include folders
EXCLUDE_DIRS = set()  # these directories don't exist

EXCLUDE_LIST = {"windows.h", "Windows.h", "stdio.h", "crtdbg.h", "minidump.h", "string.h", "stdlib.h", "malloc.h",
                "ctype.h", "wctype.h", "wchar.h", "math.h", "limits.h", "typeinfo", "memory", "stdarg.h", "time.h",
                "shlwapi.h", "algorithm"}


HEADER_EXTS = {
    'h',
    'hh',
    'hpp',
    'h++',
    'hxx'
}


# headers include probably wouldn't speed anything up tbh
def get_includes(file_path: str, include_dirs: list, headers: list) -> list:
    abs_path = os.path.abspath(file_path)  # some files might have the same relative path, but different abs paths
    if abs_path not in INCLUDE_DICT:
        INCLUDE_DICT[abs_path] = _get_includes(abs_path, include_dirs)

    return INCLUDE_DICT[abs_path]

    # this takes slightly longer, but then it won't use absolute directories
    rel_path = os.getcwd().split(args.root_dir)
    rel_path = rel_path[1] if len(rel_path) == 2 else ""

    cwd = "{0}".format("../" * rel_path.count("/"))
    if cwd not in INCLUDE_DICT_DIR:
        INCLUDE_DICT_DIR[cwd] = {}

    if abs_path not in INCLUDE_DICT:
        INCLUDE_DICT[abs_path] = _get_includes(abs_path, include_dirs)

    if abs_path not in INCLUDE_DICT_DIR[cwd]:
        INCLUDE_DICT_DIR[cwd][abs_path] = [os.path.relpath(include) for include in INCLUDE_DICT[abs_path]]

    try:
        return INCLUDE_DICT_DIR[cwd][abs_path]
    except KeyError as F:
        print(F)


def _get_includes(file_path: str, include_dirs: list) -> list:
    includes = []
    include_dirs = [] if include_dirs is None else include_dirs

    if os.path.isfile(file_path):
        with open(file_path, 'rb') as f:
            lines = f.read().splitlines()
    else:
        return []

    include_dirs_abs = []
    for include_dir in include_dirs:
        include_dir_abs = os.path.abspath(include_dir)
        if include_dir_abs in EXCLUDE_DIRS:
            continue
        elif include_dir_abs in INCLUDE_LIST_DIR:
            include_dirs_abs.append(include_dir_abs)
        elif os.path.isdir(include_dir_abs):
            include_dirs_abs.append(include_dir_abs)
            INCLUDE_LIST_DIR[include_dir_abs] = set(os.listdir(include_dir_abs))
        else:
            EXCLUDE_DIRS.add(include_dir_abs)

    def add_header(_header: str, abs_path: str) -> None:
        includes.append(abs_path)
        # HEADER_DICT[_header] = abs_path
        HEADER_PATHS.add(abs_path)

    for line in lines:
        line = line.strip()
        found_header = include_pattern.match(line)
        if found_header:
            found_header = found_header.group(1).decode()

            if found_header in EXCLUDE_LIST:
                continue

            found_header_path, found_header_name = os.path.split(found_header)
            for include_dir in include_dirs_abs:
                path_extended = include_dir + "/" + found_header_path
                if found_header_name in INCLUDE_LIST_DIR[include_dir] or \
                        path_extended in INCLUDE_LIST_DIR and found_header_name in INCLUDE_LIST_DIR[path_extended]:
                    add_header(found_header, include_dir + "/" + found_header)
                    break
            else:
                header_paths = [include_dir + "/" + found_header for include_dir in include_dirs_abs]
                # header_paths = [os.path.abspath(include_dir + "/" + found_header) for include_dir in include_dirs]
                header_paths.insert(0, os.path.abspath(found_header))

                # first check if its in INVALID_PATHS or in HEADER_PATHS, much faster
                for header_path_abs in header_paths:
                    if header_path_abs in INVALID_PATHS:
                        break
                    elif header_path_abs in HEADER_PATHS:
                        add_header(found_header, header_path_abs)
                        break
                else:
                    # then check the disk if none have been found, last resort slow method
                    for header_path_abs in header_paths:
                        if os.path.isfile(header_path_abs):
                            header_dir = os.path.split(header_path_abs)[0]
                            INCLUDE_LIST_DIR[header_dir] = set(os.listdir(header_dir))
                            add_header(found_header, header_path_abs)
                            break
                        # adding it to this so we don't waste time checking the disk
                        # for if the file exists, since we know it doesn't
                        INVALID_PATHS.add(header_path_abs)
                    # else:
                    #     if not args.hide_warnings:
                    #         print("File doesn't exist: " + found_header)
    return includes
