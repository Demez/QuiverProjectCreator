import os
import qpc_base as base
import qpc_reader as reader
import argparse

# this file is awful, good luck adding to it
# some random notes:

# the configuration blocks are merged into one main config
#   depending on the configuration name, it adds a condition for every option in it
#   it also adds a condition for every option if the config group has a condition

# base files are read differently, was trying something different
#   but then i realized that it's very very dumb
#   instead, it modifies the project blocks and writes them


# TODO: add dependencies here, they will have to be hard coded, but i could care less


# Global Variables
EVENTS = {"pre_link", "pre_build", "post_build"}

MACRO_CONVERT = {
    "SRCDIR": "SRC_DIR",
    "OUTBINDIR": "OUT_BIN_DIR",
    "OUTBINNAME": "OUT_BIN_NAME",
    "OUTLIBDIR": "OUT_LIB_DIR",
    "OUTLIBNAME": "OUT_LIB_NAME",
    "PROJECTNAME": "PROJECT_NAME",
    "LOADADDRESS_DEVELOPMENT": "LOAD_ADDRESS_DEVELOPMENT",
    "LOADADDRESS_RETAIL": "LOAD_ADDRESS_RETAIL",
    "PLATSUBDIR": "PLATFORM",
}

VPC_CONFIG_IGNORE_LIST = [
    "$additionalprojectdependencies",
    "$entrypoint",
    "$version",
    
    # posix stuff
    "$symbolvisibility",
]

OPTION_NAME_CONVERT_DICT = {
    "$outputdirectory": "out_dir",
    "$intermediatedirectory": "int_dir",
    "$configurationtype": "configuration_type",
    
    "$additionalincludedirectories": "include_directories",
    "$additionallibrarydirectories": "library_directories",
    
    "$additionaldependencies": "libraries",
    "$compileas": "language",
    "$platformtoolset": "compiler",
    
    "$preprocessordefinitions": "preprocessor_definitions",
    "$characterset": "preprocessor_definitions",
    
    "$commandline": "command_line",
    "$excludedfrombuild": "use_in_build",
    
    "$create/useprecompiledheader": "precompiled_header",
    "$create/usepchthroughfile": "precompiled_header_file",
    "$precompiledheaderfile": "precompiled_header_out_file",
    "$precompiledheaderoutputfile": "precompiled_header_out_file",
    
    "$importlibrary": "import_library",
    "$ignoreimportlibrary": "ignore_import_library",
    "$ignorespecificlibrary": "ignore_libraries",
    
    "$outputfile": "output_file",
    "$generateprogramdatabasefile": "debug_file",
    
    # all just options stuff
    "$additionaloptions": "options",
    "$disablespecificwarnings": "options",
    "$multiprocessorcompilation": "options",
    "$imagehassafeexceptionhandlers": "options",
    "generatemanifest": "options",
    "useunicoderesponsefiles": "options",
    "enablebrowseinformation": "options",
    "generatexlmdocumentationfiles": "options",
    "buffersecuritycheck": "options",
    "enablec++exceptions": "options",
    "randomizedbaseaddress": "options",
    "basicruntimechecks": "options",
    
    # posix stuff:
    "$optimizerlevel": "options",  # idk if this will work, need to test
    
    "$gcc_extracompilerflags": "options",
    "$gcc_extralinkerflags": "options",
}

OPTION_VALUE_CONVERT_DICT = {
    "Application (.exe)": "application",
    "Dynamic Library (.dll)": "dynamic_library",
    "Dynamic Library (.xex)": "dynamic_library",
    "Static Library (.lib)": "static_library",
    
    "Not Using Precompiled Headers": "none",
    "Automatically Generate (/YX)": "create",
    "Create Precompiled Header (/Yc)": "create",
    "Create (/Yc)": "create",
    "Use Precompiled Header (/Yu)": "use",
    "Use (/Yu)": "use",
    
    "Compile as C Code (/TC)": "c",
    "Compile as C++ Code (/TP)": "cpp",
    
    "TRUE": "true",
    "True": "true",
    "False": "false",
    "Yes": "true",
    "No": "false",
    
    "v90": "msvc_v90",
    "v100": "msvc_v100",
    "v110": "msvc_v110",
    "v120": "msvc_v120",
    "v140": "msvc_v140",
    "v141": "msvc_v141",
    "v142": "msvc_v142",
    
    # preprocessor defs
    "Use Multi-Byte Character Set": "MBCS",
    "Use Unicode Character Set": "_MBCS",
    
    # maybe move to somewhere else? this is WAY too general
    # "True": "/MP",
}

