# PyQuiverProjectCreator
Recreation of Valve's VPC (Valve Project Creator) in Python 3.7

## Command Line usage:

`+name` Add a group or a project

`-name` Remove a group or a project

`/f` Force Regenerate All Projects

`/verbose` Enable verbose console output

`/hidewarnings` Hide any warnings found in the project scripts

`/showlegacyoptions` Show any Configuration options using the legacy key

`/name` Enable a conditional to use in projects, which are defined in the $CommandLineConditionals Block

`/mksln "solution name"` Create a solution file to build all projects with

### Project Types Supported:

All of these will set a conditional to use in project scripts by the option name

`/vstudio` - Create Visual Studio Projects

