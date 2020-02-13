import re
import os.path

include_pattern = re.compile(r"^[ \t]*#include[ \t]+[\"<]([a-zA-Z0-9\-_\.\/]+)[\">]")


def get_includes(file_path: str) -> list:
    includes = []
    with open(file_path, 'r') as f:
        lines = f.read().split('\n')
        for line in lines:
            m = include_pattern.match(line)
            if m and os.path.isfile(m.group(1)):
                includes.append(m.group(1))
    return includes
