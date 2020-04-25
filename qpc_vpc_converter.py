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


def debug_assert(result: bool):
    if result:
        print("put breakpoint here")


# Conversion stuff
EVENTS = {"pre_link", "pre_build", "post_build"}


# HARDCODING
# shut up i know hardcoded bad, but i really don't feel like adding something to read from a file right now for this
# that can be done later, without changing any code below
# -----------------------------------------
# check if any libraries are in this list
# if so, add the name here to dependencies
# also all the paths are wrriten to whatever file is called default.qpc
LIBS_TO_DEPENDENCIES_LAZY = {
    "tier0":                    "tier0/tier0.qpc",
    "tier1":                    "tier1/tier1.qpc",
    "tier2":                    "tier2/tier2.qpc",
    "tier3":                    "tier3/tier3.qpc",
    "vstdlib":                  "vstdlib/vstdlib.qpc",
    
    "jpeglib":                  "thirdparty/jpeglib/jpeglib.qpc",
    "bzip2":                    "thirdparty/bzip2/bzip2.qpc",
    "lzma":                     "thirdparty/lzma/lzma.qpc",
    "lua":                      "thirdparty/lua-5.1.1/lua.qpc",
    "libspeex":                 "thirdparty/libspeex/libspeex.qpc",
    
    "vgui_controls":            "vgui2/vgui_controls/vgui_controls.qpc",
    "vgui_surfacelib":          "vgui2/vgui_surfacelib/vgui_surfacelib.qpc",
    "matsys_controls":          "vgui2/matsys_controls/matsys_controls.qpc",
    "dme_controls":             "vgui2/dme_controls/dme_controls.qpc",
    
    "mxtoolkitwin32":           "utils/mxtk/mxtoolkitwin32.qpc",
    "nvtristriplib":            "utils/nvtristriplib/nvtristriplib.qpc",
    "nvtristrip":               "utils/nvtristriplib/nvtristriplib.qpc",
    "vmpi":                     "utils/vmpi/vmpi.qpc",
    "libmad":                   "utils/libmad/libmad.qpc",
    
    "bitmap":                   "bitmap/bitmap.qpc",
    "bitmap_byteswap":          "bitmap/bitmap_byteswap.qpc",
    "shaderlib":                "materialsystem/shaderlib/shaderlib.qpc",
    "mathlib":                  "mathlib/mathlib.qpc",
    "mathlib_extended":         "mathlib/mathlib_extended.qpc",
    "fgdlib":                   "fgdlib/fgdlib.qpc",
    "raytrace":                 "raytrace/raytrace.qpc",
    "appframework":             "appframework/appframework.qpc",
    "movieobjects":             "movieobjects/movieobjects.qpc",
    "dmserializers":            "dmserializers/dmserializers.qpc",
    "datamodel":                "datamodel/datamodel.qpc",
    "choreoobjects":            "choreoobjects/choreoobjects.qpc",
    "unitlib":                  "unitlib/unitlib.qpc",
    "dmxloader":                "dmxloader/dmxloader.qpc",
    "particles":                "particles/particles.qpc",
    "vtf":                      "vtf/vtf.qpc",
    
    "bonesetup":                "bonesetup/bonesetup.qpc",
    "toolutils":                "toolutils/toolutils.qpc",
    "togl":                     "togl/togl.qpc",
    "vpklib":                   "vpklib/vpklib.qpc",
    "mdlobjects":               "mdlobjects/mdlobjects.qpc",
    "fow":                      "fow/fow.qpc",
    "videocfg":                 "videocfg/videocfg.qpc",
    "resourcefile":             "resourcefile/resourcefile.qpc",
    "responserules_runtime":    "responserules/runtime/responserules_runtime.qpc",
    "materialobjects":          "materialobjects/materialobjects.qpc",
    "matchmakingbase":          "matchmaking/matchmaking_base.qpc",
    "matchmakingbase_ds":       "matchmaking/matchmaking_base_ds.qpc",
    "zlib":                     "thirdparty/zlib-1.2.5/zlib.vpc",
}


MACRO_CONVERT = {
    "SRCDIR": "SRC_DIR",
    "OUTBINDIR": "OUT_BIN_DIR",
    "OUTBINNAME": "OUT_BIN_NAME",
    "OUTLIBDIR": "OUT_LIB_DIR",
    "OUTLIBNAME": "OUT_LIB_NAME",
    "PROJECTNAME": "PROJECT_NAME",
    "LOADADDRESS_DEVELOPMENT": "LOADADDRESS_DEVELOPMENT",
    "LOADADDRESS_RETAIL": "LOADADDRESS_RETAIL",
    "PLATSUBDIR": "PLATFORM",
}

IGNORE_CONFIG_GROUPS = {
    "$custombuildstep",
    "$snccompiler",
    "$snclinker",
    "$gcccompiler",
    "$gcclinker",
    "$xbox360imageconversion",
    "$consoledeployment",
    "$manifesttool",
    "$xmldocumentgenerator",
    "$browseinformation",
    "$resources",
    "$excludedfrombuild",  # i don't like this
    "$debugging",  # i could convert this, but nothing is ever setup for it, idc right now
}

