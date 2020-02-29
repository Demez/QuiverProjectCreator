import re
import os.path

include_pattern = re.compile(br"^[ \t]*#include[ \t]+[\"<]([a-zA-Z0-9\-_\./\\]+)[>\"]")


INCLUDE_DICT = {}
                
                
def GetIncludes(file_path: str, include_dirs: list = None) -> list:
    try:
        return INCLUDE_DICT[file_path]
    except KeyError:
        INCLUDE_DICT[file_path] = _get_includes(file_path, include_dirs)
        return INCLUDE_DICT[file_path]
                
    
def _get_includes(file_path: str, include_dirs: list = None) -> list:
    includes = []
    include_dirs = [] if include_dirs is None else include_dirs

    try:
        with open(file_path, 'rb') as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print(f"Warning: File does not exist: {file_path}")
        return []

    for line in lines:
        match = include_pattern.match(line)
        if match:
            header = match.group(1).decode()
            for include_dir in include_dirs:
                header_path = include_dir + "/" + header
                if os.path.isfile(header_path):
                    includes.append(header_path)
                    break
    return includes


