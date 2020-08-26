import os
import json

from qpc_base import BaseProjectGenerator, Platform, create_directory
from qpc_project import ConfigType, Language, ProjectContainer, ProjectPass, Configuration
from qpc_logging import warning, error, verbose, print_color, Color
from ..shared import cmd_line_gen
from typing import List


class VSCGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("vscode")
        self._add_platforms(Platform.WINDOWS, Platform.LINUX, Platform.MACOS)

        self.cmd_gen = cmd_line_gen.CommandLineGen()
        self.commands_list = {}
        self.all_files = {}

    def post_args_init(self):
        pass

    def does_project_exist(self, project_out_dir: str) -> bool:
        return False

    def projects_finished(self):
        ball: dict = {
        "configurations": [],
        "version": 4,
    }
        if not self.commands_list:
            return
        print("------------------------------------------------------------------------")
        create_directory(".vscode")
        for label, commands_list in self.commands_list.items():
            ball["configurations"].append(commands_list)
        print_color(Color.CYAN, "Writing: " + f".vscode/c_cpp_properties.json")
        compile_commands = json.dumps(ball, indent=4)
        with open(f".vscode/c_cpp_properties.json", "w") as file_io:
            file_io.write(compile_commands)

    def create_project(self, project: ProjectContainer) -> None:
        project_passes: List[ProjectPass] = self._get_passes(project)
        if not project_passes:
            return

        print_color(Color.CYAN, "Adding to Compile Commands: " + project.file_name)

        for proj_pass in project_passes:
            self.cmd_gen.set_mode(proj_pass.cfg.general.compiler)
            label = f"{proj_pass.cfg_name.lower()}_{proj_pass.platform.name.lower()}_{proj_pass.arch.name.lower()}"
            if label not in self.all_files:
                self.all_files[label] = set()
            if label not in self.commands_list:
                self.commands_list[label] = self.handle_file(proj_pass, label)

    def handle_file(self, project: ProjectPass, label: str) -> dict:
        file_dict = {
            "name": label,
            "includePath": ["${workspaceFolder}/**"],
            "defines": [],
            "compilerPath": "/usr/bin/gcc",
            "cStandard": "gnu11",
            "cppStandard": "gnu++14",
            "intelliSenseMode": "gcc-x64",
            "compileCommands": f"compile_commands/{label}.json"
        }
        return file_dict