IGNORE_CONFIG_KEYS = {
    "$entrypoint",
    "$version",
    
    "$description",
    
    "$forcedusingfiles",
    "$moduledefinitionfile",
    "$additionaloutputfiles",
    "$gameoutputfile",
    "$warninglevel",
    "$useofmfc",
    "$useofatl",
    "$baseaddress",
    
    # posix stuff
    "$symbolvisibility",
}

OPTION_NAME_CONVERT_DICT = {
    "$targetname": "out_name",
    "$outputdirectory": "out_dir",
    "$intermediatedirectory": "int_dir",
    "$configurationtype": "configuration_type",
    
    "$additionalincludedirectories": "include_directories",
    "$additionallibrarydirectories": "library_directories",
    "$additionalprojectdependencies": "dependencies",
    
    "$additionaldependencies": "libraries",
    "$systemframeworks": "libraries",
    "$systemlibraries": "libraries",
    
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
    "$enableenhancedinstructionset": "options",
    "$enablelargeaddresses": "options",
    "$fixedbaseaddress": "options",
    "$enablec++exceptions": "options",
    "$enableruntimetypeinfo": "options",
    "$enablecomdatfolding": "options",
    "$floatingpointmodel": "options",
    
    # special child
    "$forceincludes": "options",
    
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
    "Yes": "true",
    
    "False": "false",
    "No": "false",
    
    "v100": "msvc_100",
    "v110": "msvc_110",
    "v120": "msvc_120",
    "v140": "msvc_140",
    "v141": "msvc_141",
    "v142": "msvc_142",
    
    "v120_xp": "msvc_120_xp",
    "v140_xp": "msvc_140_xp",
    
    # preprocessor defs
    "Use Multi-Byte Character Set": "MBCS",
    "Use Unicode Character Set": "_MBCS",
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
    
    "Yes (/INCREMENTAL)": "/INCREMENTAL",
    "No (/INCREMENTAL:NO)": "/INCREMENTAL:NO",
    
    "Yes (/NOLOGO)": "/NOLOGO",
    "Yes (/nologo)": "/nologo",
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
    
    "Yes (/RELEASE)": "/RELEASE",
    "Yes (/GS)": "/GS",
    "Yes (/MAPINFO:EXPORTS)": "/MAPINFO:EXPORTS",
    "Yes (/FC)": "/FC",
    
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
    "Eliminate Unreferenced Data (/OPT:REF)": "/OPT:REF",
    
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
    
    "Call profiler within function calls. (/callcap)": "/callcap",
    "Call profiler around function calls. (/fastcap)": "/fastcap",
    
    "Default image type": "",
    "No Listing": "",
    "Not Using Precompiled Headers": "",
    "Not Set": "",
    "No": "",
    "Neither": "",
    "Default": "",
    "No Common Language RunTime Support": "",
    "No Whole Program Optimization": "",
}

CONFIG_GROUP_CONVERT_DICT = {
    "$compileas": "general",
    "$additionalincludedirectories": "general",
    "$additionallibrarydirectories": "general",
    
    "$characterset": "compiler",
    "$outputfile": "linker",
}

VS_BOOL_CONVERT = {
    "$imagehassafeexceptionhandlers": {
        "true": "/SAFESEH",
        "false": "/SAFESEH:NO",
    },
}

OPTION_PREFIX_ADD = {
    "$forceincludes": "/FI",
}


FILE_KEYS = {"$file", "$dynamicfile", "-$file", "$filepattern"}


MACRO_KEYS = {
    "$macro",
    "$macrorequired",
    "$macrorequiredallowempty",
    "$macroemptystring",
    "$conditional",
}


# vpc sucks
SPECIAL_FILE_KEYS = {
    "$dynamicfile_nopch", "$file_nopch", "$file_createpch", "$shaders",
    "$qtfile", "$qtschemafile", "$schemafile", "$schemaincludefile",
    "$sharedlib", "-$sharedlib"
}

IGNORE_ROOT_KEYS = {
    "$linux",
    "$ignoreredundancywarning",
    
    "$loadaddressmacro",
    "$loadaddressmacroauto",
    "$loadaddressmacroauto_padded",
    "$loadaddressmacroalias",
    
    # "$custombuildstep",
    # "$custombuildscript",
}