# TODO: do the same here in vstudio, but convert the other way around to vs2019 options
#  and then search for that converted option value in all the options?
CMD_CONVERT = {
    # preprocessor defs
    # "Use Multi-Byte Character Set": "MBCS",
    # "Use Unicode Character Set": "_MBCS",
    
    # commands
    "C7 Compatible (/Z7)": "/Z7",
    "Program Database (/Zi)": "/Zi",
    "Program Database for Edit & Continue (/ZI)": "/ZI",
    
    "Common Language RunTime Support (/clr)": "/clr",
    "Pure MSIL Common Language RunTime Support (/clr:pure)": "/clr:pure",
    "Safe MSIL Common Language RunTime Support (/clr:safe)": "/clr:safe",
    "Common Language RunTime Support, Old Syntax (/clr:oldSyntax)": "/clr:oldSyntax",
    
    "Off: Turn Off All Warnings (/W0)": "/W0",
    "Level 1 (/W1)": "/W1",
    "Level 2 (/W2)": "/W2",
    "Level 3 (/W3)": "/W3",
    "Level 4 (/W4)": "/W4",
    "EnableAllWarnings (/Wall)": "/Wall",
    
    "No (/WX-)": "/WX-",
    "Yes (/WX)": "/WX",  # TODO: check if this is correct
    
    "No (/INCREMENTAL:NO)": "/INCREMENTAL:NO",
    
    "Yes (/NOLOGO)": "/NOLOGO",
    "Yes (/Gy)": "/Gy",
    "Yes (/GF)": "/GF",
    "Yes (/Gm)": "/Gm",
    "Yes (/GR)": "/GR",
    "Yes (/Oi)": "/Oi",
    "Yes (/MAP)": "/MAP",
    "Yes (/Wp64)": "/Wp64",
    
    "Yes (/Zc:forScope)": "/Zc:forScope",
    "Yes (/Zc:wchar_t)": "/Zc:wchar_t",
    
    "Yes (/DEBUG)": "/DEBUG",
    
    "Single-threaded (/ML)": "/ML",
    "Single-threaded Debug (/MLd)": "/MLd",
    
    "Include All Browse Information (/FR)": "/FR",
    
    "Disabled (/Od)": "/Od",
    "Minimize Size (/O1)": "/O1",
    "Maximize Speed (/O2)": "/O2",
    "Full Optimization (/Ox)": "/Ox",
    
    "Disabled (/Ob0)": "/Ob0",
    "Only __inline (/Ob1)": "/Ob1",
    "Any Suitable (/Ob2)": "/Ob2",
    
    "Favor Fast Code (/Ot)": "/Ot",
    "Favor Small Code (/Os)": "/Os",
    
    "Yes With SEH Exceptions (/EHa)": "/EHa",
    "Yes (/EHsc)": "/EHsc",
    "Yes with Extern C functions (/EHs)": "/EHs",
    
    "Stack Frames (/RTCs)": "/RTCs",
    "Uninitialized Variables (/RTCu)": "/RTCu",
    "Both (/RTC1, equiv. to /RTCsu)": "/RTC1",
    "Both (/RTC1, equiv. to /RTCsu) (/RTC1)": "/RTC1",
    
    "Multi-threaded (/MT)": "/MT",
    "Multi-threaded Debug (/MTd)": "/MTd",
    "Multi-threaded DLL (/MD)": "/MD",
    "Multi-threaded Debug DLL (/MDd)": "/MDd",
    
    "1 Byte (/Zp1)": "/Zp1",
    "2 Bytes (/Zp2)": "/Zp2",
    "4 Bytes (/Zp4)": "/Zp4",
    "8 Bytes (/Zp8)": "/Zp8",
    "16 Bytes (/Zp16)": "/Zp16",
    
    "Streaming SIMD Extensions (/arch:SSE)": "/arch:SSE",
    "Streaming SIMD Extensions (/arch:SSE) (/arch:SSE)": "/arch:SSE",
    "Streaming SIMD Extensions 2 (/arch:SSE2)": "/arch:SSE2",
    "Streaming SIMD Extensions 2 (/arch:SSE2) (/arch:SSE2)": "/arch:SSE2",
    
    "Precise (/fp:precise)": "/fp:precise",
    "Strict (/fp:strict)": "/fp:strict",
    "Fast (/fp:fast)": "/fp:fast",
    
    # "Create Precompiled Header (/Yc)": "/Yc",
    # "Create (/Yc)": "/Yc",
    # "Use Precompiled Header (/Yu)": "/Yu",
    # "Use (/Yu)": "/Yu",
    
    "Assembly-Only Listing (/FA)": "/FA",
    "Assembly With Machine Code (/FAc)": "/FAc",
    "Assembly With Source Code (/FAs)": "/FAs",
    "Assembly, Machine Code and Source (/FAcs)": "/FAcs",
    
    "__cdecl (/Gd)": "/Gd",
    "__fastcall (/Gr)": "/Gr",
    "__stdcall (/Gz)": "/Gz",
    
    # skipping CompileAs, since language sets that
    
    "Do Not Send Report (/errorReport:none)": "/errorReport:none",
    "Prompt Immediately (/errorReport:prompt)": "/errorReport:prompt",
    "Queue For Next Login (/errorReport:queue)": "/errorReport:queue",
    "Send Automatically (/errorReport:send)": "/errorReport:send",
    
    "Do Not Send Report (/ERRORREPORT:NONE)": "/ERRORREPORT:NONE",
    "Prompt Immediately (/ERRORREPORT:PROMPT)": "/ERRORREPORT:PROMPT",
    "Queue For Next Login (/ERRORREPORT:QUEUE)": "/ERRORREPORT:QUEUE",
    "Send Automatically (/ERRORREPORT:SEND)": "/ERRORREPORT:SEND",
    
    "MachineARM (/MACHINE:ARM)": "/MACHINE:ARM",
    "MachineEBC (/MACHINE:EBC)": "/MACHINE:EBC",
    "MachineIA64 (/MACHINE:IA64)": "/MACHINE:IA64",
    "MachineMIPS (/MACHINE:MIPS)": "/MACHINE:MIPS",
    "MachineMIPS16 (/MACHINE:MIPS16)": "/MACHINE:MIPS16",
    "MachineMIPSFPU (/MACHINE:MIPSFPU)": "/MACHINE:MIPSFPU",
    "MachineMIPSFPU16 (/MACHINE:MIPSFPU16)": "/MACHINE:MIPSFPU16",
    "MachineSH4 (/MACHINE:SH4)": "/MACHINE:SH4",
    "MachineTHUMB (/MACHINE:THUMB)": "/MACHINE:THUMB",
    "MachineX64 (/MACHINE:X64)": "/MACHINE:X64",
    "MachineX86 (/MACHINE:X86)": "/MACHINE:X86",
    
    # skipping show progress
    
    "Enabled (/FORCE)": "/FORCE",
    "Multiply Defined Symbol Only (/FORCE:MULTIPLE)": "/FORCE:MULTIPLE",
    "Undefined Symbol Only (/FORCE:UNRESOLVED)": "/FORCE:UNRESOLVED",
    
    "Enabled (/FUNCTIONPADMIN)": "/FUNCTIONPADMIN",
    "X86 Image Only (/FUNCTIONPADMIN:5)": "/FUNCTIONPADMIN:5",
    "X64 Image Only (/FUNCTIONPADMIN:6)": "/FUNCTIONPADMIN:6",
    "Itanium Image Only (/FUNCTIONPADMIN:16)": "/FUNCTIONPADMIN:16",
    
    "asInvoker (/level='asInvoker')": "/level='asInvoker'",
    "highestAvailable (/level='highestAvailable')": "/level='highestAvailable'",
    "requireAdministrator (/level='requireAdministrator')": "/level='requireAdministrator'",
    
    "No runtime tracking and enable optimizations (/ASSEMBLYDEBUG:DISABLE)": "/ASSEMBLYDEBUG:DISABLE",
    "No (/ASSEMBLYDEBUG:DISABLE)": "/ASSEMBLYDEBUG:DISABLE",
    "Runtime tracking and disable optimizations (/ASSEMBLYDEBUG)": "/ASSEMBLYDEBUG",
    "Yes (/ASSEMBLYDEBUG)": "/ASSEMBLYDEBUG",
    
    "Console (/SUBSYSTEM:CONSOLE)": "/SUBSYSTEM:CONSOLE",
    "Windows (/SUBSYSTEM:WINDOWS)": "/SUBSYSTEM:WINDOWS",
    "Native (/SUBSYSTEM:NATIVE)": "/SUBSYSTEM:NATIVE",
    "EFI Application (/SUBSYSTEM:EFI_APPLICATION)": "/SUBSYSTEM:EFI_APPLICATION",
    "EFI Boot Service Driver (/SUBSYSTEM:EFI_BOOT_SERVICE_DRIVER)": "/SUBSYSTEM:EFI_BOOT_SERVICE_DRIVER",
    "EFI ROM (/SUBSYSTEM:EFI_ROM)": "/SUBSYSTEM:EFI_ROM",
    "EFI Runtime (/SUBSYSTEM:EFI_RUNTIME_DRIVER)": "/SUBSYSTEM:EFI_RUNTIME_DRIVER",
    "WindowsCE (/SUBSYSTEM:WINDOWSCE)": "/SUBSYSTEM:WINDOWSCE",
    "POSIX (/SUBSYSTEM:POSIX)": "/SUBSYSTEM:POSIX",
    
    "Do Not Support Addresses Larger Than 2 Gigabytes (/LARGEADDRESSAWARE:NO)": "/LARGEADDRESSAWARE:NO",
    "No (/LARGEADDRESSAWARE:NO)": "/LARGEADDRESSAWARE:NO",
    "Support Addresses Larger Than 2 Gigabytes (/LARGEADDRESSAWARE)": "/LARGEADDRESSAWARE",
    "Yes (/LARGEADDRESSAWARE)": "/LARGEADDRESSAWARE",
    
    "Driver (/DRIVER)": "/DRIVER",
    "Up Only (/DRIVER:UPONLY)": "/DRIVER:UPONLY",
    "WDM (/DRIVER:WDM)": "/DRIVER:WDM",
    
    "Do Not Remove Redundant COMDATs (/OPT:NOICF)": "/OPT:NOICF",
    "No (/OPT:NOICF)": "/OPT:NOICF",
    "Remove Redundant COMDATs (/OPT:ICF)": "/OPT:ICF",
    "Yes (/OPT:ICF)": "/OPT:ICF",
    
    "Use Link Time Code Generation": "/ltcg",
    "Use Link Time Code Generation (/ltcg)": "/ltcg",
    "Profile Guided Optimization - Instrument (/ltcg:pginstrument)": "/ltcg:pginstrument",
    "Profile Guided Optimization - Optimize (/ltcg:pgoptimize)": "/ltcg:pgoptimize",
    "Profile Guided Optimization - Update (/ltcg:pgupdate)": "/ltcg:pgupdate",
    
    "Generate a relocation section (/FIXED:NO)": "/FIXED:NO",
    "No (/FIXED:NO)": "/FIXED:NO",
    "Image must be loaded at a fixed address (/FIXED)": "/FIXED",
    "Yes (/FIXED)": "/FIXED",
    
    "Default threading attribute (/CLRTHREADATTRIBUTE:NONE)": "/CLRTHREADATTRIBUTE:NONE",
    "MTA threading attribute (/CLRTHREADATTRIBUTE:MTA)": "/CLRTHREADATTRIBUTE:MTA",
    "STA threading attribute (/CLRTHREADATTRIBUTE:STA)": "/CLRTHREADATTRIBUTE:STA",
    
    "Force IJW image (/CLRIMAGETYPE:IJW)": "/CLRIMAGETYPE:IJW",
    "Force pure IL image (/CLRIMAGETYPE:PURE)": "/CLRIMAGETYPE:PURE",
    "Force safe IL image (/CLRIMAGETYPE:SAFE)": "/CLRIMAGETYPE:SAFE",
    
    "Enabled (/CLRSupportLastError)": "/CLRSupportLastError",
    "Disabled (/CLRSupportLastError:NO)": "/CLRSupportLastError:NO",
    "System Dlls Only (/CLRSupportLastError:SYSTEMDLL)": "/CLRSupportLastError:SYSTEMDLL",
    
    # "aaaaaaaa": "/aaaaaaaa",
    
    "Default image type": "",
    "No Listing": "",
    "Not Using Precompiled Headers": "",
    "Not Set": "",
    "No": "",
    "Neither": "",
    "Default": "",
    "No Common Language RunTime Support": "",
}

