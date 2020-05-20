import sys
import os
import json
from enum import Enum

# from qpc_args import args
import qpc_hash
from qpc_base import BaseProjectGenerator, Platform, create_directory
from qpc_project import ConfigType, Language, ProjectContainer, ProjectPass, Configuration
from project_generators.shared.cmd_line_gen import get_compiler
from qpc_parser import BaseInfo
from qpc_logging import warning, error, verbose, print_color, Color
from ..shared import cmd_line_gen


class NinjaGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("build.ninja")
        self._add_platforms(Platform.WINDOWS, Platform.LINUX, Platform.MACOS)
        
        self.cmd_gen = cmd_line_gen.CommandLineGen()
        self.commands_list = {}
        self.all_files = {}
    
    def post_args_init(self):
        pass

    def does_project_exist(self, project_out_dir: str) -> bool:
        return False
    
    def projects_finished(self):
        if not self.commands_list:
            return
        print("------------------------------------------------------------------------")
        create_directory("build_ninja")
        for label, commands_list in self.commands_list.items():
            print_color(Color.CYAN, "Writing: " + f"build_ninja/{label}.ninja")
            script = self.gen_rules()
            script += '\n\n'.join(commands_list)
            with open(f"build_ninja/{label}.ninja", "w") as file_io:
                file_io.write(script)
    
    def create_project(self, project: ProjectContainer) -> None:
        project_passes = self._get_passes(project)
        if not project_passes:
            return

        proj_name = project.file_name.replace('.', '_')

        print_color(Color.CYAN, "Adding to Ninja: " + project.file_name)

        
        for proj_pass in project_passes:
            conf = proj_pass.config
            self.cmd_gen.set_mode(proj_pass.config.general.compiler)
            label = f"{proj_pass.config_name.lower()}_{proj_pass.platform.name.lower()}_{proj_pass.arch.name.lower()}"
            if label not in self.all_files:
                self.all_files[label] = set()
            if label not in self.commands_list:
                self.commands_list[label] = []

            compiler = get_compiler(proj_pass.config.general.compiler,
                                    proj_pass.config.general.language)

            self.commands_list[label].append(self.gen_header(conf, project, compiler, proj_name))
                   
            for file in proj_pass.source_files:
                if file not in self.all_files[label]:
                    self.all_files[label].add(file)
                    self.commands_list[label].append(self.handle_file(file, proj_pass, proj_name))

            self.commands_list[label].append(self.handle_target(conf, proj_pass.source_files))

    def gen_rules(self) -> str:
        return f"""

# rules
rule cc
    command = $compiler -c -o $out $in $cflags

rule exe
    command = $compiler -o $out $in $cflags

rule ar
    command = ar rcs $out $in

rule so
    command = $compiler -o $out $in -fPIC -shared $cflags
"""

    def gen_header(self, conf, project, compiler, proj_name: str):
        outname = conf.general.out_name if conf.general.out_name else project.container.file_name
        return f"""#!/usr/bin/env ninja -f
# variables
{proj_name}_srcdir = {os.getcwd()}
out_file = {outname}
{proj_name}_compiler = {compiler}
"""

    def handle_target(self, conf, source_files) -> str:
        target_name = conf.linker.output_file if conf.linker.output_file else "$out_file"
        objs = ' '.join([ os.path.abspath(a) + '.o'  for a in source_files ])
        type, ext = {
            ConfigType.APPLICATION: ('exe', ''),
            ConfigType.DYNAMIC_LIBRARY: ('so', '.so'),
            ConfigType.STATIC_LIBRARY: ('ar', '.a')
        }[conf.general.configuration_type]

        return f"build {os.path.abspath(target_name)}{ext}: {type} {objs}\n"

    # Build definition for file
    # TODO: only supports objects rn, add so and exe support
    def handle_file(self, file: str, project: ProjectPass, proj_name: str) -> str:
        print(os.getcwd(), project)
        cmd = f"build {os.path.abspath(file)}.o: cc {os.path.abspath(file)}\n"
        
        defs = " ".join(self.cmd_gen.convert_defines(project.config.compiler.preprocessor_definitions))
        includes = " ".join(self.cmd_gen.convert_includes(project.config.general.include_directories))
        cflags = " ".join(project.config.compiler.options)
        cmd += f"    cflags = {cflags} {includes} {defs}\n"
        cmd += f"    compiler = {proj_name}_compiler\n"

        return cmd
