import sys
import os
import json
from enum import Enum

# from qpc_args import args
import qpc_hash
from qpc_base import BaseProjectGenerator, Platform, create_directory
from qpc_project import Compiler, ConfigType, Language, ProjectContainer, ProjectPass, Configuration
from qpc_parser import BaseInfo
from ..shared import cmd_line_gen


class CompileCommandsGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("compile_commands.json")
        self._add_platform(Platform.WIN32)
        self._add_platform(Platform.WIN64)
        self._add_platform(Platform.LINUX32)
        self._add_platform(Platform.LINUX64)
        self._add_platform(Platform.MACOS)
        # self._set_generate_master_file(True)
        
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
        create_directory("compile_commands")
        for label, commands_list in self.commands_list.items():
            print("Writing: " + f"compile_commands/{label}.json")
            compile_commands = json.dumps(commands_list, indent=4)
            with open(f"compile_commands/{label}.json", "w") as file_io:
                file_io.write(compile_commands)
    
    def create_project(self, project: ProjectContainer) -> None:
        project_passes = self._get_passes(project)
        if not project_passes:
            return

        print("Adding to Compile Commands: " + project.file_name)
        
        for project_pass in project_passes:
            self.cmd_gen.set_mode(project_pass.config.general.compiler)
            label = f"{project_pass.config_name.lower()}_{project_pass.platform.name.lower()}"
            if label not in self.all_files:
                self.all_files[label] = set()
            if label not in self.commands_list:
                self.commands_list[label] = []
                
            all_files = project_pass.source_files
            for file in all_files:
                if file not in self.all_files[label]:
                    self.all_files[label].add(file)
                    self.commands_list[label].append(self.handle_file(file, project_pass))
            
    def handle_file(self, file: str, project: ProjectPass) -> dict:
        file_dict = {
            "directory": os.getcwd().replace("\\", "/"),
            "command": self.cmd_gen.get_compiler_path(project.config.general.language) + " ",
            "file": file
        }
        
        file_dict["command"] += " ".join(self.cmd_gen.convert_defines(project.config.compiler.preprocessor_definitions))
        file_dict["command"] += " " + " ".join(self.cmd_gen.convert_includes(project.config.general.include_directories))
        
        file_dict["command"] += " " + " ".join(project.config.compiler.options)
        if f"{self.cmd_gen.switch}c" not in project.config.compiler.options:
            file_dict["command"] += f" {self.cmd_gen.switch}c"
            
        file_dict["command"] += " " + file
        
        return file_dict
        
        


