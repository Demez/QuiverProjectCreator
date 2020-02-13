import hashlib
import qpc_reader
from qpc_args import args, PROJECT_GENERATORS
from qpc_base import posix_path
# from os import path, sep, getcwd
import os


QPC_DIR = posix_path(os.path.dirname(os.path.realpath(__file__))) + "/"
QPC_GENERATOR_DIR = QPC_DIR + "project_generators/"
QPC_HASH_DIR = QPC_DIR + "hashes/"


def create_directory(directory):
    try:
        os.makedirs(directory)
        if args.verbose:
            print("Created Directory: " + directory)
    except FileExistsError:
        pass
    except FileNotFoundError:
        pass
    

create_directory(QPC_HASH_DIR)


# Source: https://bitbucket.org/prologic/tools/src/tip/md5sum
def MakeHash(filename):
    md5 = hashlib.md5()
    try:
        with open(filename, "rb") as f:
            for chunk in iter(lambda: f.read(128 * md5.block_size), b""):
                md5.update(chunk)
        return md5.hexdigest()
    except FileNotFoundError:
        return ""
    
    
def MakeHashFromString(string: str):
    return hashlib.md5(string.encode()).hexdigest()


BASE_QPC_HASH_LIST = (
    "qpc.py",
    "qpc_base.py",
    "qpc_c_parser.py",
    "qpc_hash.py",
    "qpc_parser.py",
    "qpc_project.py",
    "qpc_reader.py",
    # "qpc_vpc_converter.py",
    "qpc_generator_handler.py",
)
        
        
BASE_QPC_HASHES = {}
for file in BASE_QPC_HASH_LIST:
    BASE_QPC_HASHES[QPC_DIR + file] = MakeHash(QPC_DIR + file)
    
# for file in os.listdir(QPC_GENERATOR_DIR):
for file in PROJECT_GENERATORS:
    BASE_QPC_HASHES[QPC_GENERATOR_DIR + file + ".py"] = MakeHash(QPC_GENERATOR_DIR + file + ".py")


# could make these functions into a class as a namespace
# probably a class, to store hashes of files we've checked before
def CheckHash(project_path: str, file_list=None):
    project_hash_file_path = get_hash_file_path(project_path)
    project_dir = os.path.split(project_path)[0]
    
    if os.path.isfile(project_hash_file_path):
        hash_file = qpc_reader.read_file(project_hash_file_path)
        
        if not hash_file:
            return False
        
        for block in hash_file:
            if block.key == "commands":
                if not _check_commands(project_dir, block.items):
                    return False
                
            elif block.key == "hashes":
                if not _CheckFileHash(project_dir, block.items):
                    return False

            elif block.key == "dependencies":
                pass

            elif block.key == "project_dependencies":
                if not _CheckMasterFileDependencies(project_dir, block.items):
                    return False
                
            elif block.key == "files":
                if not file_list:
                    continue
                if not _CheckFiles(project_dir, block.items, file_list):
                    return False
                
            else:
                # how would this happen
                block.Warning("Unknown Key in Hash: ")

        print("Valid: " + project_path + GetHashFileExt(project_path) + "\n")
        return True
    else:
        if args.verbose:
            print("Hash File does not exist")
        return False
    
    
def get_out_dir(project_hash_file_path):
    if os.path.isfile(project_hash_file_path):
        hash_file = qpc_reader.read_file(project_hash_file_path)
        
        if not hash_file:
            return ""

        commands_block = hash_file.GetItem("commands")
        
        if commands_block is None:
            print("hold up")
        
        working_dir = commands_block.GetItemValues("working_dir")[0]
        out_dir = commands_block.GetItemValues("out_dir")[0]
        return posix_path(os.path.normpath(working_dir + "/" + out_dir))
    
    
def _check_commands(project_dir: str, command_list) -> bool:
    for command_block in command_list:
        if command_block.key == "working_dir":
            directory = os.getcwd()
            if project_dir:
                directory += "/" + project_dir
            # something just breaks here i use PosixPath in the if statement
            directory = posix_path(directory)
            if directory != posix_path(command_block.values[0]):
                return False
        
        elif command_block.key == "out_dir":
            pass
        
        elif command_block.key == "add":
            if sorted(args.add) != sorted(command_block.values):
                return False
        
        elif command_block.key == "remove":
            if sorted(args.remove) != sorted(command_block.values):
                return False
        
        elif command_block.key == "generators":  # generators
            if sorted(args.generators) != sorted(command_block.values):
                return False
        
        elif command_block.key == "macros":
            if sorted(args.macros) != sorted(command_block.values):
                return False
        
        elif command_block.key == "qpc_py_count":
            if len(BASE_QPC_HASHES) != int(command_block.values[0]):
                return False
        
        else:
            command_block.Warning("Unknown Key in Hash: ")
    return True
    
    
def _CheckFileHash(project_dir, hash_list):
    for hash_block in hash_list:
        if os.path.isabs(hash_block.values[0]) or not project_dir:
            project_file_path = os.path.normpath(hash_block.values[0])
        else:
            project_file_path = os.path.normpath(project_dir + "/" + hash_block.values[0])
        
        if hash_block.key != MakeHash(project_file_path):
            if args.verbose:
                print("Invalid: " + hash_block.values[0])
            return False
    return True