# idfk what to call this function
def prepare_vpc_file(project_script_path):
    project_script_path = project_script_path.replace("\\", "/")
    project_dir, project_filename = os.path.split(project_script_path)
    project_name = os.path.splitext(project_filename)[0]
    project_file = reader.read_file(project_script_path, False, False, False)
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
    qpc_base_file = []
    
    def add_space(string):
        if qpc_base_file:
            if (not qpc_base_file[-1].startswith(string) or qpc_base_file[-1] == "}") and qpc_base_file[-1] != "":
                qpc_base_file.append("")
    
    for block_index, project_block in enumerate(vgc_project):
        key = project_block.key.casefold()  # compare with ignoring case
        values = project_block.values
        
        if key in ("$macro", "$conditional", "$project", "$group", "$include"):
            if key in ("$project", "$group"):
                add_space(key[1:])
                qpc_base_file.append(key[1:])
                if project_block.values:
                    qpc_base_file[-1] += ' "' + '" "'.join(project_block.values) + '"'
                
                if key == "$project" and len(project_block.items) == 1:
                    qpc_base_file[-1] += f' "{project_block.items[0].key.replace(".vpc", ".qpc")}"'.replace("\\", "/")
                    write_condition(project_block.items[0].condition, qpc_base_file)
                    qpc_base_file.append("")
                    project_block.items.remove(project_block.items[0])
                else:
                    write_condition(project_block.condition, qpc_base_file)
                
                if project_block.items:
                    qpc_base_file.append("{")
                    convert_project_group_recurse(1, project_block.items, qpc_base_file)
                    qpc_base_file.append("}")
            
            elif key in ("$macro", "$conditional", "$include"):
                for index, value in enumerate(values):
                    # HARDCODING
                    if not args.no_hardcoding:
                        values[index] = convert_macro_casing(value.replace("vpc_scripts", "_qpc_scripts"))
                        values[index] = values[index].replace("projects", "_projects")
                        values[index] = values[index].replace("groups", "_groups")

                if key == "$include":
                    qpc_base_file.append(
                        'include "' + project_block.values[0].replace("\\", "/").replace("vgc", "qpc_base") + '"')
                else:
                    qpc_base_file.append('macro "' + project_block.values[0].replace("\\", "/") + '"')

                write_condition(project_block.condition, qpc_base_file)
            
        # skip
        elif key in {"$games"}:
            pass
        else:
            project_block.warning("Unknown Key:")
            
    # add configurations block
    # HARDCODING
    if vgc_filename == "default":
        qpc_base_file.extend(
            ["",
             "configurations",
             "{",
             "\t\"Debug\"",
             "\t\"Release\"",
             "}"
             ]
        )
    
    # HARDCODING
    if not args.no_hardcoding:
        write_project(vgc_dir, vgc_filename, qpc_base_file, True)
    else:
        write_project(vgc_dir, "_" + vgc_filename, qpc_base_file, True)
    
    return


def convert_project_group_recurse(depth, block_items, qpc_base_file):
    space = "{0}".format("\t" * depth)
    for sub_block in block_items:
        if sub_block.key.casefold() == "$folder":
            qpc_base_file.append(space + 'folder "' + sub_block.values[0] + '"')
            write_condition(sub_block.condition, qpc_base_file)
            for item in sub_block.items:
                convert_project_group_recurse(depth + 1, item, qpc_base_file)
        else:
            key = convert_macro_casing('"' + sub_block.key.replace("\\", "/").replace(".vpc", ".qpc") + '"')
            qpc_base_file.append(space + key)
            write_condition(sub_block.condition, qpc_base_file)
    return


def create_directory(directory: str):
    try:
        os.makedirs(directory)
        if args.verbose:
            print("Created Directory: " + directory)
    except FileExistsError:
        pass
    except FileNotFoundError:
        pass


