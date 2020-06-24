import os
import sys


def get_inc_dirs(version: str) -> list:
    return MSVC_DEFAULT_INC_DIRS.copy()


def get_lib_dirs(version: str) -> list:
    return MSVC_DEFAULT_LIB_DIRS.copy()


# stupid and ugly, and these are for the latest msvc version
# should attempt to set something up that can grab the correct directories for these files based on your msvc version
# and where they are on your computer
MSVC_DEFAULT_LIB_DIRS = [
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Tools\\MSVC\\14.25.28610\\lib\\x86",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Tools\\MSVC\\14.25.28610\\atlmfc\\lib\\x86",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Auxiliary\\VS\\lib\\x86",
    "C:\\Program Files (x86)\\Windows Kits\\10\\lib\\10.0.18362.0\\ucrt\\x86",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Auxiliary\\VS\\UnitTest\\lib",
    "C:\\Program Files (x86)\\Windows Kits\\10\\lib\\10.0.18362.0\\um\\x86",
    "C:\\Program Files (x86)\\Windows Kits\\NETFXSDK\\4.8\\lib\\um\\x86"
]

MSVC_DEFAULT_INC_DIRS = [
    # base includes
    # $(VC_IncludePath)
    # $(WindowsSDK_IncludePath)
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Tools\\MSVC\\14.25.28610\\include",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Tools\\MSVC\\14.25.28610\\atlmfc\\include",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Auxiliary\\VS\\include",
    "C:\\Program Files (x86)\\Windows Kits\\10\\Include\\10.0.18362.0\\ucrt",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Auxiliary\\VS\\UnitTest\\include",
    "C:\\Program Files (x86)\\Windows Kits\\10\\Include\\10.0.18362.0\\um",
    "C:\\Program Files (x86)\\Windows Kits\\10\\Include\\10.0.18362.0\\shared",
    "C:\\Program Files (x86)\\Windows Kits\\10\\Include\\10.0.18362.0\\winrt",
    "C:\\Program Files (x86)\\Windows Kits\\10\\Include\\10.0.18362.0\\cppwinrt",
    "C:\\Program Files (x86)\\Windows Kits\\NETFXSDK\\4.8\\Include\\um",
    
    # other mfc and atl crap
    # $(VC_SourcePath)
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Tools\\MSVC\\14.25.28610\\atlmfc\\src\\mfc",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Tools\\MSVC\\14.25.28610\\atlmfc\\src\\mfcm",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Tools\\MSVC\\14.25.28610\\atlmfc\\src\\atl",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Tools\\MSVC\\14.25.28610\\crt\\src",
    "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\VC\\Auxiliary\\VS\\src",
    "C:\\Program Files (x86)\\Windows Kits\\10\\Source\\10.0.18362.0\\ucrt",
]