CONFIG_GROUP_CONVERT_DICT = {
    "$compileas": "general",
    "$additionalincludedirectories": "general",
    "$additionallibrarydirectories": "general",
    
    "$characterset": "compiler",
}

VS_BOOL_CONVERT = {
    "$imagehassafeexceptionhandlers": {
        "true": "/SAFESEH",
        "false": "/SAFESEH:NO",
    },
}


# idfk what to call this function
def prepare_vpc_file(project_script_path):
    project_dir, project_filename = os.path.split(project_script_path)
    project_name = os.path.splitext(project_filename)[0]
    project_file = reader.read_file(project_script_path)
    return project_file, project_dir, project_name


def get_vpc_scripts(root_dir):
    vpc_paths = []
    vgc_paths = []
    for subdir, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".vpc"):
                vpc_paths.append(os.path.join(subdir, file))
            elif file.endswith(".vgc"):
                vgc_paths.append(os.path.join(subdir, file))
    
    return vgc_paths, vpc_paths


# you could just read it and then replace the keys directly probably,
# would keep all comments that way at least
def convert_vgc(vgc_dir, vgc_filename, vgc_project):
    qpc_project_path = vgc_dir + os.sep + vgc_filename + ".qpc"
    qpc_base_file = []
    
    def AddSpace(string):
        if qpc_base_file:
            if (not qpc_base_file[-1].startswith(string) or qpc_base_file[-1] == "}") and qpc_base_file[-1] != "":
                qpc_base_file.append("")
    
    for block_index, project_block in enumerate(vgc_project):
        key = project_block.key.casefold()  # compare with ignoring case
        values = project_block.values
        
        if key in ("$macro", "$conditional", "$project", "$group", "$include"):
            if key in ("$project", "$group"):
                AddSpace(key[1:])
                qpc_base_file.append(key[1:])
                if project_block.values:
                    qpc_base_file[-1] += ' "' + '" "'.join(project_block.values) + '"'
                
                if key == "$project" and len(project_block.items) == 1:
                    qpc_base_file[-1] += ' "' + project_block.items[0].key.replace("\\", "/").replace(".vpc", ".qpc") + '"'''
                    WriteCondition(project_block.items[0].condition, qpc_base_file)
                    qpc_base_file.append("")
                    project_block.items.remove(project_block.items[0])
                else:
                    WriteCondition(project_block.condition, qpc_base_file)
                
                if project_block.items:
                    qpc_base_file.append("{")
                    ConvertSubVGCBlock(1, project_block.items, qpc_base_file)
                    qpc_base_file.append("}")
            
            elif key in ("$macro", "$conditional", "$include"):
                for index, value in enumerate(values):
                    values[index] = ConvertMacroCasing(value.replace("vpc_scripts", "_qpc_scripts"))

                if key == "$include":
                    qpc_base_file.append(
                        'include "' + project_block.values[0].replace("\\", "/").replace("vgc", "qpc_base") + '"')
                else:
                    qpc_base_file.append('macro "' + project_block.values[0].replace("\\", "/") + '"')

                WriteCondition(project_block.condition, qpc_base_file)
            
        # skip
        elif key in {"$games"}:
            pass
        else:
            project_block.warning("Unknown Key:")
            
    # add configurations block
    qpc_base_file.extend(
        ["",
         "configurations",
         "{",
         "\t\"Debug\"",
         "\t\"Release\"",
         "}"
         ]
    )
    
    WriteProject(vgc_dir, vgc_filename, qpc_base_file, True)
    
    return


