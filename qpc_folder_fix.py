
import os
import qpc_reader
from qpc_base import args, CreateDirectory
# from qpc_parser import CheckFileExists


def GetAllQPCScripts():
    qpc_paths = []
    qpc_base_paths = []
    for subdir, dirs, files in os.walk(args.root_dir):
        for file in files:
            if file.endswith(".qpc"):
                relative_dir = ''.join(os.path.join(subdir, file).split(args.root_dir))[1:]
                qpc_paths.append(relative_dir)
            elif file.endswith(".qpc_base"):
                relative_dir = ''.join(os.path.join(subdir, file).split(args.root_dir))[1:]
                qpc_base_paths.append(relative_dir)
    
    return qpc_paths, qpc_base_paths
    
    
# there's probably a better way to do this, oh well
def GetRelativeSrcDir(out_dir):
    split_root_dir = args.root_dir.split(os.sep)
    split_out_dir = out_dir.split(os.sep)
    src_dir = []
    for depth, out_folder in enumerate(split_out_dir):
        if depth < len(split_root_dir):
            if split_root_dir[depth] != out_folder:
                # how many folders do we need to go out of
                folder_depth = len(split_out_dir) - depth
                trail_back = "{0}".format((".." + os.sep) * folder_depth)[:-1]
                src_dir = [trail_back, *split_root_dir[depth:]]
                break
    return os.sep.join(src_dir)


def FixFile(qpc_path, qpc_file):
    # first, add a PROJECT_DIR macro
    AddProjectDirMacro(qpc_path, qpc_file)
    
    config = qpc_file.GetItem("configuration")
    if config:
        general_list = config.GetAllItems("general")
        for general_block in general_list:
            include_directories_list = general_block.GetAllItems("include_directories")
            for include_directories in include_directories_list:
                FixDirectories(include_directories)
                
            library_directories_list = general_block.GetAllItems("library_directories")
            for library_directories in library_directories_list:
                FixDirectories(library_directories)
                
    FixMacroUsages(qpc_file)
    
    file_block_list = qpc_file.GetAllItems("files")
    if file_block_list:
        for file_block in file_block_list:
            FixFoldersInFilesBlock(file_block)
            
    with open(GetOutputPath(qpc_path), mode="w", encoding="utf8") as new_file:
        new_file.write(qpc_file.ToString())


# removes SRCDIR macro and adds $BASE_SCRIPTS macro
def FixMacroUsages(qpc_file):
    for block in qpc_file.items:
        if "$SRCDIR" in block.key:
            block.key = RemoveSrcDirMacro(block.key)
        for index, value in enumerate(block.values):
            if "$SRCDIR" in value:
                block.values[index] = RemoveSrcDirMacro(value)

        if "_qpc_scripts" in block.key:
            block.key = FixQPCScriptsPath(block.key)
        for index, value in enumerate(block.values):
            if "_qpc_scripts" in value:
                block.values[index] = FixQPCScriptsPath(value)
            
        if block.items:
            FixMacroUsages(block)


def RemoveSrcDirMacro(string):
    if "$SRCDIR/" in string:
        return ''.join(string.split("$SRCDIR/"))
    else:
        return ''.join(string.split("$SRCDIR"))


def FixQPCScriptsPath(string):
    return MACRO_BASE_SCRIPTS.join(string.split("_qpc_scripts"))


def AddProjectDirMacro(qpc_path, qpc_file):
    for block in qpc_file.items:
        if block.key == "macro":
            if block.values[0] in {"SRCDIR", "SRC_DIR"}:
                index = qpc_file.GetIndexOfItem(block)
                qpc_file.AddItemAtIndex(index + 1, "macro",
                                        ["PROJECT_DIR", '"' + os.path.split(qpc_path)[0].replace("\\", "/") + '"'])
                qpc_file.items.remove(block)
                return
    qpc_file.AddItemAtIndex(0, "macro", ["PROJECT_DIR", '"' + os.path.split(qpc_path)[0].replace("\\", "/") + '"'])


