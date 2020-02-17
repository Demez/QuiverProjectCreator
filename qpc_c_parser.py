import re
import os.path

include_pattern = re.compile(r"^[ \t]*#include[ \t]+[\"<]([a-zA-Z0-9\-_\.\/]+)[\">]")


# speeds up this function by an insane amount
INCLUDE_DICT = {
    # "file_path": ["include list"]
}


def decode(data) -> str:
    try:
        return data.decode("UTF-8")
    except UnicodeDecodeError:
        try:
            return data.decode("ASCII")
        except UnicodeDecodeError:
            return data.decode("ANSI")


def GetIncludes(file_path: str) -> list:
    try:
        if file_path in INCLUDE_DICT:
            return INCLUDE_DICT[file_path]
        INCLUDE_DICT[file_path] = _get_includes(file_path)
        return INCLUDE_DICT[file_path]
    except UnicodeDecodeError as F:
        print("UnicodeDecodeError: " + str(F) +
              "\nFile: " + file_path)
        return []


def _get_includes(file_path: str) -> list:
    includes = []
    with open(file_path, 'rb') as f:
        data = f.read()
    text = decode(data)
    lines = text.splitlines()
    for line in lines:
        m = include_pattern.match(line)
        if m and os.path.isfile(m.group(1)):
            includes.append(m.group(1))
    return includes