def _CheckMasterFileDependencies(project_dir: str, dependency_list: list) -> bool:
    for script_path in dependency_list:
        if os.path.isabs(script_path.key) or not project_dir:
            project_file_path = posix_path(os.path.normpath(script_path.key))
        else:
            project_file_path = posix_path(os.path.normpath(project_dir + "/" + script_path.key))

        project_dep_list = get_project_dependencies(project_file_path)
        if not project_dep_list:
            if script_path.values:  # and not script_path.values[0] == "":
                # all dependencies were removed from it, and we think it has some still, rebuild
                return False
            continue
        elif not script_path.values and project_dep_list:
            # project has dependencies now, and we think it doesn't, rebuild
            return False
        
        project_dep_list.sort()
        if script_path.values[0] != MakeHashFromString(' '.join(project_dep_list)):
            if args.verbose:
                print("Invalid: " + script_path.values[0])
            return False
    return True
    
    
def _CheckFiles(project_dir, hash_file_list, file_list):
    for hash_block in hash_file_list:
        if os.path.isabs(hash_block.values[0]) or not project_dir:
            project_file_path = posix_path(os.path.normpath(hash_block.values[0]))
        else:
            project_file_path = posix_path(os.path.normpath(project_dir + "/" + hash_block.values[0]))
            
        if project_file_path not in file_list:
            if args.verbose:
                print("New project added to master file: " + hash_block.key)
            return False
    return True
    
    
def get_hash_file_path(project_path):
    return posix_path(os.path.normpath(QPC_HASH_DIR + GetHashFileName(project_path)))
    
    
def GetHashFileName(project_path):
    hash_name = project_path.replace("\\", ".").replace("/", ".")
    return hash_name + GetHashFileExt(hash_name)

    
def GetHashFileExt(project_path):
    if os.path.splitext(project_path)[1] == ".qpc":
        return "_hash"
    else:
        return ".qpc_hash"


def get_project_dependencies(project_path: str) -> list:
    project_hash_file_path = get_hash_file_path(project_path)
    dep_list = []

    if os.path.isfile(project_hash_file_path):
        hash_file = qpc_reader.read_file(project_hash_file_path)

        if not hash_file:
            return dep_list

        for block in hash_file:
            if block.key == "dependencies":
                for dep_block in block.items:
                    # maybe get dependencies of that file as well? recursion?
                    dep_list.append(dep_block.key)
                    dep_list.extend(dep_block.values)
                break
    return dep_list


# TODO: change this to use QPC's ToString function in the lexer, this was made before that (i think)
def write_hash_file(project_path: str, out_dir: str = "", hash_list=None, file_list=None,
                    master_file: bool = False, dependencies=None) -> None:
    def ListToString(arg_list):
        if arg_list:
            return '"' + '" "'.join(arg_list) + '"\n'
        return "\n"
    
    with open(get_hash_file_path(project_path), mode="w", encoding="utf-8") as hash_file:
        # write the commands
        hash_file.write("commands\n{\n"
                        '\tworking_dir\t\t"' + os.getcwd().replace('\\', '/') + '"\n'
                        '\tout_dir\t\t\t"' + out_dir.replace('\\', '/') + '"\n')
        if not master_file:
            hash_file.write('\tgenerators\t\t' + ListToString(args.generators) +
                            '\tqpc_py_count\t"' + str(len(BASE_QPC_HASHES)) + "\"\n")
        else:
            hash_file.write('\tadd\t\t\t\t' + ListToString(args.add) +
                            '\tremove\t\t\t' + ListToString(args.remove))
        hash_file.write('\tmacros\t\t\t' + ListToString(args.macros) + "}\n\n")
        
        # write the hashes
        if hash_list:
            hash_file.write("hashes\n{\n")
            
            for project_script_path, hash_value in BASE_QPC_HASHES.items():
                hash_file.write('\t"' + hash_value + '" "' + project_script_path + '"\n')
            hash_file.write('\t\n')
            for project_script_path, hash_value in hash_list.items():
                hash_file.write('\t"' + hash_value + '" "' + project_script_path + '"\n')
                
            hash_file.write("}\n")
        
        if file_list:
            hash_file.write("files\n{\n")
            for script_hash_path, script_path in file_list.items():
                hash_file.write('\t"{0}"\t"{1}"\n'.format(script_path, script_hash_path))
            hash_file.write("}\n")

        if dependencies and not master_file:
            hash_file.write("\ndependencies\n{\n")
            for script_path in dependencies:
                hash_file.write('\t"{0}"\n'.format(script_path))
            hash_file.write("}\n")

        elif dependencies and master_file:
            hash_file.write("\nproject_dependencies\n{\n")
            for project, dependency_tuple in dependencies.items():
                dependency_list = list(dependency_tuple)
                dependency_list.sort()
                if dependency_list:
                    dependency_hash = MakeHashFromString(' '.join(dependency_list))
                    hash_file.write('\t"{0}"\t"{1}"\n'.format(posix_path(project), dependency_hash))
                else:
                    hash_file.write('\t"{0}"\n'.format(posix_path(project)))
            hash_file.write("}\n")
    return

