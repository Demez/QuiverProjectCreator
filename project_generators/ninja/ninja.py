import sys
import os
import json
from enum import Enum

# from qpc_args import args
import qpc_hash
from qpc_base import BaseProjectGenerator, Platform, create_directory
from qpc_project import ConfigType, Language, ProjectContainer, ProjectPass, Configuration
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
            script = json.dumps(commands_list, indent=4)
            with open(f"build_ninja/{label}.ninja", "w") as file_io:
                file_io.write(script)
    
    def create_project(self, project: ProjectContainer) -> None:
        project_passes = self._get_passes(project)
        if not project_passes:
            return

        print_color(Color.CYAN, "Adding to Ninja: " + project.file_name)
        
        for proj_pass in project_passes:
            self.cmd_gen.set_mode(proj_pass.config.general.compiler)
            label = f"{proj_pass.config_name.lower()}_{proj_pass.platform.name.lower()}_{proj_pass.arch.name.lower()}"
            if label not in self.all_files:
                self.all_files[label] = set()
            if label not in self.commands_list:
                self.commands_list[label] = []
                
            for file in proj_pass.source_files:
                if file not in self.all_files[label]:
                    self.all_files[label].add(file)
                    self.commands_list[label].append(self.handle_file(file, proj_pass))

    # Build definition for file
    # TODO: only supports objects rn, add so and exe support
    def handle_file(self, file: str, project: ProjectPass) -> str:
        cmd = f"build {file}.o: cc {file}\n"
        
        defs = " ".join(self.cmd_gen.convert_defines(project.config.compiler.preprocessor_definitions))
        includes = " ".join(self.cmd_gen.convert_includes(project.config.general.include_directories))
        cflags = " ".join(project.config.compiler.options)
        cmd += f"    cflags = {cflags} {includes} {defs}\n"

        return cmd
