import hashlib
import qpc_reader
from qpc_args import args
from qpc_base import posix_path, get_platform_name, QPC_DIR, QPC_GENERATOR_DIR
from qpc_reader import QPCBlockBase, QPCBlock
from qpc_generator_handler import GENERATOR_PATHS, GENERATOR_LIST
import glob
import os
    

QPC_HASH_DIR = QPC_DIR + "hashes/"


# Source: https://bitbucket.org/prologic/tools/src/tip/md5sum
def make_hash(filename):
    md5 = hashlib.md5()
    try:
        with open(filename, "rb") as f:
            for chunk in iter(lambda: f.read(128 * md5.block_size), b""):
                md5.update(chunk)
        return md5.hexdigest()
    except FileNotFoundError:
        return ""
    
    
def hash_from_string(string: str):
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
        
        
QPC_BASE_HASHES = {}
QPC_GENERATOR_HASHES = {}

for file in BASE_QPC_HASH_LIST:
    QPC_BASE_HASHES[QPC_DIR + file] = make_hash(QPC_DIR + file)
    
for file in GENERATOR_LIST:
    generator = f"{QPC_GENERATOR_DIR}/{file}/{file}.py"
    QPC_GENERATOR_HASHES[generator] = make_hash(generator)
    
QPC_HASHES = {**QPC_BASE_HASHES, **QPC_GENERATOR_HASHES}


# could make these functions into a class as a namespace
# probably a class, to store hashes of files we've checked before
def check_hash(project_path: str) -> bool:
    project_hash_file_path = get_hash_file_path(project_path)
    project_dir = os.path.split(project_path)[0]
    total_blocks = sorted(("commands", "hashes", "glob_files"))
    blocks_found = []
    
    if os.path.isfile(project_hash_file_path):
        hash_file = qpc_reader.read_file(project_hash_file_path)
        
        if not hash_file:
            return False
        
        for block in hash_file:
            if block.key == "commands":
                blocks_found.append(block.key)
                if not _check_commands(project_dir, block.items):
                    return False
                
            elif block.key == "hashes":
                blocks_found.append(block.key)
                if not _check_file_hash(project_dir, block.items):
                    return False

            elif block.key == "dependencies":
                pass

            elif block.key == "glob_files":
                blocks_found.append(block.key)
                if not _check_glob_files(project_dir, block.items):
                    return False
                
            else:
                # how would this happen
                block.warning("Unknown Key in Hash: ")

        if total_blocks == sorted(blocks_found):
            print("Valid: " + project_path + get_hash_file_ext(project_path))
            return True
        return False
    else:
        if args.verbose:
            print("Hash File does not exist")
        return False
    
    
def check_master_file_hash(project_path: str, base_info, has_project_folders: bool) -> bool:
    project_hash_file_path = get_hash_file_path(project_path)
    project_dir = os.path.split(project_path)[0]
    total_blocks = sorted(("commands", "hashes", "files"))
    blocks_found = []
    
    if os.path.isfile(project_hash_file_path):
        hash_file = qpc_reader.read_file(project_hash_file_path)
        
        if not hash_file:
            return False
        
        for block in hash_file:
            if block.key == "commands":
                blocks_found.append(block.key)
                if not _check_commands(project_dir, block.items):
                    return False
                
            elif block.key == "hashes":
                blocks_found.append(block.key)
                if not _check_file_hash(project_dir, block.items):
                    return False
                
            elif block.key == "files":
                blocks_found.append(block.key)
                if not base_info.project_hashes:
                    continue
                if has_project_folders:
                    if not _check_files(project_dir, block.items, base_info.project_hashes, base_info.project_list):
                        return False
                else:
                    if not _check_files(project_dir, block.items, base_info.project_hashes):
                        return False
                
            else:
                # how would this happen
                block.warning("Unknown Key in Hash: ")

        if total_blocks == sorted(blocks_found):
            print("Valid: " + project_path + get_hash_file_ext(project_path))
            return True
        return False
    else:
        if args.verbose:
            print("Hash File does not exist")
        return False
    
    
def get_out_dir(project_hash_file_path):
    if os.path.isfile(project_hash_file_path):
        hash_file = qpc_reader.read_file(project_hash_file_path)
        
        if not hash_file:
            return ""

        commands_block = hash_file.get_item("commands")
        
        if commands_block is None:
            print("hold up")
            return ""
        
        return posix_path(os.path.normpath(commands_block.get_item_values("working_dir")[0]))
        # working_dir = commands_block.get_item_values("working_dir")[0]
        # out_dir = commands_block.get_item_values("out_dir")[0]
        # return posix_path(os.path.normpath(working_dir + "/" + out_dir))
    
    