def ConvertSubVGCBlock(depth, block_items, qpc_base_file):
    space = "{0}".format("\t" * depth)
    for sub_block in block_items:
        if sub_block.key.casefold() == "$folder":
            qpc_base_file.append(space + 'folder "' + sub_block.values[0] + '"')
            WriteCondition(sub_block.condition, qpc_base_file)
            for item in sub_block.items:
                ConvertSubVGCBlock(depth+1, item, qpc_base_file)
        else:
            key = ConvertMacroCasing('"' + sub_block.key.replace("\\", "/").replace(".vpc", ".qpc") + '"')
            qpc_base_file.append(space + key)
            WriteCondition(sub_block.condition, qpc_base_file)
    return


def CreateDirectory(directory: str):
    try:
        os.makedirs(directory)
        if args.verbose:
            print("Created Directory: " + directory)
    except FileExistsError:
        pass
    except FileNotFoundError:
        pass


def WriteProject(directory, filename, project_lines, base_file=False):
    directory = directory.replace("vpc_scripts", "_qpc_scripts")
    CreateDirectory(directory)
    
    abs_path = os.path.normpath(directory + os.sep + filename + ".qpc")
    if base_file:
        abs_path += "_base"
    
    with open(abs_path, mode="w", encoding="utf-8") as project_file:
        WriteTopComment(project_file)
        project_file.write('\n'.join(project_lines) + "\n")
    return


# might just use the class right from the qpc parser, idk
# this is really awful
class Configuration:
    def __init__(self):
        general = ConfigGroup("general")
        general.options = [
            ConfigOption("out_name"),
            ConfigOption("out_dir"),
            ConfigOption("int_dir"),
            ConfigOption("configuration_type"),
            ConfigOption("language"),
            ConfigOption("compiler"),
            ConfigOption("include_directories", True),
            ConfigOption("library_directories", True),
            ConfigOption("options", True),
        ]
        
        compiler = ConfigGroup("compiler")
        compiler.options = [
            ConfigOption("preprocessor_definitions", True),
            ConfigOption("precompiled_header"),
            ConfigOption("precompiled_header_file"),
            ConfigOption("precompiled_header_out_file"),
            ConfigOption("options", True),
        ]
        
        linker = ConfigGroup("linker")
        linker.options = [
            ConfigOption("output_file"),
            ConfigOption("debug_file"),
            ConfigOption("import_library"),
            ConfigOption("ignore_import_library"),
            ConfigOption("libraries", True),
            ConfigOption("ignore_libraries", True),
            ConfigOption("options", True),
        ]
        
        self.groups = {
            "general": general.ToDict(),
            "compiler": compiler.ToDict(),
            "linker": linker.ToDict(),
        }
        
        self.options = {
            "pre_build": ConfigOption("pre_build", True),
            "pre_link": ConfigOption("pre_link", True),
            "post_build": ConfigOption("post_build", True),
        }


# we will only have one main config,
# any option or group added to it will have a condition of the config name
# like ($_CONFIG == Debug)
# it checks if the config option/group already exists, and if it does,
# it adds onto the condition, ex: $WINDOWS && ($_CONFIG == Debug)
# if a config condition is already added to it, it will somehow check if
# that config and the current config is Debug AND Release, or just all available configs somehow
# if it all configs, it will get rid of both of those conditions
# or just keep it and handle it in WriteCondition
# since we might have another condition in there

# what about platform conditions? meh, handle those in WriteCondition as well


# maybe only apply the condition to the group if everything in the options has some shared condition?
class ConfigGroup:
    def __init__(self, name):
        self.name = name
        self.options = []
        
    def ToDict(self):
        option_dict = {}
        for option in self.options:
            option_dict[option.name] = option
        return option_dict
        
        
class ConfigOption:
    def __init__(self, name, is_list=False):
        self.name = name
        self.is_list = is_list
        self.condition = None
        self.value = []
    
    def SetValue(self, values, condition, split_values):
        if self.is_list:
            if split_values:
                for string in split_values:
                    values = ' '.join(values).split(string)
                values = list(filter(None, values))  # remove empty items from the list
                # wrap each value in quotes (maybe add an input option here for we should wrap in quotes or not?)
                values = list('"' + value + '"' for value in values)
            
            if self.name not in ("preprocessor_definitions", "options"):
                for index, value in enumerate(values):
                    if value != "\\n":
                        values[index] = value.replace("\\", "/")
                    if values[index] != '""' and values[index].endswith('""'):
                        values[index] = values[index][:-1]
            
            # might be added already
            for added_value in self.value:
                if added_value.value in values:
                    # it is added, so merge the conditions
                    added_value.condition = MergeConfigConditions(condition, added_value.condition)
                    values.remove(added_value.value)
            
            if split_values:
                for value in values:
                    value = value.replace("$BASE ", "").replace("$BASE", "")
                    # other values
                    value = value.replace("%(AdditionalDependencies)", "")
                    if value != '""':
                        condition = NormalizePlatformConditions(condition)
                        self.value.append(ConfigOptionValue(value, condition))
            else:
                for value in values:
                    value = value.replace("$BASE", "")
                    value = value.lstrip().rstrip()  # strip trailing whitespace at start and end
                    if value and value != "\\n":
                        condition = NormalizePlatformConditions(condition)
                        self.value.append(ConfigOptionValue('"' + value + '"', condition))
        else:
            value = '"' + ''.join(values) + '"'
            value = value.replace("$PLATSUBDIR", "$PLATFORM")
            
            if self.name != "configuration_type":
                value = value.replace("\\", "/")
            
            # get rid of any file extension and add the quote back onto the end if it changed
            if self.name in ("output_file", "debug_file", "import_library"):
                # value = os.path.splitext(value)[0] + '"'
                new_value = os.path.splitext(value)[0]
                if new_value != value:
                    value = new_value + '"'
            
            # might be added already
            for added_value in self.value:
                if added_value.value == value:
                    # it is added, so merge the conditions
                    added_value.condition = MergeConfigConditions(condition, added_value.condition)
                    added_value.condition = NormalizePlatformConditions(added_value.condition)
                    return
            
            if not condition:
                condition = None
            
            condition = NormalizePlatformConditions(condition)
            self.value.append(ConfigOptionValue(value, condition))
    
    def AddValue(self, value, condition):
        # might be added already
        for added_value_obj in self.value:
            if added_value_obj.value == value and added_value_obj.condition == condition:
                return
        
        self.value.append(ConfigOptionValue(value, condition))


