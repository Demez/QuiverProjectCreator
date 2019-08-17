import re


include_pattern = re.compile(r'^[ \t]*#include[ \t]+"(a-zA-Z\-_\./)"')

def GetIncludes(file_path):
    includes = []
    with open(file_path, 'r') as f:
        lines = f.read().split('\n')
        for line in lines:
            m = include_pattern.match(line)
            if m:
                includes.append(m.group(1))
    return includes
