# Quiver Project Creator

Project Creator based off of Valve's VPC (Valve Project Creator) in Python 3.7

Will support many project types to generate and many platforms

## Command Line usage:

`/rootdir` or `/dir` - Change the current working directory of the script

`/basefile` - Set the path to the base script to use

`/force` or `/f` - Force Regenerate All Projects

`/verbose` or `/v` - Enable verbose console output

`/hidewarnings` or `/hide` - Suppress all warnings

`/masterfile` or `/master` - `"solution name"` - Create a master file to build all projects with (ex. visual studio solution file)

### Adding and removing projects:

`/add` - `[projects or groups]` - Add groups or projects

`/remove` or `/rm` - `[projects or groups]` Remove groups or projects

### Setting Macros in the command line:

`/macros` - `[names]` Set macros with these names to 1 to use in projects

### Project Types Supported:

Setting a project type is done with adding any valid project type name into the input list here

`/types [types]`

All of these will set a conditional to use in project scripts by the option name

Valid project Types:

`vstudio` - Create Visual Studio Projects

`vpc_convert` - Convert all vpc scripts in the root directory to qpc scrtipts