class ConfigOptionValue:
    def __init__(self, value, condition):
        self.value = value
        self.condition = condition


# TODO: maybe change this to MergeConditions? would have to split by all operators and go through each one
#  meh, maybe in the future, though i doubt it
def MergeConfigConditions(cond, add_cond):
    if cond and add_cond:
        if "$DEBUG" in cond and "$RELEASE" in add_cond and \
                "RELEASEASSERTS" not in cond and "RELEASEASSERTS" not in add_cond:
            add_cond = RemoveCondition(add_cond, "$RELEASE")
        
        elif "$RELEASE" in cond and "$DEBUG" in add_cond and \
                "RELEASEASSERTS" not in cond and "RELEASEASSERTS" not in add_cond:
            add_cond = RemoveCondition(add_cond, "$DEBUG")
        
        elif add_cond:
            add_cond = AddCondition(add_cond, cond, "&&")
        
        if not add_cond:
            add_cond = None
    else:
        add_cond = cond
    return add_cond


def ConvertMacroCasing(string):
    for macro in MACRO_CONVERT:
        if macro in string:
            string = string.replace(macro, MACRO_CONVERT[macro])
    return string


def convert_vpc(vpc_dir, vpc_filename, vpc_project):
    qpc_project_list = []
    config = Configuration()
    libraries = []
    files_block_list = []
    
    for project_block in vpc_project:
        
        key = project_block.key.casefold()  # compare with ignoring case
        
        if key == "$configuration":
            ParseConfiguration(project_block, config)
        
        elif key == "$project":
            if len(qpc_project_list) > 0 and not qpc_project_list[-1].endswith("\n") and qpc_project_list[-1] != "":
                qpc_project_list.append("")
            
            if project_block.values:
                qpc_project_list.insert(0, "macro PROJECT_NAME \"" + project_block.values[0] + "\"")
                qpc_project_list.insert(1, "")

            files_block = ["files"]
            WriteCondition(project_block.condition, files_block)
            files_block.append("{")
            found_libraries, files_block = WriteFilesBlock(project_block, files_block, "\t")
            
            if found_libraries:
                libraries.extend(found_libraries)
            if len(files_block) > 2:
                # qpc_project_list.extend(files_block)
                # qpc_project_list.append("}")
                files_block.append("}")
                files_block_list.extend(files_block)
        
        elif key in ("$macro", "$macrorequired", "$macrorequiredallowempty", "$conditional"):
            WriteMacro(project_block, qpc_project_list)
        
        elif key == "$include":
            WriteInclude(project_block, qpc_project_list)
        
        elif key in ("$linux", "$ignoreredundancywarning", "$loadaddressmacro", "$loadaddressmacroauto"):
            pass
        
        else:
            project_block.warning("Unknown Key: ")
    
    if libraries:
        # if not qpc_project_list[-1].endswith("\n") and qpc_project_list[-1] != "":
        #     qpc_project_list.append("")
        # WriteLibraries( libraries, linker_libraries, qpc_project_list, base_macros )
        AddLibrariesToConfiguration(libraries, config)
        
        # config = MergeConfigurations(config_list)
    qpc_project_list = WriteConfiguration(config, "", qpc_project_list)
    
    # gap between anything before files and files
    if qpc_project_list[-1] != "":
        qpc_project_list.append("")
    qpc_project_list.extend(files_block_list)
    
    for index, line in enumerate(qpc_project_list):
        qpc_project_list[index] = ConvertMacroCasing(line)
    
    WriteProject(vpc_dir, vpc_filename, qpc_project_list)
    return


def WriteTopComment(qpc_project):
    qpc_project.write(
        "// ---------------------------------------------------------------\n" +
        "// Auto Generated QPC Script - Fix if needed before using\n" +
        "// ---------------------------------------------------------------\n")


def NormalizePlatformConditions(cond):
    if cond:
        if "$WINDOWS" in cond:
            if "$WIN32" in cond or "$WIN64" in cond:
                cond = RemoveCondition(cond, "$WIN32")
                cond = RemoveCondition(cond, "$WIN64")
        
        if "$WIN32" in cond and "$WIN64" in cond:
            cond = cond.replace("$WIN32", "$WINDOWS")
            cond = RemoveCondition(cond, "$WIN64")
        
        if "$LINUX32" in cond and "$LINUX64" in cond:
            cond = cond.replace("$LINUX32", "$LINUX")
            cond = RemoveCondition(cond, "$LINUX64")
        
        if "$OSX32" in cond and "$OSX64" in cond:
            cond = cond.replace("$OSX32", "$MACOS")
            cond = RemoveCondition(cond, "$OSX64")
        
        cond = cond.replace("$OSXALL", "$OSX")
        cond = cond.replace("$LINUXALL", "$LINUX")
        
        if "$POSIX64" in cond:
            # get rid of any redundant conditions (might not be redundant and im just dumb)
            if "$OSX64" in cond and "!$OSX64" not in cond:
                cond = RemoveCondition(cond, "$OSX64")
            if "$LINUX64" in cond and "!$LINUX64" not in cond:
                cond = RemoveCondition(cond, "$LINUX64")
        
        if "$POSIX32" in cond:
            # get rid of any redundant conditions (might not be redundant and im just dumb)
            if "$OSX32" in cond and "!$OSX32" not in cond:
                cond = RemoveCondition(cond, "$OSX32")
            if "$LINUX32" in cond and "!$LINUX64" not in cond:
                cond = RemoveCondition(cond, "$LINUX32")
    return cond


# could be used to add a condition maybe
def NormalizeConfigConditions(cond):
    if cond:
        # remove it and then add it back, could be in there multiple times lmao
        if "$DEBUG" in cond:
            cond = RemoveCondition(cond, "$DEBUG")
            cond = AddCondition(cond, "$DEBUG", "&&")
        if "$RELEASE" in cond and "RELEASEASSERTS" not in cond:
            cond = RemoveCondition(cond, "$RELEASE")
            cond = AddCondition(cond, "$RELEASE", "&&")
    return cond


