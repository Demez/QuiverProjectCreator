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

-fm --force_master      Force Regenerate Master File

-v  --verbose           Enable verbose console output

-w  --hidewarnings      Suppress all warnings

-mf --masterfile NAME   Create a master file to build all projects with (ex. vstudio solution)

-p  --platforms []      Pick specific platforms to build for instead of the default
```

### Adding and removing projects:

```
-a  --add [projects/groups]     Add groups or projects

-r  --remove [projects/groups]  Don't use these projects or groups
```

### Setting Macros in the command line:

```
-m  --macros [names]    Set macros with these names to 1 to use in projects
```

### Project Generators:

Choosing project generators to use is done with adding any valid generator name into the input list here

```
-g  --generators [generators]     Project types to generate
```

Current Project Generators:

```
visual_studio   Create Visual Studio Projects

makefile        Create Makefiles for every project
```

You can make your own project generator by looking at [this page on the wiki](https://github.com/quiverteam/QuiverProjectCreator/wiki/Creating-your-own-generator)