def FixFoldersInFilesBlock(file_block):
    for file_path in file_block.items:
        if file_path.key == "folder":
            FixFoldersInFilesBlock(file_path)
        else:
            file_path.key = ProjectDirFilePath(file_path.key.replace("\\", "/"))
            for index, file_path_value in enumerate(file_path.values):
                file_path.values[index] = ProjectDirFilePath(file_path_value.replace("\\", "/"))


# fixes include_directories, library_directories, and libraries
def FixDirectories(block):
    for path_block in block.items:
        path_block.key = ProjectDirFilePath(path_block.key.replace("\\", "/"))
        for index, file_path_value in enumerate(path_block.values):
            path_block.values[index] = ProjectDirFilePath(file_path_value.replace("\\", "/"))

            
def ProjectDirFilePath(path):
    if path.startswith("-"):
        return path
    elif path.startswith('"'):
        if len(path) > 2 and path[1] != "$":
            return '"$PROJECT_DIR/' + path[1:-1] + '"'
    elif not path.startswith("$"):
        return "$PROJECT_DIR/" + path
    return path


def GetOutputPath(qpc_path):
    return args.out_dir + os.sep + os.path.split(qpc_path)[1]


def FixBaseFile(qpc_path, qpc_file):
    # first, add a BASE_SCRIPTS macro
    AddQPCScriptsFolderMacro(os.path.split(qpc_path)[0], qpc_file)
    
    include_list = qpc_file.GetAllItems("include")
    for include_block in include_list:
        if include_block.values and "_qpc_scripts" in include_block.values[0]:
            include_block.values[0] = FixQPCScriptsPath(include_block.values[0])
    
    with open(GetOutputPath(qpc_path), mode="w", encoding="utf8") as new_file:
        new_file.write(qpc_file.ToString())
        
        
def AddQPCScriptsFolderMacro(script_path, qpc_file):
    split_root_dir = args.root_dir.split(os.sep)
    split_out_dir = args.out_dir.split(os.sep)
    src_dir = []
    for depth, out_folder in enumerate(split_out_dir):
        if depth < len(split_root_dir):
            if split_root_dir[depth] != out_folder:
                # how many folders do we need to go out of
                folder_depth = len(split_out_dir) - depth
                trail_back = "{0}".format("../" * folder_depth)[:-1]
                src_dir = [trail_back, script_path.replace("\\", "/")]
                break
                
    bad_comment = "// Relative to the source directory"
    qpc_file.AddItemAtIndex(0, "macro", [MACRO_BASE_SCRIPTS[1:], '"' + "/".join(src_dir) + '"', bad_comment])
    return
    
    
def FixProjectDefinition(block):
    # fix values[1:] and items
    for sub_block in block.items:
        FixProjectDefinition(sub_block)
    
    
def Main():
    qpc_path_list, qpc_base_path_list = GetAllQPCScripts()
    
    if qpc_path_list:
        print("\nFixing QPC Scripts")
        
        for qpc_path in qpc_path_list:
            # TODO: maybe make a keep comments option in ReadFile()? otherwise, commented out files won't be kept
            print("Converting: " + qpc_path)
            qpc_file = qpc_reader.ReadFile(qpc_path, keep_quotes=True)
            FixFile(qpc_path, qpc_file)
    
    if qpc_base_path_list:
        print("\nFixing QPC Base Scripts")
        
        for qpc_base_path in qpc_base_path_list:
            # TODO: maybe make a keep comments option in ReadFile()? otherwise, commented out files won't be kept
            print("Converting: " + qpc_base_path)
            qpc_base_file = qpc_reader.ReadFile(qpc_base_path, keep_quotes=True)
            FixBaseFile(qpc_base_path, qpc_base_file)


if __name__ == "__main__":
    os.chdir(args.root_dir)
    MACRO_BASE_SCRIPTS = "$BASE_SCRIPTS"
    SRC_DIR = GetRelativeSrcDir(args.out_dir)
    CreateDirectory(args.out_dir)
    Main()