def AddCondition(base_cond, add_cond, add_operator):
    if base_cond:
        # if we have operators in this already, then wrap that in parenthesis
        for operator in ("||", "&&", ">", ">=", "==", "!=", "=<", "<"):
            if operator in base_cond:
                # don't need to wrap if it's || or &&
                if operator in ("||", "&&"):
                    base_cond += add_operator + add_cond
                else:
                    base_cond = "(" + base_cond + ")" + add_operator + add_cond
                break
        else:
            # there are no operators, only one condition, so don't wrap in parenthesis
            base_cond += add_operator + add_cond
    else:
        base_cond = add_cond
    return base_cond


def RemoveCondition(cond, value_to_remove):
    while value_to_remove in cond:
        cond = cond.split(value_to_remove, 1)
        
        operator = ''
        if cond[0].endswith("||") or cond[0].endswith("&&"):
            operator = cond[0][-2:]
            cond[0] = cond[0][:-2]
        
        if cond[1].startswith("||") or cond[1].startswith("&&"):
            operator = cond[1][:2]
            cond[1] = cond[1][2:]
        
        # strip parenthesis from both ends if they existed
        # this might cause an issue, because there might be more conds depending on these parenthesis
        # though that's very unlikely, so im not going to bother fixing it
        if cond[0].endswith("("):
            cond[0] = cond[0][:-1]
        elif len(cond) > 1 and cond[1].startswith("("):
            cond[1] = cond[1][1:-1]
        
        # better way to merge them together
        if cond[0] and cond[1] and operator:
            cond = AddCondition(cond[0], cond[1], operator)
        else:
            cond = ''.join(cond)
    
    return cond


def WriteCondition(condition, qpc_project):
    if condition:
        condition = NormalizePlatformConditions(condition)
        condition = NormalizeConfigConditions(condition)
        condition = AddSpacingToCondition(condition)
        qpc_project[-1] += " [" + condition + "]"


def AddSpacingToCondition(cond):
    cond = cond.strip(" ")
    
    if ">=" not in cond:
        cond = cond.replace(">", " > ")
    if "<=" not in cond:
        cond = cond.replace("<", " < ")
        
    for operator in {"<=", ">=", "==", "||", "&&"}:
        cond = cond.replace(operator, ' ' + operator + ' ')
    
    return cond


def WriteMacro(vpc_macro, qpc_project):
    if len(vpc_macro.values) > 1:
        macro_value = ' "' + ConvertMacroCasing(vpc_macro.values[1]) + '"'
    else:
        macro_value = ''
    
    # leave a gap in-between
    if len(qpc_project) > 0 and not qpc_project[-1].startswith("macro") and qpc_project[-1][-1] != "\n":
        qpc_project.append("")
    
    # might be a bad idea for a macro
    macro_value = macro_value.replace("\\", "/")
    if macro_value.endswith('""'):
        macro_value = macro_value[:-1]
    
    qpc_project.append("macro " + ConvertMacroCasing(vpc_macro.values[0]) + macro_value)
    WriteCondition(vpc_macro.condition, qpc_project)


def WriteInclude(vpc_include, qpc_project):
    qpc_include_path = vpc_include.values[0].replace(".vpc", ".qpc")
    qpc_include_path = qpc_include_path.replace("vpc_scripts", "_qpc_scripts")
    qpc_include_path = os.path.normpath(qpc_include_path)
    qpc_include_path = ConvertMacroCasing(qpc_include_path)
    
    # leave a gap in-between
    if len(qpc_project) > 0 and not qpc_project[-1].startswith("include") and qpc_project[-1][-1] != "\n":
        qpc_project.append("")
    
    qpc_project.append("include \"" + qpc_include_path.replace("\\", "/") + "\"")
    WriteCondition(vpc_include.condition, qpc_project)


def WriteFilesBlock(vpc_files, qpc_project, indent):
    libraries = []
    for file_block in vpc_files.items:
        
        if file_block.key.casefold() == "$folder" and not file_block.values[0] == "Link Libraries":
            
            # if "}" in qpc_project[-1]:
            if "{" not in qpc_project[-1]:
                qpc_project[-1] += "\n"
            
            qpc_project.append(indent + "folder \"" + file_block.values[0] + '"')
            WriteCondition(file_block.condition, qpc_project)
            qpc_project.append(indent + "{")
            nothing, qpc_project = WriteFilesBlock(file_block, qpc_project, indent + "\t")
            qpc_project.append(indent + "}")
        
        elif file_block.key.casefold() in ("$file", "$dynamicfile", "-$file"):
            if file_block.values[0].endswith(".lib"):
                libraries.append(file_block)
            else:
                qpc_project = WriteFile(file_block, qpc_project, indent)
        
        elif file_block.key.casefold() == "$folder" and file_block.values[0] == "Link Libraries":
            libraries.extend(file_block.items)
    
    return libraries, qpc_project


def WriteFile(file_block, qpc_project, indent):
    if file_block.key.casefold() in ("$file", "$dynamicfile", "-$file"):
        if len(file_block.values) > 1:
            qpc_project[-1] += "\n"
            for index, file_path in enumerate(file_block.values):
                file_path = file_path.replace("\\", "/")
                # TODO: would be cool to get every "\" indented the same amount, but idk how i would do that
                if index == 0 and file_block.key.startswith("-"):
                    qpc_project.append(indent + '- "' + file_path + "\"\t\\")
                elif index < len(file_block.values) - 1:
                    qpc_project.append(indent + '"' + file_path + "\"\t\\")
                else:
                    qpc_project.append(indent + '"' + file_path + "\"")
        else:
            if "}" in qpc_project[-1]:
                qpc_project[-1] += "\n"
            
            file_path = file_block.values[0].replace("\\", "/")
            if file_block.key.startswith("-"):
                qpc_project.append(indent + '- "' + file_path + '"')
            else:
                qpc_project.append(indent + '"' + file_path + '"')
        
        WriteCondition(file_block.condition, qpc_project)
        
        if file_block.items:
            file_config = Configuration()
            
            for file_config_block in file_block.items:
                ParseConfiguration(file_config_block, file_config)
            
            # useless?
            # config = MergeConfigurations(file_config)
            
            qpc_project.append(indent + "{")
            # qpc_project = WriteConfiguration(file_config, len(qpc_project) + 1, indent + "\t", qpc_project)
            qpc_project = WriteConfiguration(file_config, indent + "\t", qpc_project)
            qpc_project.append(indent + "}")
    else:
        file_block.warning("Unknown Key: ")
    return qpc_project


