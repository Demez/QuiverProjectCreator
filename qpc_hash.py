import hashlib
import qpc_reader
from qpc_base import args, CreateDirectory
from os import path, sep, getcwd


QPC_DIR = path.dirname(path.realpath(__file__)) + sep
QPC_HASH_DIR = QPC_DIR + "hashes" + sep
CreateDirectory(QPC_HASH_DIR)


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


BASE_QPC_HASH_LIST = [
    "qpc.py",
    "qpc_base.py",
    "qpc_c_parser.py",
    "qpc_hash.py",
    "qpc_makefile.py",
    "qpc_parser.py",
    "qpc_reader.py",
    "qpc_visual_studio.py",
    "qpc_vpc_converter.py",
    "qpc_writer.py",
]
        
        
BASE_QPC_HASHES = {}
for file in BASE_QPC_HASH_LIST:
    BASE_QPC_HASHES[MakeHash(QPC_DIR + file)] = QPC_DIR + file


def CheckHash(project_path):
    project_hash_file_path = GetHashFilePath(project_path)
    project_dir = path.split(project_path)[0]
    
    # open the hash file if it exists,
    # run MakeHash on every file there
    # and check if it matches what MakeHash returned
    if path.isfile(project_hash_file_path):
        hash_file = qpc_reader.ReadFile(project_hash_file_path)
        
        for block in hash_file:
            if block.key == "commands":
                if not _CheckCommands(project_dir, block.items):
                    return False
                
            elif block.key == "hashes":
                if not _CheckFileHash(project_dir, block.items):
                    return False
                
            else:
                block.Unknown()

        print("Valid: " + project_path + GetHashFileExt(project_path) + "\n")
        return True
    else:
        if args.verbose:
            print("Hash File does not exist")
        return False
    
    
def _CheckCommands(project_dir, command_list):
    for command_block in command_list:
        if command_block.key == "working_dir":
            directory = getcwd()
            if project_dir:
                directory += sep + project_dir
            if directory != path.normpath(command_block.values[0]):
                return False
        
        elif command_block.key == "add":
            if sorted(args.add) != sorted(command_block.values):
                return False
        
        elif command_block.key == "remove":
            if sorted(args.remove) != sorted(command_block.values):
                return False
        
        elif command_block.key == "types":
            if sorted(args.types) != sorted(command_block.values):
                return False
        
        elif command_block.key == "macros":
            if sorted(args.macros) != sorted(command_block.values):
                return False
        
        else:
            command_block.Unknown()
    return True
    
    
def _CheckFileHash(project_dir, hash_list):
    for hash_block in hash_list:
        if path.isabs(hash_block.values[0]) or not project_dir:
            project_file_path = path.normpath(hash_block.values[0])
        else:
            project_file_path = path.normpath(project_dir + sep + hash_block.values[0])
        
        if hash_block.key != MakeHash(project_file_path):
            if args.verbose:
                print("Invalid: " + hash_block.values[0])
            return False
    return True
    
    
def GetHashFilePath(project_path):
    return path.normpath(QPC_HASH_DIR + GetHashFileName(project_path))
    
    
def GetHashFileName(project_path):
    hash_name = project_path.replace(sep, ".")
    return hash_name + GetHashFileExt(hash_name)

    
def GetHashFileExt(project_path):
    if path.splitext(project_path)[1] == ".qpc":
        return "_hash"
    else:
        return ".qpc_hash"


def WriteHashFile(project_path, hash_list, master_file=False):
    def ListToString(arg_list):
        if arg_list:
            return '"' + '" "'.join(arg_list) + '"\n'
        return "\n"
    
    with open(GetHashFilePath(project_path), mode="w", encoding="utf-8") as hash_file:
        # write the commands
        hash_file.write("commands\n{\n")
        hash_file.write('\t"working_dir"\t"' + getcwd().replace('\\', '/') + '"\n')
        hash_file.write('\t"add"\t\t\t' + ListToString(args.add))
        hash_file.write('\t"remove"\t\t' + ListToString(args.remove))
        if not master_file:
            hash_file.write('\t"types"\t\t\t' + ListToString(args.types))
        hash_file.write('\t"macros"\t\t' + ListToString(args.macros))
        hash_file.write("}\n\n")
        
        # write the hashes
        hash_file.write("hashes\n{\n")
        for project_script_path, hash_value in hash_list.items():
            hash_file.write('\t"' + hash_value + '" "' + project_script_path + '"\n')
        hash_file.write("}\n")
    return

