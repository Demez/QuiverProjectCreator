# Quiver Project Creator

Project Creator based off of Valve's VPC (Valve Project Creator) in Python 3.7

Will support many project types to generate and many platforms

## Command Line Values:
 - all caps on a word like `NAME` is a single string
 - a value with `[]` around it like `[NAMES]` is a list, for multiple values

## Command Line usage:

```
-d  --rootdir DIR       Change the current working directory of the script

-b  --basefile FILE     Set the path to the base script to use

-f  --force             Force Regenerate All Projects

-v  --verbose           Enable verbose console output

-w  --hidewarnings      Suppress all warnings

-mf --masterfile NAME   Create a master file to build all projects with (ex. visual studio solution)
```

### Adding and removing projects:

```
-a  --add [projects/groups]       Add groups or projects

-r  --remove [projects/groups]    Don't use these projects or groups
```

### Setting Macros in the command line:

```
-m  --macros [names]     Set macros with these names to 1 to use in projects
```

### Project Types Supported:

Setting a project type is done with adding any valid project type name into the input list here

```
-t  --types [types]      Project types to generate
```

This will loop through each option and set a macro to "1" to use in projects

Valid Project Types:

```
vstudio       Create Visual Studio Projects

makefile      Create Makefiles for every project

vpc_convert   Convert all vpc scripts in the root directory to qpc scripts, different from all the others
```