def AddLibrariesToConfiguration(libraries_block_list, config):
    config_option = config.groups["linker"]["libraries"]
    library_paths = []
    
    # adds a gap in-between already added libraries and these
    # if config_option.value:
    #     config_option.AddValue("", None)
    
    for library in libraries_block_list:
        lib_name = ' '.join(library.values).replace("\\", "/")
        lib_name = '"' + os.path.splitext(lib_name)[0] + '"'
        
        path_dict = {
            "$SRC_DIR/lib/common": "$LIBCOMMON",
            "$SRCDIR/lib/common": "$LIBCOMMON",
            "lib/common": "$LIBCOMMON",
            "$SRC_DIR/lib/public": "$LIBPUBLIC",
            "$SRCDIR/lib/public": "$LIBPUBLIC",
            "lib/public": "$LIBPUBLIC",
        }
        
        for path, macro in path_dict.items():
            if path in lib_name:
                lib_name = macro.join(lib_name.split(path))
                break
        
        if library.key.startswith("-"):
            config_option.AddValue("- " + lib_name, library.condition)
        else:
            config_option.AddValue(lib_name, library.condition)
    
    # might be a bad idea
    if library_paths:
        for lib_path in library_paths:
            config.groups["general"]["library_directories"].AddValue('"' + os.path.splitext(lib_path)[0] + '"', None)
    return


# might be skipping this if it has a condition?
# maybe return any paths found and add that into the configuration?
def WriteLibraries(libraries_block, linker_libraries, qpc_project, macros):
    qpc_project.append("libraries")
    if libraries_block:
        WriteCondition(libraries_block.condition, qpc_project)
    qpc_project.append("{")
    
    if libraries_block:
        for library in libraries_block.items:
            lib_path = ' '.join(library.values).replace("\\", "/")
            
            lib_path = lib_path.replace(macros["$_STATICLIB_EXT"], "")
            lib_path = lib_path.replace(macros["$_IMPLIB_EXT"], "")
            
            if library.key.startswith("-"):
                qpc_project.append("\t- \"" + lib_path + '"')
            else:
                qpc_project.append("\t\"" + lib_path + '"')
            
            WriteCondition(library.condition, qpc_project)
        
        if linker_libraries:
            qpc_project[-1] += "\n"
    
    for library, condition in linker_libraries.items():
        if library == '"%(AdditionalDependencies)"':
            continue
        
        lib_path = library.replace("\\", "/")
        
        lib_path = lib_path.replace(macros["$_STATICLIB_EXT"], "")
        lib_path = lib_path.replace(macros["$_IMPLIB_EXT"], "")
        
        qpc_project.append("\t" + lib_path)
        
        WriteCondition(condition, qpc_project)
    
    qpc_project.append("}\n")
    return


def ParseConfigOption(condition, option_block, qpc_option, option_value):
    condition = NormalizePlatformConditions(condition)
    # ew
    if option_block.key.casefold() == "$multiprocessorcompilation":
        if option_block.values and option_block.values[0] == "True":
            option_value = ["/MP"]
    # ew again
    elif option_block.key.casefold() == "$disablespecificwarnings":
        if option_block.values:
            option_value = [option_block.values[0].replace(";", ";/ignore:")]
    # ew yet again
    elif option_block.key.casefold() == "$excludedfrombuild":
        if option_block.values:
            if option_block.values[0] == "No":
                option_value = "True"
            elif option_block.values[0] == "Yes":
                option_value = "False"
    
    if option_block.key.casefold() == "$commandline":
        for index, value in enumerate(option_value):
            option_value[index] = value.replace('"', '\\"').replace('$QUOTE', '\\"')
        
        # don't split this into a list
        qpc_option.SetValue(option_value, condition, False)
        
    elif option_block.key.casefold() in ("$gcc_extracompilerflags", "$gcc_extralinkerflags", "$optimizerlevel"):
        qpc_option.SetValue(option_value, condition, [','])  # only split by commas (i think?)
    else:
        qpc_option.SetValue(option_value, condition, [',', ';', ' '])
    return


def ParseConfiguration(vpc_config, qpc_config):
    if vpc_config.values:
        config_cond = "$" + vpc_config.values[0].upper()
        if vpc_config.condition:
            config_cond += "&&" + vpc_config.condition
    else:
        config_cond = vpc_config.condition
    
    for config_group in vpc_config.items:
        config_group_name = ConvertConfigGroupName(config_group.key)
        
        if not config_group_name:
            config_group.warning("Unknown config group: ")
            continue
        
        for option_block in config_group.items:
            config_group_name = ConvertVPCGroup(option_block.key, config_group.key)
            option_name = ConvertConfigOptionName(option_block.key)
            
            if option_block.key in VPC_CONFIG_IGNORE_LIST:
                print("ignore list key")
            
            if config_group_name in EVENTS:
                if option_block.key.casefold() == "$commandline":
                    option_value = option_block.values
                else:
                    continue
            
            elif not option_name:
                option_value = ConvertVPCOptionToQPCOption(option_block.values)
                
                if not option_value:
                    option_block.warning("Unknown config option: ")
                    continue
                else:
                    option_name = "options"
            else:
                option_value = ConvertBoolToVSCommand(option_block)
                if not option_value:
                    option_value = ConvertVPCOption(option_block.values)
            
            if option_value:
                if config_group_name in qpc_config.options:
                    ParseConfigOption(config_cond, option_block, qpc_config.options[config_group_name], option_value)
                elif config_group_name in qpc_config.groups:
                    try:
                        qpc_option = qpc_config.groups[config_group_name][option_name]
                    except KeyError:
                        print("unknown config option")
                        continue
                            
                    condition = NormalizePlatformConditions(option_block.condition)

                    # if the group has a condition, add that onto every value here
                    if config_group and config_group.condition:
                        if condition:
                            # TODO: test this, never ran into this yet, so im hoping this works
                            group_condition = NormalizePlatformConditions(config_group.condition)

                            if condition != group_condition:
                                condition = NormalizePlatformConditions(
                                    option_block.condition + "&&" + group_condition)
                        else:
                            condition = NormalizePlatformConditions(config_group.condition)

                    # if this option is in a specific config, add a config condition to it
                    if config_cond:
                        condition = AddCondition(condition, config_cond, "&&")
                        
                    ParseConfigOption(condition, option_block, qpc_option, option_value)
                else:
                    print("unknown config group/option")
    
    return


def ConvertConfigGroupName(group_name):
    group_name = group_name.casefold()
    if group_name == "$general":
        return "general"
    elif group_name == "$compiler":
        return "compiler"
    elif group_name == "$linker":
        return "linker"
    elif group_name == "$librarian":
        return "linker"
    elif group_name == "$prelinkevent":
        return "pre_link"
    elif group_name == "$prebuildevent":
        return "pre_build"
    elif group_name == "$postbuildevent":
        return "post_build"
    else:
        return None