def write_project(directory, filename, project_lines, base_file=False):
    out_dir = args.output + directory.split(args.directory)[1].replace("vpc_scripts", "_qpc_scripts")
    create_directory(out_dir)
    
    abs_path = os.path.normpath(out_dir + os.sep + filename + ".qpc")
    if base_file:
        abs_path += "_base"
    
    with open(abs_path, mode="w", encoding="utf-8") as project_file:
        write_comment_header(project_file, filename)
        project_file.write('\n'.join(project_lines) + "\n")

        # HARDCODING
        if filename.endswith("default"):
            dependencies = "\n".join([f'\t"{key}"\t\t\t"{value}"' for key, value in LIBS_TO_DEPENDENCIES_LAZY.items()])
            project_file.write(f'\ndependency_paths\n{{\n{dependencies}\n}}\n')
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
            ConfigOption("configuration_type", False, False),
            ConfigOption("language"),
            ConfigOption("compiler"),
            ConfigOption("include_directories", True),
            ConfigOption("library_directories", True),
            ConfigOption("options", True, False),
        ]
        
        compiler = ConfigGroup("compiler")
        compiler.options = [
            ConfigOption("preprocessor_definitions", True, False),
            ConfigOption("precompiled_header"),
            ConfigOption("precompiled_header_file"),
            ConfigOption("precompiled_header_output_file"),
            ConfigOption("options", True, False),
        ]
        
        linker = ConfigGroup("linker")
        linker.options = [
            ConfigOption("output_file"),
            ConfigOption("debug_file"),
            ConfigOption("import_library"),
            ConfigOption("ignore_import_library"),
            ConfigOption("libraries", True),
            ConfigOption("ignore_libraries", True),
            ConfigOption("options", True, False),
        ]
        
        self.groups = {
            "general": general.to_dict(),
            "compiler": compiler.to_dict(),
            "linker": linker.to_dict(),
        }
        
        self.options = {
            "pre_build": ConfigOption("pre_build", True, False),
            "pre_link": ConfigOption("pre_link", True, False),
            "post_build": ConfigOption("post_build", True, False),
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
        
    def to_dict(self) -> dict:
        option_dict = {}
        for option in self.options:
            option_dict[option.name] = option
        return option_dict
        
        
class ConfigOption:
    def __init__(self, name: str, is_list: bool = False, replace_path_sep: bool = True, remove_ext: bool = False):
        self.name = name
        self.condition = None
        self.value = []
        
        self.is_list = is_list
        self.replace_path_sep = replace_path_sep
        self.remove_ext = remove_ext
    
    def set_value(self, values, condition, split_values):
        if self.is_list:
            if split_values:
                for string in split_values:
                    values = ' '.join(values).split(string)
                values = list(filter(None, values))  # remove empty items from the list
                # wrap each value in quotes (maybe add an input option here for we should wrap in quotes or not?)
                values = list('"' + value + '"' for value in values)
            
            if self.replace_path_sep:
                for index, value in enumerate(values):
                    if value != "\\n":
                        values[index] = value.replace("\\", "/")
                    if values[index] != '""' and values[index].endswith('""'):
                        values[index] = values[index][:-1]
            
            # might be added already
            for added_value in self.value:
                if added_value.value in values:
                    # it is added, so merge the conditions
                    added_value.condition = merge_config_conditions(condition, added_value.condition)
                    values.remove(added_value.value)
            
            if split_values:
                for value in values:
                    value = value.replace("$BASE ", "").replace("$BASE", "")
                    # other values
                    value = value.replace("%(AdditionalDependencies)", "")
                    if value != '""':
                        condition = normalize_platform_conditions(condition)
                        self.value.append(ConfigOptionValue(value, condition))
            else:
                for value in values:
                    value = value.replace("$BASE", "")
                    value = value.lstrip().rstrip()  # strip trailing whitespace at start and end
                    if value and value != "\\n":
                        condition = normalize_platform_conditions(condition)
                        self.value.append(ConfigOptionValue('"' + value + '"', condition))
        else:
            value = '"' + ''.join(values) + '"'
            value = value.replace("$PLATSUBDIR", "$PLATFORM")
            
            if self.replace_path_sep:
                value = value.replace("\\", "/")
            
            # get rid of any file extension and add the quote back onto the end if it changed
            if self.remove_ext:
                # value = os.path.splitext(value)[0] + '"'
                new_value = os.path.splitext(value)[0]
                if new_value != value:
                    value = new_value + '"'
            
            # might be added already
            for added_value in self.value:
                if added_value.value == value:
                    # it is added, so merge the conditions
                    added_value.condition = merge_config_conditions(condition, added_value.condition)
                    added_value.condition = normalize_platform_conditions(added_value.condition)
                    return
            
            if not condition:
                condition = None
            
            condition = normalize_platform_conditions(condition)
            self.value.append(ConfigOptionValue(value, condition))
    
    def add_value(self, value, condition):
        # might be added already
        for added_value_obj in self.value:
            if added_value_obj.value == value and added_value_obj.condition == condition:
                return
        
        self.value.append(ConfigOptionValue(value, condition))


class ConfigOptionValue:
    def __init__(self, value, condition):
        self.value = value
        self.condition = condition


# TODO: maybe change this to merge_conditions? would have to split by all operators and go through each one
#  meh, maybe in the future, though i doubt it
def merge_config_conditions(cond: str, add_cond: str) -> str:
    if cond and add_cond:
        if "$DEBUG" in cond and "$RELEASE" in add_cond and \
                "RELEASEASSERTS" not in cond and "RELEASEASSERTS" not in add_cond:
            add_cond = remove_condition(add_cond, "$RELEASE")
        
        elif "$RELEASE" in cond and "$DEBUG" in add_cond and \
                "RELEASEASSERTS" not in cond and "RELEASEASSERTS" not in add_cond:
            add_cond = remove_condition(add_cond, "$DEBUG")
        
        elif add_cond:
            add_cond = add_condition(add_cond, cond, "&&")
        
        if not add_cond:
            add_cond = None
    else:
        add_cond = cond
    return add_cond


def convert_macro_casing(string: str) -> str:
    for macro in MACRO_CONVERT:
        if macro in string:
            string = string.replace(macro, MACRO_CONVERT[macro])
    return string


def convert_vpc(vpc_dir, vpc_filename, vpc_project):
    qpc_project_list = []
    config = Configuration()
    libraries = []
    files_block_list = []
    dependencies = {}
    
    for project_block in vpc_project:
        
        key = project_block.key.casefold()  # compare with ignoring case
        
        if key == "$configuration":
            parse_configuration(project_block, config, dependencies)
        
        elif key == "$project":
            if len(qpc_project_list) > 0 and not qpc_project_list[-1].endswith("\n") and qpc_project_list[-1] != "":
                qpc_project_list.append("")
            
            if project_block.values:
                qpc_project_list.insert(0, "macro PROJECT_NAME \"" + project_block.values[0] + "\"")
                qpc_project_list.insert(1, "")

            files_block = ["files"]
            write_condition(project_block.condition, files_block)
            files_block.append("{")
            found_libraries, files_block = write_files_block(project_block, files_block, "\t")
            
            if found_libraries:
                libraries.extend(found_libraries)
            if len(files_block) > 2:
                # qpc_project_list.extend(files_block)
                # qpc_project_list.append("}")
                files_block.append("}")
                files_block_list.extend(files_block)
        
        elif key in {"$macro", "$macrorequired", "$macrorequiredallowempty", "$conditional", "$macroemptystring"}:
            write_macro(project_block, qpc_project_list)
        
        elif key == "$include":
            write_include(project_block, qpc_project_list)
        
        elif key in IGNORE_ROOT_KEYS:
            pass
        
        else:
            project_block.warning("Unknown Key: ")
    
    if libraries:
        # if not qpc_project_list[-1].endswith("\n") and qpc_project_list[-1] != "":
        #     qpc_project_list.append("")
        # WriteLibraries( libraries, linker_libraries, qpc_project_list, base_macros )
        AddLibrariesToConfiguration(libraries, config)
        
        # config = MergeConfigurations(config_list)
    qpc_project_list = write_configuration(config, "", qpc_project_list)
    
    
    for library in config.groups["linker"]["libraries"].value:
        if library.value.startswith("- "):
            continue
        value = library.value[1:-1]
        if value.startswith("$LIBPUBLIC/") or value.startswith("$LIBCOMMON/"):
            value = value[11:]
            
        if value in LIBS_TO_DEPENDENCIES_LAZY:
            dependencies[value] = library.condition
        elif "bzip2" in value:
            dependencies["bzip2"] = library.condition
        
    if dependencies:
        # dependencies = "\n".join([f'\t"{key}"\t\t\t"{value}"' for key, value in LIBS_TO_DEPENDENCIES_LAZY.items()])
        # project_file.write(f'\ndependency_paths\n{{\n{dependencies}\n}}\n')
        qpc_project_list.append("\ndependencies\n{")
        for dependency, condition in dependencies.items():
            string = f'\t"{dependency}"'
            if condition:
                string += f"\t[{format_condition(condition)}]"
            qpc_project_list.append(string)
        qpc_project_list.append("}")
    
    # gap between anything before files and files
    if qpc_project_list and qpc_project_list[-1] != "":
        qpc_project_list.append("")
    qpc_project_list.extend(files_block_list)
    
    # empty vpc script
    if not qpc_project_list:
        return
    
    for index, line in enumerate(qpc_project_list):
        qpc_project_list[index] = convert_macro_casing(line)
    
    write_project(vpc_dir, vpc_filename, qpc_project_list)
    return


def write_comment_header(qpc_project, filename: str):
    qpc_project.write(
        f"// ---------------------------------------------------------------\n" +
        f"// {filename}.qpc\n" +
        f"// ---------------------------------------------------------------\n")


def normalize_platform_conditions(cond: str) -> str:
    if cond:
        if "$WINDOWS" in cond:
            if "$WIN32" in cond or "$WIN64" in cond:
                cond = remove_condition(cond, "$WIN32")
                cond = remove_condition(cond, "$WIN64")
        
        if "$WIN32" in cond and "$WIN64" in cond:
            cond = cond.replace("$WIN32", "$WINDOWS")
            cond = remove_condition(cond, "$WIN64")
        
        if "$LINUX32" in cond and "$LINUX64" in cond:
            cond = cond.replace("$LINUX32", "$LINUX")
            cond = remove_condition(cond, "$LINUX64")
        
        if "$OSX32" in cond and "$OSX64" in cond:
            cond = cond.replace("$OSX32", "$MACOS")
            cond = remove_condition(cond, "$OSX64")
        
        cond = cond.replace("$OSXALL", "$OSX")
        cond = cond.replace("$LINUXALL", "$LINUX")
        
        if "$POSIX64" in cond:
            # get rid of any redundant conditions (might not be redundant and im just dumb)
            if "$OSX64" in cond and "!$OSX64" not in cond:
                cond = remove_condition(cond, "$OSX64")
            if "$LINUX64" in cond and "!$LINUX64" not in cond:
                cond = remove_condition(cond, "$LINUX64")
        
        if "$POSIX32" in cond:
            # get rid of any redundant conditions (might not be redundant and im just dumb)
            if "$OSX32" in cond and "!$OSX32" not in cond:
                cond = remove_condition(cond, "$OSX32")
            if "$LINUX32" in cond and "!$LINUX64" not in cond:
                cond = remove_condition(cond, "$LINUX32")
    return cond


# could be used to add a condition maybe
def normalize_config_conditions(cond):
    if cond:
        # remove it and then add it back, could be in there multiple times lmao
        if "$DEBUG" in cond:
            cond = remove_condition(cond, "$DEBUG")
            cond = add_condition(cond, "$DEBUG", "&&")
        if "$RELEASE" in cond and "RELEASEASSERTS" not in cond:
            cond = remove_condition(cond, "$RELEASE")
            cond = add_condition(cond, "$RELEASE", "&&")
    return cond


def add_condition(base_cond, add_cond, add_operator):
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


def remove_condition(cond, value_to_remove):
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
            cond = add_condition(cond[0], cond[1], operator)
        else:
            cond = ''.join(cond)
    
    return cond


def write_condition(condition, qpc_project):
    if condition:
        qpc_project[-1] += " [" + format_condition(condition) + "]"


def format_condition(condition: str) -> str:
    if condition:
        condition = normalize_platform_conditions(condition)
        condition = normalize_config_conditions(condition)
        condition = add_spacing_to_condition(condition)
    return condition


def add_spacing_to_condition(cond):
    cond = cond.strip(" ")
    
    if ">=" not in cond:
        cond = cond.replace(">", " > ")
    if "<=" not in cond:
        cond = cond.replace("<", " < ")
        
    for operator in {"<=", ">=", "==", "||", "&&"}:
        cond = cond.replace(operator, ' ' + operator + ' ')
    
    return cond


def write_macro(vpc_macro, qpc_project):
    if len(vpc_macro.values) > 1:
        macro_value = ' "' + convert_macro_casing(vpc_macro.values[1]) + '"'
    else:
        macro_value = ''
    
    # leave a gap in-between
    if len(qpc_project) > 0 and not qpc_project[-1].startswith("macro") and qpc_project[-1][-1] != "\n":
        qpc_project.append("")
    
    # might be a bad idea for a macro
    macro_value = macro_value.replace("\\", "/")
    if macro_value.endswith('""'):
        macro_value = macro_value[:-1]
    
    qpc_project.append("macro " + convert_macro_casing(vpc_macro.values[0]) + macro_value)
    write_condition(vpc_macro.condition, qpc_project)


def write_include(vpc_include, qpc_project):
    qpc_include_path = vpc_include.values[0].replace(".vpc", ".qpc")
    qpc_include_path = os.path.normpath(qpc_include_path)
    qpc_include_path = convert_macro_casing(qpc_include_path)
    
    # HARDCODING
    if not args.no_hardcoding:
        qpc_include_path = qpc_include_path.replace("vpc_scripts", "_qpc_scripts")
    
    # leave a gap in-between
    if len(qpc_project) > 0 and not qpc_project[-1].startswith("include") and qpc_project[-1][-1] != "\n":
        qpc_project.append("")
    
    qpc_project.append("include \"" + qpc_include_path.replace("\\", "/") + "\"")
    write_condition(vpc_include.condition, qpc_project)


def write_files_block(vpc_files, qpc_project, indent):
    libraries = []
    for file_block in vpc_files.items:
        
        key = file_block.key.casefold()
        
        if key == "$folder" and not file_block.values[0].casefold() == "link libraries":
            
            # if "}" in qpc_project[-1]:
            if "{" not in qpc_project[-1]:
                qpc_project[-1] += "\n"
            
            qpc_project.append(indent + "folder \"" + file_block.values[0] + '"')
            write_condition(file_block.condition, qpc_project)
            qpc_project.append(indent + "{")
            nothing, qpc_project = write_files_block(file_block, qpc_project, indent + "\t")
            qpc_project.append(indent + "}")
        
        elif key in FILE_KEYS:
            if file_block.values[0].endswith(".lib"):
                libraries.append(file_block)
            else:
                qpc_project = write_file(file_block, qpc_project, indent)
        
        elif key == "$folder" and file_block.values[0] == "Link Libraries":
            libraries.extend(file_block.items)
            
        elif key in SPECIAL_FILE_KEYS:
            print("what the fuck: " + key)
    
    return libraries, qpc_project


def write_file(file_block, qpc_project, indent):
    if file_block.key.casefold() in FILE_KEYS:
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
        
        write_condition(file_block.condition, qpc_project)
        
        if file_block.items:
            file_config = Configuration()
            
            for file_config_block in file_block.items:
                parse_configuration(file_config_block, file_config)
            
            # useless?
            # config = MergeConfigurations(file_config)

            config_lines = write_config_group(file_config.groups["compiler"], indent[:-2])
            qpc_project.extend(config_lines)
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
            config_option.add_value("- " + lib_name, library.condition)
        else:
            config_option.add_value(lib_name, library.condition)
    
    # might be a bad idea
    if library_paths:
        for lib_path in library_paths:
            config.groups["general"]["library_directories"].add_value('"' + os.path.splitext(lib_path)[0] + '"', None)
    return


# might be skipping this if it has a condition?
# maybe return any paths found and add that into the configuration?
def WriteLibraries(libraries_block, linker_libraries, qpc_project, macros):
    qpc_project.append("libraries")
    if libraries_block:
        write_condition(libraries_block.condition, qpc_project)
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
            
            write_condition(library.condition, qpc_project)
        
        if linker_libraries:
            qpc_project[-1] += "\n"
    
    for library, condition in linker_libraries.items():
        if library == '"%(AdditionalDependencies)"':
            continue
        
        lib_path = library.replace("\\", "/")
        
        lib_path = lib_path.replace(macros["$_STATICLIB_EXT"], "")
        lib_path = lib_path.replace(macros["$_IMPLIB_EXT"], "")
        
        qpc_project.append("\t" + lib_path)
        
        write_condition(condition, qpc_project)
    
    qpc_project.append("}\n")


def parse_config_option(condition, option_block, qpc_option, option_values: list):
    condition = normalize_platform_conditions(condition)
    # ew
    if option_block.key.casefold() == "$multiprocessorcompilation":
        if option_block.values and option_block.values[0] == "True":
            option_values = ["/MP"]
    # ew again
    elif option_block.key.casefold() == "$disablespecificwarnings":
        if option_block.values:
            option_values = [option_block.values[0].replace(";", ";/ignore:")]
    # ew yet again
    elif option_block.key.casefold() == "$excludedfrombuild":
        if option_block.values:
            if option_block.values[0] == "No":
                option_values = "True"
            elif option_block.values[0] == "Yes":
                option_values = "False"
    
    if option_block.key.casefold() == "$commandline":
        for index, value in enumerate(option_values):
            option_values[index] = value.replace('"', '\\"').replace('$QUOTE', '\\"')
        
        # don't split this into a list
        qpc_option.set_value(option_values, condition, False)
        
    elif option_block.key.casefold() in ("$gcc_extracompilerflags", "$gcc_extralinkerflags", "$optimizerlevel"):
        qpc_option.set_value(option_values, condition, [','])  # only split by commas (i think?)
    else:
        qpc_option.set_value(option_values, condition, [',', ';', ' '])


def parse_configuration(vpc_config: reader.QPCBlock, qpc_config, dependencies: dict = None):
    if vpc_config.values:
        config_cond = "$" + vpc_config.values[0].upper()
        if vpc_config.condition:
            config_cond += "&&" + vpc_config.condition
    else:
        config_cond = vpc_config.condition
    
    for config_group in vpc_config.items:
        if config_group.key.casefold() in IGNORE_CONFIG_GROUPS:
            continue
            
        config_group_name = convert_config_group_name(config_group.key)
        
        if not config_group_name:
            # config_group.warning("Unknown config group: ")
            print("Unknown config group: " + config_group.key.casefold())
            continue
        
        for option_block in config_group.items:
            if option_block.key.casefold() in IGNORE_CONFIG_KEYS:
                continue
                
            config_group_name = convert_vpc_group(option_block.key, config_group.key)
            option_name = convert_config_option_name(option_block.key)
            
            if config_group_name in EVENTS:
                if option_block.key.casefold() == "$commandline":
                    option_values = option_block.values
                else:
                    continue
            
            elif not option_name:
                if not option_block.values:
                    continue
                option_values = convert_to_qpc_option(option_block.values)
                
                if not option_values:
                    # option_block.warning("Unknown config option: " + option_block.key.casefold())
                    print("Unknown config option: " + option_block.key.casefold() + " - " + " ".join(option_block.values))
                    continue
                else:
                    option_name = "options"
            else:
                option_values = convert_bool_to_vs_cmd(option_block)
                if not option_values:
                    option_values = convert_option(option_block.values)
            
            if option_values:
                if option_block.key.casefold() == "$additionalprojectdependencies":
                    for value in option_values:
                        if "$BASE" in value:
                            value = value.replace("$BASE;", "").replace(";$BASE", "").replace("$BASE", "")
                        dependencies[value] = add_config_condition(option_block, config_group, config_cond)
                    
                elif config_group_name in qpc_config.options:
                    parse_config_option(config_cond, option_block, qpc_config.options[config_group_name], option_values)
                    
                elif config_group_name in qpc_config.groups:
                    try:
                        qpc_option = qpc_config.groups[config_group_name][option_name]
                    except KeyError:
                        # option_block.warning("Unknown config option 2: " + option_block.key.casefold())
                        print("Unknown config option 2: " + option_block.key.casefold())
                        continue
                            
                    condition = add_config_condition(option_block, config_group, config_cond)
                    
                    option_values = add_options_prefix(option_block, option_values)
                        
                    parse_config_option(condition, option_block, qpc_option, option_values)
                else:
                    print("unknown config group/option")
    
    return


def add_config_condition(option_block: reader.QPCBlock, config_group: reader.QPCBlock, config_cond: str) -> str:
    condition = normalize_platform_conditions(option_block.condition)
    
    # if the group has a condition, add that onto every value here
    if config_group and config_group.condition:
        if condition:
            # TODO: test this, never ran into this yet, so im hoping this works
            group_condition = normalize_platform_conditions(config_group.condition)
            
            if condition != group_condition:
                condition = normalize_platform_conditions(
                    option_block.condition + "&&" + group_condition)
        else:
            condition = normalize_platform_conditions(config_group.condition)
    
    # if this option is in a specific config, add a config condition to it
    if config_cond:
        condition = add_condition(condition, config_cond, "&&")
        
    return condition


def convert_config_group_name(group_name: str) -> str:
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


def convert_config_option_name(option_name) -> str:
    option_name = option_name.casefold()
    try:
        return OPTION_NAME_CONVERT_DICT[option_name]
    except KeyError:
        pass


def convert_option(option_value: list) -> list:
    if option_value:
        try:
            return [OPTION_VALUE_CONVERT_DICT[option_value[0]]]
        except KeyError:
            return option_value
    else:
        pass


def convert_vpc_group(option_name: str, current_group) -> str:
    option_name = option_name.casefold()
    try:
        return CONFIG_GROUP_CONVERT_DICT[option_name]
    except KeyError:
        # convert it again, since we might of changed it in the previous option
        return convert_config_group_name(current_group)


def convert_to_qpc_option(option_value: str):
    if option_value:
        try:
            return [CMD_CONVERT[option_value[0]]]
        except KeyError:
            return None
    else:
        return None


def convert_bool_to_vs_cmd(option_block: reader.QPCBlock) -> list:
    if option_block.key and option_block.values:
        try:
            return [VS_BOOL_CONVERT[option_block.key.casefold()][option_block.values[0]]]
        except KeyError:
            pass


def add_options_prefix(option_block: reader.QPCBlock, option_values: list) -> list:
    if option_block.key and option_values:
        key = option_block.key.casefold()
        if key in OPTION_PREFIX_ADD:
            return [OPTION_PREFIX_ADD[key] + value for value in option_values]
    return option_values
    
    
def write_config_option(indent: str, option):
    current_option = []
    if option.value:
        if option.is_list:
            current_option = [indent + "\t" + option.name]
            option_lines = []
            cond_values = {}
            for value_obj in option.value:
                base.add_dict_value(cond_values, value_obj.condition, list)
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
                                write_condition(condition, option_lines)
                                option_lines.append(indent + "\t\t" + value)
                    else:
                        option_lines[-1] += " ".join(value_list)
                    
                    # would be cool if i could get the conditionals indented the same amount
                    write_condition(condition, option_lines)
            
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
                write_condition(value_obj.condition, option_lines)
            current_option += option_lines
            
            # current_group.append(indent + "\t" + option.name + " " + option.value + '')
            # WriteCondition(option.condition, current_group)
            
    return current_option


def write_file_configuration(config: Configuration, indent: str, qpc_project_list: list):
    config_lines = write_config_group(config.groups["compiler"], indent[:-2])
    qpc_project_list.extend(config_lines)
    return qpc_project_list


def _config_add_space(config_lines: list, indent: str):
    if config_lines and "}" in config_lines[-1] and not config_lines[-1].endswith("\n"):
        config_lines.append(indent + "\t")


def write_config_group(config_group: dict, indent: str) -> list:
    current_group = [indent + "\t{"]
    
    for option in config_group.values():
        option_lines = write_config_option(indent + "\t", option)
        if option_lines:
            if current_group:
                # add indenting
                if "}" in current_group[-1] and not current_group[-1].endswith("\n") or \
                        (option.is_list and "{" not in current_group[-1]):
                    current_group.append(indent + "\t\t")
            current_group.extend(option_lines)
    
    if len(current_group) > 1:
        current_group.append(indent + "\t}")
        return current_group
    else:
        return []
            

def write_configuration(config: Configuration, indent: str, qpc_project_list: list):
    starting_config_lines = [indent + "configuration", indent + "{"]
    config_lines = []
    
    for config_group, config_option_dict in config.groups.items():
        config_group_written = write_config_group(config_option_dict, indent)
        if config_group_written:
            _config_add_space(config_lines, indent)
            config_lines += [indent + "\t" + config_group, *config_group_written]
            
    for config_option in config.options.values():
        # current_option = [indent + "\t" + config_option.name, indent + "\t{"]
        option_lines = write_config_option(indent, config_option)
        if option_lines:
            _config_add_space(config_lines, indent)
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
    arg_parser.add_argument("-q", "--quiet", default=0, type=int, help="type of stuff to hide, 1 is converting")
    arg_parser.add_argument("-nh", "--nohardcoding", dest="no_hardcoding", action="store_true", help="don't do some of the hardcoding")
    return arg_parser.parse_args()


def main():
    print("\nConverting VPC Scripts to QPC Scripts")
    
    print("Finding All VPC and VGC Scripts")
    vgc_path_list, vpc_path_list = get_vpc_scripts(args.directory)
    
    if vgc_path_list:
        print("\nConverting VGC Scripts")
        for vgc_path in vgc_path_list:
            if args.quiet < 1:
                print("Converting: " + vgc_path)
            read_vgc, vgc_dir, vgc_name = prepare_vpc_file(vgc_path)
            convert_vgc(vgc_dir, vgc_name, read_vgc)
    
    if vpc_path_list:
        print("\nConverting VPC Scripts")
        
        for vpc_path in vpc_path_list:
            # TODO: maybe make a keep comments option in ReadFile()? otherwise, commented out files won't be kept
            if args.quiet < 1:
                print("Converting: " + vpc_path)
            read_vpc, vpc_dir, vpc_name = prepare_vpc_file(vpc_path)
            convert_vpc(vpc_dir, vpc_name, read_vpc)
    
    print("finished")


if __name__ == "__main__":
    args = parse_args()
    args.directory = args.directory.replace("\\", "/")
    args.output = args.output.replace("\\", "/")
    main()
