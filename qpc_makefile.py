import sys
import os

import qpc_c_parser as cp

header_extensions = [
    'h',
    'hh',
    'hpp',
    'h++',
    'hxx'
]


def MkIfEq(a, b, body):
    return f"\nifeq ({a},{b})\n{body}\nendif\n"


def GenGnuCFlags(conf, libs=True, defs=True, includes=True):
    mk = ""
    if len(conf.compiler.preprocessor_definitions) > 0 and defs:
        mk += ' -D ' + ' -D '.join(conf.compiler.preprocessor_definitions)
    if len(conf.linker.libraries) > 0 and libs:
        mk += ' -l' + ' -l'.join(['.'.join(i.split('.')[:-1]) for i in conf.linker.libraries])
    if len(conf.general.library_directories) > 0 and libs:
        mk += ' -L' + ' -L'.join(conf.general.library_directories)
    if len(conf.general.include_directories) > 0 and includes:
        mk += ' -I' + ' -I'.join(conf.general.include_directories)
    return mk


# TODO: add a non-gnu flag option (/ instead of --, etc)
def GenCompileExeGnu(compiler, conf):
    entry = ""
    if not conf.linker.entry_point == "":
        entry = "-Wl,--entry={conf.linker.entry_point}"
    return f"@{compiler} -o $@ $(SOURCES) {entry} {GenGnuCFlags(conf)}"


def GenCompileDynGnu(compiler, conf):
    return f"@{compiler} -shared -fPIC -o $@ $(SOURCES) {GenGnuCFlags(conf)}"


def GenCompileStatGnu(compiler, conf):
    return f"@ar rcs $@ $(OBJECTS)"


def GenProjectTargets(conf):
    makefile = "\n\n# TARGETS\n\n"
    target_name = ""
    # theres got to be a better way to do this but im tired
    if conf.linker.output_file:
        target_name = conf.linker.output_file
    else:
        target_name = "$(OUTNAME)"
    
    if True:  # conf.general.toolset_version == "gcc":
        lang_switch = {"c": "gcc", "cpp": "g++", "c++": "g++"}
        compiler = lang_switch[conf.general.language]
    
    if conf.general.configuration_type == "application":
        makefile += f"{target_name}: __PREBUILD $(OBJECTS) $(FILES) __PRELINK\n"
        makefile += f"\t@echo '$(GREEN)Compiling executable {target_name}$(NC)'\n"
        makefile += '\t' + '\n\t'.join(GenCompileExeGnu(compiler, conf).split('\n'))
    
    elif conf.general.configuration_type == "dynamic_library":
        makefile += f"$(addsuffix .so,{target_name}): __PREBUILD $(OBJECTS) $(FILES) __PRELINK\n"
        makefile += f"\t@echo '$(CYAN)Compiling dynamic library {target_name + '.so'}$(NC)'\n"
        makefile += '\t' + '\n\t'.join(GenCompileDynGnu(compiler, conf).split('\n'))
    
    elif conf.general.configuration_type == "static_library":
        makefile += f"$(addsuffix .a,{target_name}): __PREBUILD $(OBJECTS) $(FILES) __PRELINK\n"
        makefile += f"\t@echo '$(CYAN)Compiling static library {target_name}.a$(NC)'\n"
        makefile += '\t' + '\n\t'.join(GenCompileStatGnu(compiler, conf).split('\n'))
    
    makefile += "\n\t" + "\n\t".join(conf.post_build)
    
    return makefile


def GenDependencyTree(objects, headers, conf):
    makefile = "\n#DEPENDENCY TREE:\n\n"
    pic = ""
    if conf.general.configuration_type == "shared_library":
        pic = "-fPIC"
    for obj in objects.keys():
        makefile += f"\n{obj}: {objects[obj]} {' '.join(cp.GetIncludes(objects[obj]))}\n"
        makefile += f"\t@echo '$(CYAN)Building Object {objects[obj]}$(NC)'\n"
        makefile += f"\t@$(TOOLSET-VERSION) -c {pic} -o $@ {objects[obj]} {GenGnuCFlags(conf, libs=False)}\n"
    
    for h in headers:
        makefile += f"\n{h}: {' '.join(cp.GetIncludes(h))}\n"
    
    return makefile