def ConvertConfigOptionName(option_name):
    option_name = option_name.casefold()
    try:
        return OPTION_NAME_CONVERT_DICT[option_name]
    except KeyError:
        return None


def ConvertVPCOption(option_value):
    if option_value:
        try:
            return [OPTION_VALUE_CONVERT_DICT[option_value[0]]]
        except KeyError:
            return option_value
    else:
        return None


def ConvertVPCGroup(option_name, current_group):
    option_name = option_name.casefold()
    try:
        return CONFIG_GROUP_CONVERT_DICT[option_name]
    except KeyError:
        # convert it again, since we might of changed it in the previous option
        return ConvertConfigGroupName(current_group)


def ConvertVPCOptionToQPCOption(option_value):
    if option_value:
        try:
            return [CMD_CONVERT[option_value[0]]]
        except KeyError:
            return None
    else:
        return None


def ConvertBoolToVSCommand(option_block):
    if option_block.key and option_block.values:
        try:
            return [VS_BOOL_CONVERT[option_block.key.casefold()][option_block.values[0]]]
        except KeyError:
            return None
    else:
        return None
    
    
def WriteConfigOption(indent, option):
    current_option = []
    if option.value:
        if option.is_list:
            current_option = [indent + "\t" + option.name]
            option_lines = []
            cond_values = {}
            for value_obj in option.value:
                base.add_dict_value(cond_values, value_obj.condition, "list")
                cond_values[value_obj.condition].append(value_obj.value)
                # option_lines.append(indent + "\t\t\t" + value_obj.value + '')
                # WriteCondition( value_obj.condition, option_lines )
            
            # write any value with the same condition on the same line
            for condition, value_list in cond_values.items():
                if condition:
                    # TODO: what if the line gets too long?
                    #  need to add a check for that and break if needed
                    option_lines.append(indent + "\t\t")
                    
                    # can't have multiple "keys" on the same line
                    # so only add it once, and strip it from the rest of the values
                    if value_list[0].startswith("- \""):
                        option_lines[-1] += value_list[0]
                        del value_list[0]
                        for value in value_list:
                            if value.startswith("- \""):
                                option_lines[-1] += " " + value[2:]
                            else:
                                WriteCondition(condition, option_lines)
                                option_lines.append(indent + "\t\t" + value)
                    else:
                        option_lines[-1] += " ".join(value_list)
                    
                    # would be cool if i could get the conditionals indented the same amount
                    WriteCondition(condition, option_lines)
            
            if None in cond_values:
                for value in cond_values[None]:
                    option_lines.append(indent + "\t\t" + value)
            
            if "" in cond_values:
                for value in cond_values[""]:
                    option_lines.append(indent + "\t\t" + value)
            
            current_option.append(indent + "\t{")
            current_option += option_lines
            current_option.append(indent + "\t}")
        else:
            # TODO: BUG: can't have multiple of these with different conditions
            # this is a workaround that will probably never change
            
            option_lines = []
            for value_obj in option.value:
                option_lines.append(indent + "\t" + option.name + " " + value_obj.value + '')
                WriteCondition(value_obj.condition, option_lines)
            current_option += option_lines
            
            # current_group.append(indent + "\t" + option.name + " " + option.value + '')
            # WriteCondition(option.condition, current_group)
            
    return current_option


# def WriteConfiguration(config, insert_index, indent, qpc_project_list):
def WriteConfiguration(config, indent, qpc_project_list):
    starting_config_lines = [indent + "configuration", indent + "{"]
    config_lines = []
    
    def AddSpace():
        if config_lines and "}" in config_lines[-1] and not config_lines[-1].endswith("\n"):
            config_lines.append(indent + "\t")
    
    def AddSpaceGroup(is_list=False):
        if current_group:
            if "}" in current_group[-1] and not current_group[-1].endswith("\n") or \
                    (is_list and "{" not in current_group[-1]):
                current_group.append(indent + "\t\t")
    
    for config_group, config_option_dict in config.groups.items():
        current_group = [indent + "\t" + config_group, indent + "\t{"]
        
        for option in config_option_dict.values():
            option_lines = WriteConfigOption(indent + "\t", option)
            if option_lines:
                AddSpaceGroup(option.is_list)
                current_group.extend(option_lines)
        
        if len(current_group) > 2:
            current_group.append(indent + "\t}")
            AddSpace()
            config_lines += current_group
            
    for config_option in config.options.values():
        # current_option = [indent + "\t" + config_option.name, indent + "\t{"]
        option_lines = WriteConfigOption(indent, config_option)
        if option_lines:
            AddSpace()
            config_lines.extend(option_lines)
    
    if config_lines:
        config_lines = starting_config_lines + config_lines + [indent + "}"]
        if qpc_project_list:
            # now jam the config into the spot where we want it
            # make sure we have a gap between anything before and the config
            if "{" not in qpc_project_list[-1] and "\n" not in qpc_project_list[-1] and qpc_project_list[-1] != "":
                # config_lines[0] = "\n" + config_lines[0]
                qpc_project_list.append("")
            
            # what is this for?
            # if len(qpc_project_list[insert_index:]) > 0:
            #     if qpc_project_list[insert_index:][0] != "" and qpc_project_list[insert_index:][0][0] != "\n":
            #         config_lines[-1] += "\n"
            # qpc_project_list = qpc_project_list[:insert_index] + config_lines + qpc_project_list[insert_index:]
            qpc_project_list.extend(config_lines)
        else:
            qpc_project_list = config_lines
    
    return qpc_project_list


def parse_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-d", "--directory")
    arg_parser.add_argument("-o", "--output")
    arg_parser.add_argument("-v", "--verbose")
    return arg_parser.parse_args()


def main():
    print("\nConverting VPC Scripts to QPC Scripts")
    
    print("Finding All VPC and VGC Scripts")
    vgc_path_list, vpc_path_list = get_vpc_scripts(args.directory)
    
    if vgc_path_list:
        print("\nConverting VGC Scripts")
        for vgc_path in vgc_path_list:
            print("Converting: " + vgc_path)
            read_vgc, vgc_dir, vgc_name = prepare_vpc_file(vgc_path)
            convert_vgc(vgc_dir, vgc_name, read_vgc)
    
    if vpc_path_list:
        print("\nConverting VPC Scripts")
        
        for vpc_path in vpc_path_list:
            # TODO: maybe make a keep comments option in ReadFile()? otherwise, commented out files won't be kept
            print("Converting: " + vpc_path)
            read_vpc, vpc_dir, vpc_name = prepare_vpc_file(vpc_path)
            convert_vpc(vpc_dir, vpc_name, read_vpc)


if __name__ == "__main__":
    args = parse_args()
    main()
