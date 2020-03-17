import re
import os.path

include_pattern = re.compile(br"^[ \t]*#include[ \t]+[\"<]([a-zA-Z0-9\-_\./\\]+)[>\"]")

INCLUDE_DICT = {}
HEADER_DICT = {}
HEADER_PATHS = set()
EXCLUDE_LIST = {"windows.h", "stdio.h", "crtdbg.h", "minidump.h"}


def get_includes(file_path: str, include_dirs: list, files: list) -> list:
    abs_path = os.path.abspath(file_path)  # some files might have the same relative path, but different abs paths
    try:
        return INCLUDE_DICT[abs_path]
    except KeyError:
        INCLUDE_DICT[abs_path] = _get_includes(abs_path, include_dirs, files)
        return INCLUDE_DICT[abs_path]


def _get_includes(file_path: str, include_dirs: list, headers: list) -> list:
    includes = []
    include_dirs = [] if include_dirs is None else include_dirs

    if os.path.isfile(file_path):
        with open(file_path, 'rb') as f:
            lines = f.read().splitlines()
    else:
        return []

    def add_header(_header, path) -> None:
        includes.append(path)
        HEADER_DICT[_header] = path
        HEADER_PATHS.add(path)

    for line in lines:
        line = line.strip()
        # if not line.startswith(b"#include"):
        #     continue
        found_header = include_pattern.match(line)
        if found_header:
            found_header = found_header.group(1).decode()

            if found_header in EXCLUDE_LIST:
                continue

            if found_header in HEADER_DICT:
                includes.append(HEADER_DICT[found_header])
                continue

            if found_header in HEADER_PATHS or os.path.isfile(found_header):
                add_header(found_header, found_header)
                continue

            for include_dir in include_dirs:
                header_path = include_dir + "/" + found_header
                if header_path in HEADER_PATHS or os.path.isfile(header_path):
                    add_header(found_header, header_path)
                    break
    return includes