def _check_commands(project_dir: str, command_list, master_file: bool = False) -> bool:
    total_commands = 4
    commands_found = 0
    
    for command_block in command_list:
        if command_block.key == "working_dir":
            commands_found += 1
            directory = os.getcwd()
            if project_dir:
                directory += "/" + project_dir
            # something just breaks here i use PosixPath in the if statement
            directory = posix_path(directory)
            hash_directory = posix_path(command_block.values[0])
            if hash_directory.endswith("/"):
                hash_directory = hash_directory[:-1]
            if directory != hash_directory:
                return False
        
        elif command_block.key == "out_dir":
            pass
        
        elif command_block.key == "add":
            commands_found += 1
            if sorted(args.add) != sorted(command_block.values):
                return False
        
        elif command_block.key == "remove":
            commands_found += 1
            if sorted(args.remove) != sorted(command_block.values):
                return False
        
        elif command_block.key == "generators":
            commands_found += 1
            if sorted(args.generators) != sorted(command_block.values):
                return False
        
        elif command_block.key == "macros":
            commands_found += 1
            if sorted(args.macros) != sorted(command_block.values):
                return False
        
        elif command_block.key == "qpc_py_count":
            commands_found += 1
            if len(QPC_BASE_HASHES) != int(command_block.values[0]):
                return False
        
        else:
            command_block.warning("Unknown Key in Hash: ")
    return commands_found == total_commands
    
    
def _check_file_hash(project_dir: str, hash_list) -> bool:
    for hash_block in hash_list:
        if os.path.isabs(hash_block.values[0]) or not project_dir:
            project_file_path = os.path.normpath(hash_block.values[0])
        else:
            project_file_path = os.path.normpath(project_dir + "/" + hash_block.values[0])
        
        if hash_block.key != make_hash(project_file_path):
            if args.verbose:
                print("Invalid: " + hash_block.values[0])
            return False
    return True


def _check_master_file_dependencies(project_dir: str, dependency_list: list) -> bool:
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
        if script_path.values[0] != hash_from_string(' '.join(project_dep_list)):
            if args.verbose:
                print("Invalid: " + script_path.values[0])
            return False
    return True
    
    
def _check_files(project_dir, hash_file_list, file_list, project_def_list: tuple = None) -> bool:
    if len(hash_file_list) != len(file_list):
        return False
    for file_block in hash_file_list:
        hash_path = file_block.get_item_values("hash_path")[0]
        folder = file_block.get_item_values("folder")
        folder = folder[0] if folder else ""
        dependency_hash = file_block.get_item_values("dependency_hash")
        dependency_hash = dependency_hash[0] if dependency_hash else ""
        
        if os.path.isabs(hash_path) or not project_dir:
            hash_path = posix_path(os.path.normpath(hash_path))
        else:
            hash_path = posix_path(os.path.normpath(project_dir + "/" + hash_path))
            
        if hash_path not in file_list.values():
            if args.verbose:
                print("New project added to master file: " + file_block.key)
            return False
        
        elif folder and project_def_list:
            for project_def in project_def_list:
                if file_block.key in project_def.script_list and folder != "/".join(project_def.folder_list):
                    return False

        # Now check dependencies
        project_dep_list = get_project_dependencies(file_block.key)
        if not project_dep_list:
            if dependency_hash:  # and not script_path.values[0] == "":
                # all dependencies were removed from it, and we think it has some still, rebuild
                return False
            continue
        elif not dependency_hash and project_dep_list:
            # project has dependencies now, and we think it doesn't, rebuild
            return False

        project_dep_list.sort()
        if dependency_hash != hash_from_string(' '.join(project_dep_list)):
            if args.verbose:
                print("Invalid: " + dependency_hash)
            return False
            
    return True


def _check_glob_files(project_dir: str, file_list: list) -> bool:
    for file_block in file_list:
        file_hash = file_block.key
        file_glob = file_block.values[0]
        
        glob_list = glob.glob(project_dir + "/" + file_glob)
        for index, path in enumerate(glob_list):
            glob_list[index] = posix_path(path)
            
        glob_list.sort()

        if file_hash != hash_from_string(' '.join(glob_list)):
            if args.verbose:
                print("Files found are different: " + file_glob)
            return False
        
    return True
    
    
def get_hash_file_path(project_path) -> str:
    return posix_path(os.path.normpath(QPC_HASH_DIR + get_hash_file_name(project_path)))
    
    
def get_hash_file_name(project_path) -> str:
    hash_name = project_path.replace("\\", ".").replace("/", ".")
    return hash_name + get_hash_file_ext(hash_name)

    
