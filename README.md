# REQUIRES PYTHON 3.7+ AND LXML INSTALLED
For Windows, install lxml with `py -m pip install lxml`
For Linux, install lxml with `python3 -m pip install lxml`

# Quiver Project Creator

Generates projects for different build systems, scroll down for supported build systems.

This is inspired by Valve's VPC (Valve Project Creator).

It aims to retain the good elements of VPC (simplicity, ease of use, extensibility and configurability, "direct" access to compiler options and the like)

...but improve the areas where VPC failed (multi-platform support, speed, syntax, modernization)

We also want this to be better documented - eventually. Right now, you can look at some example scripts [here](https://github.com/Demez/demez_asw_base/tree/master/_qpc_scripts)

## Command Line Values:
 - all caps on a word like `NAME` is a single string
 - a value with `[]` around it like `[NAMES]` is a list, for multiple values

## Command Line usage:

```
-d  --rootdir DIR       Change the current working directory of the script

-b  --basefile FILE     Set the path to the base script to use

-f  --force             Force Regenerate All Projects

-fm --force_master      Force Regenerate Master File

-v  --verbose           Enable verbose console output

-w  --hidewarnings      Suppress all warnings

-cf --checkfiles        Check if all files added exists

-t  --time              Display the time taken to parse projects, generate projects and master files

-s  --skipprojects      Skip Generating projects, useful for working on master files in generators

-mf --masterfile NAME   Create a master file to build all projects with (ex. vstudio solution)

-m  --macros [names]    Set global macros. (ex: -m HL2 is equal to macro HL2 "1", -m "VIDEOPROVIDER=MPV" is equal to macro VIDEOPROVIDER MPV)

-c  --configs []        Set configs, if no configs are set in a basefile, qpc will use "Default"
```

### Adding and removing projects:

```
-a  --add [projects/groups]     Add groups or projects

-r  --remove [projects/groups]  Don't use these projects or groups
```

### Generating for other platforms and architectures

This option allows you to generate projects for multiple different platforms and architectures at a time

It Defaults to the current platform and arch you are on
```
-p  --platforms []

-ar --archs []
```
Current Platforms:
- windows
- linux
- macos

Current Architectures:
- i386
- amd64
- arm
- arm64

### Project Generators:

Choosing project generators to use is done with adding any valid generator name into the input list here

```
-g  --generators [generators]     Project types to generate
```

Current Project Generators:

```
visual_studio       Create Visual Studio Projects

makefile            Create Makefiles

compile_commands    Create files in the compile_commands.json format, stored in compile_commands folder

ninja               Create ninja build scripts in build_ninja in the directory qpc is called from (or from --rootdir)

cmake               Create CMakeLists.txt files where the project script is located, also works with multiple in the same folder

vsc                 Create A basic vscode file with paths setup for the compile_commands generator
```

You can make your own project generator by looking at [this page on the wiki](https://github.com/quiverteam/QuiverProjectCreator/wiki/Creating-your-own-generator)