def GenCleanTarget():
    return f"""
# CLEAN TARGET:

clean:
\t@echo "Cleaning objects, archives, shared objects, and dynamic libs"
\t@rm -f $(wildcard *.o *.a *.so *.dll *.dylib)

.PHONY: clean __PREBUILD __PRELINK __POSTBUILD


"""


def GenScriptTargets(conf):
    makefile = "\n\n__PREBUILD:\n"
    makefile += '\t' + '\n\t'.join(conf.pre_build) + "\n\n"
    
    makefile += "\n\n__PRELINK:\n"
    makefile += '\t' + '\n\t'.join(conf.pre_link) + "\n\n"
    
    return makefile


# TODO: less shit name
def GenProjConfDefs(project):
    objects = {}
    for i in project.source_files:
        objects['.'.join(i.split('.')[:-1])
                    .replace('/', '\\/')
                    .replace('..', ('\\.\\.')
                             .replace(' ', '\\ ')) + '.o'] = i
    
    headers = [i for i in project.files if i.split('.')[-1] in header_extensions]
    nonheader_files = [i for i in project.files if i not in headers]
    
    makefile = "\n# SOURCE FILES:\n\n"
    makefile += "SOURCES = " + '\t\\\n\t'.join(project.source_files) + "\n"
    
    makefile += "\n#OBJECTS:\n\n"
    makefile += "OBJECTS = " + '\t\\\n\t'.join(objects.keys()) + "\n"
    
    makefile += "\n# AUX FILES:\n\n"
    makefile += "FILES = " + '\t\\\n\t'.join(nonheader_files) + "\n"
    
    makefile += "\n# MACROS:\n\n"
    try:
        makefile += "OUTNAME = " + project.macros["$PROJECT_NAME"]
    except KeyError:
        makefile += "OUTNAME = default"
    
    makefile += GenProjectTargets(project.config)
    
    makefile += GenCleanTarget()
    
    makefile += GenDependencyTree(objects, headers, project.config)
    # print(project.config)
    
    makefile += GenScriptTargets(project.config)
    
    return MkIfEq(project.config_name, "$(CONFIG)",
                  MkIfEq(project.platform, "$(PLATFORM)", makefile))


def GetPlatform():
    p = sys.platform
    if sys.maxsize > 2 ** 32:
        p += "64"
    else:
        p += "32"
    
    return p


def GenDefines(toolset):
    if toolset:
        compiler = toolset
    else:
        compiler = "gcc"
    return f"""#!/usr/bin/make -f


# MAKEFILE GENERATED BY QPC
# IF YOU ARE READING THIS AND DID NOT GENERATE THIS FILE WITH QPC,
# IT PROBABLY WILL NOT WORK. DOWNLOAD QPC AND BUILD THE MAKEFILE
# YOURSELF.


# |￣￣￣￣￣￣￣￣|  
# |    make > *    |
# |＿＿＿＿＿＿＿＿|
# (\__/) || 
# (•ㅅ•) || 
# / 　 づ  

# don't mess with this, might break stuff
PLATFORM = {GetPlatform()}
# change the config with CONFIG=[Release,Debug] to make
CONFIG = Debug
# edit this in your QPC script configuration/general/toolset-version
TOOLSET-VERSION = {compiler}


# COLORS!!!

# i realize now that this will dump binary shit into the makefile.
# i apologize in advance for anyone who decides to edit it by hand
# and who's editor refuses to open it
RED     =\033[0;31m
CYAN    =\033[0;36m
GREEN   =\033[0;32m
NC      =\033[0m

############################
### BEGIN BUILD TARGETS ###
###########################
"""


def CreateMakefile(projects):
    print("CREATING MAKEFILE")
    makefile = GenDefines(projects.projects[0].config.general.toolset_version)
    
    for p in projects.projects:
        makefile += GenProjConfDefs(p)
    
    with open("makefile", "w") as f:
        f.write(makefile)