def get_hash_file_ext(project_path) -> str:
    if os.path.splitext(project_path)[1] == ".qpc":
        return "_hash"
    return ".qpc_hash"


def get_project_dependencies(project_path: str, recurse: bool = False) -> list:
    project_hash_file_path = get_hash_file_path(project_path)
    dep_list = set()

    if os.path.isfile(project_hash_file_path):
        hash_file = qpc_reader.read_file(project_hash_file_path)

        if not hash_file:
            return list(dep_list)

        for block in hash_file:
            if block.key == "dependencies":
                for dep_block in block.items:
                    # maybe get dependencies of that file as well? recursion?
                    dep_list.add(dep_block.key)
                    if recurse:
                        dep_list.update(get_project_dependencies(dep_block.key))
                    if dep_block.values and dep_block.values[0] != "":
                        for path in dep_block.values:
                            if path:
                                dep_list.add(path)
                                if recurse:
                                    dep_list.update(get_project_dependencies(dep_block.key))
                break
    return list(dep_list)


def write_project_hash(project_path: str, out_dir: str, hash_list: dict, dependencies: dict, glob_files: list) -> None:
    base_block = QPCBlockBase(project_path)
    
    _write_hash_commands(base_block, out_dir)
    
    hashes = base_block.add_item("hashes", [])
    [hashes.add_item(hash_value, script_path) for script_path, hash_value in QPC_HASHES.items()]
    if hash_list:
        [hashes.add_item(hash_value, script_path) for script_path, hash_value in hash_list.items()]
        
    glob_files_block = base_block.add_item("glob_files", [])
    for path in glob_files:
        found_files = glob.glob(os.path.split(project_path)[0] + "/" + path)
        for index, _path in enumerate(found_files):
            found_files[index] = posix_path(_path)
        found_files.sort()
        glob_files_block.add_item(hash_from_string(' '.join(found_files)), path)

    if dependencies:
        dependencies_block = base_block.add_item("dependencies", [])
        [dependencies_block.add_item(script_path, None) for script_path in dependencies]

    with open(get_hash_file_path(project_path), mode="w", encoding="utf-8") as hash_file:
        hash_file.write(base_block.to_string(True, True))


def write_master_file_hash(project_path: str, base_info, platforms: list, generator_path: str, out_dir: str = ""):
    base_block = QPCBlockBase(project_path)
    
    _write_hash_commands(base_block, out_dir, True)
    
    hashes = base_block.add_item("hashes", [])
    [hashes.add_item(hash_value, script_path) for script_path, hash_value in QPC_BASE_HASHES.items()]
    
    if generator_path in QPC_GENERATOR_HASHES:
        hashes.add_item(QPC_GENERATOR_HASHES[generator_path], generator_path)
    
    info_list = set()
    [info_list.add(base_info.get_base_info(platform)) for platform in platforms]
    if None in info_list:
        info_list.remove(None)
    files = base_block.add_item("files", [])
    
    for info_platform in info_list:
        for project_def in info_platform.projects_to_use:
            folder = "/".join(project_def.folder_list)
            
            for script_path in project_def.script_list:
                script = files.add_item(script_path, [])
                
                if script_path in base_info.project_hashes:
                    hash_path = base_info.project_hashes[script_path]
                    script.add_item("hash_path", hash_path)
                    
                # if project_def.folder_list:
                script.add_item("folder", folder)
                    
                if script_path in base_info.project_dependencies:
                    dependency_list = list(base_info.project_dependencies[script_path])
                    dependency_list.sort()
                    value = hash_from_string(" ".join(dependency_list)) if dependency_list else ""
                    script.add_item("dependency_hash", value)

    with open(get_hash_file_path(project_path), mode="w", encoding="utf-8") as hash_file:
        hash_file.write(base_block.to_string(True, True))
        
        
def _write_hash_commands(base_block: QPCBlockBase, out_dir: str = "", master_file: bool = False) -> None:
    commands = base_block.add_item("commands", [])
    commands.add_item("working_dir", os.getcwd().replace('\\', '/') + "/" + os.path.split(base_block.file_path)[0])
    commands.add_item("out_dir", out_dir.replace('\\', '/'))
    commands.add_item("macros", args.macros)
    
    if master_file:
        commands.add_item("add", args.add)
        commands.add_item("remove", args.remove)
    else:
        commands.add_item("generators", args.generators)
        commands.add_item("qpc_py_count", str(len(QPC_BASE_HASHES)))
       
        
def _write_hash_paths(base_block: QPCBlockBase, hash_file_paths: dict):
    if hash_file_paths:
        files = base_block.add_item("files", [])
        [files.add_item(hash_path, script_path) for script_path, hash_path in hash_file_paths.items()]
