import sys
import os

from qpc_base import BaseProjectGenerator, Platform, create_directory
from qpc_project import ConfigType, Language, ProjectContainer, ProjectPass, Configuration, General, SourceFileCompile
from qpc_parser import BaseInfo
from qpc_logging import warning, error, verbose, print_color, Color, verbose_color
from ..shared.cmd_line_gen import get_compiler, Mode
from ..shared import cmd_line_gen
from ..shared import msvc_tools
from typing import List


class NinjaGenerator(BaseProjectGenerator):
    def __init__(self):
        super().__init__("build.ninja")
        self._add_platforms(Platform.WINDOWS, Platform.LINUX, Platform.MACOS)
        
        self.cmd_gen = cmd_line_gen.CommandLineGen()
        self.commands_list = {}
        self.all_files = {}
        self.output_files = {}
        self.dependencies = {}
    
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
            
            for item, deps in self.dependencies.items():
                if item in self.output_files[label]:
                    out_file, command = self.output_files[label][item]
                    if command in commands_list:
                        new_command = command.split("\n")
                        dep_list = self.get_dependencies(label, deps)
                        new_command[0] += " || " + " ".join(dep_list)
                        commands_list[commands_list.index(command)] = "\n".join(new_command)
            
            script += '\n\n'.join(commands_list)
            with open(f"build_ninja/{label}.ninja", "w") as file_io:
                file_io.write(script)
    
    def get_dependencies(self, label: str, dep_list: list) -> list:
        output_list = []
        for dep in dep_list:
            if dep in self.output_files[label]:
                output_list.append(self.output_files[label][dep][0])
        return output_list
    
    def create_project(self, project: ProjectContainer) -> None:
        project_passes: List[ProjectPass] = self._get_passes(project)
        if not project_passes:
            return
        
        proj_name = project.file_name.replace('.', '_').replace(':', '$')
        
        print_color(Color.CYAN, "Adding to Ninja: " + project.file_name)
            
        if project.dependencies:
            self.dependencies[project.project_path] = project.dependencies.copy()
        
        for proj_pass in project_passes:
            conf = proj_pass.cfg
            self.cmd_gen.set_mode(proj_pass.cfg.general.compiler)
            label = f"{proj_pass.cfg_name.lower()}_{proj_pass.platform.name.lower()}_{proj_pass.arch.name.lower()}"
            
            if label not in self.all_files:
                self.all_files[label] = set()
            if label not in self.commands_list:
                self.commands_list[label] = []
            if label not in self.output_files:
                self.output_files[label] = {}
            
            compiler = get_compiler(proj_pass.cfg.general.compiler,
                                    proj_pass.cfg.general.language)
            
            self.commands_list[label].append(self.gen_header(conf, project, compiler, proj_name))
            
            for file, file_compile in proj_pass.source_files.items():
                self.commands_list[label].append(self.handle_file(file, file_compile.compiler, proj_pass, proj_name))
            
            output_file = self.handle_target(proj_pass, proj_name, proj_pass.source_files)
            self.commands_list[label].append(output_file)
            self.output_files[label][project.project_path] = (self.get_output_file(proj_pass), output_file)
            
    @staticmethod
    def gen_rules_gcc_clang(compiler: str):
        return f"""

rule cc_{compiler}
    command = $compiler -c -o $out $in $cflags

rule exe_{compiler}
    command = $compiler -o $out $in $cflags

rule ar_{compiler}
    command = ar rcs $out $in

rule so_{compiler}
    command = $compiler -o $out $in -fPIC -shared $cflags
"""

    def gen_rules(self) -> str:
        rules = f"""
rule cc_msvc
    command = $compiler /nologo /Fd"$out.pdb" /Fo"$out" /c $in $cflags

rule exe_msvc
    command = link.exe /OUT:$out @$out.rsp $cflags
    rspfile = $out.rsp
    rspfile_content = $in

rule ar_msvc
    command = lib.exe /OUT:$out @$out.rsp $cflags
    rspfile = $out.rsp
    rspfile_content = $in

rule so_msvc
    command = link.exe /DLL /OUT:$out @$out.rsp $cflags
    rspfile = $out.rsp
    rspfile_content = $in
"""
        # command = link.exe /DLL /OUT:$out $in $cflags
        
        rules += self.gen_rules_gcc_clang("gcc")
        rules += self.gen_rules_gcc_clang("clang")
        
        return f"\n# rules" + rules + "\n\n" \
               "rule mkdir\n    command = mkdir \"$out\"\n\n"

    def gen_header(self, conf: Configuration, project: ProjectContainer, compiler: str, proj_name: str):
        outname = conf.general.out_name if conf.general.out_name else project.file_name
        # {proj_name}_build_dir = {abs_path(conf.general.build_dir)}
        return f"""#!/usr/bin/env ninja -f
# variables
{proj_name}_src_dir = {os.getcwd()}
out_file = {outname}
{proj_name}_compiler = {compiler}
{proj_name}_build_dir = {os.path.abspath(conf.general.build_dir)}

build ${proj_name}_build_dir: mkdir ${proj_name}_build_dir
"""
    
    def get_file_build_path(self, proj_name: str, general: General, file: str):
        return os.path.abspath(self.cmd_gen.get_file_build_path(general, file)).replace(':', '$:')
        # return f"${proj_name}_src_dir/{self.cmd_gen.get_file_build_path(general, file)}"
    
    @staticmethod
    def get_target_type_ext(project: ProjectPass) -> tuple:
        target_type, ext = {
            ConfigType.APPLICATION: ('exe', project.macros["EXT_APP"]),
            ConfigType.DYNAMIC_LIB: ('so', project.macros["EXT_DLL"]),
            ConfigType.STATIC_LIB: ('ar', project.macros["EXT_LIB"])
        }[project.cfg.general.config_type]
        return (target_type, ext)
    
    def get_output_file(self, project: ProjectPass):
        target_name = project.cfg.link.output_file if project.cfg.link.output_file else project.cfg.general.out_name
        return f"{abs_path(target_name)}{self.get_target_type_ext(project)[1]}"

    # TODO: handle dependencies
    def handle_target(self, project: ProjectPass, proj_name: str, source_files) -> str:
        obj_files = " ".join([self.get_file_build_path(proj_name, project.cfg.general, a) for a in source_files])

        target_name = self.get_output_file(project)
        target_type, ext = self.get_target_type_ext(project)

        build = f"build {target_name}: {target_type}_{self.cmd_gen.mode.name.lower()} {obj_files}"
        
        link_flags = add_escapes(self.cmd_gen.link_flags(project.cfg, libs=False))
        link_flags += " " + " ".join(self.cmd_gen.lib_dirs([""]))
        
        # slightly hacky, oh well
        libs = [f"${proj_name}_src_dir/{lib}" if "/" in lib else lib for lib in project.cfg.link.libs]
        libs = " ".join(self.cmd_gen.libs(libs))

        return f"{build}\n    cflags = {link_flags} {libs}\n"

    # Build definition for file
    def handle_file(self, file: str, file_compile: SourceFileCompile, proj: ProjectPass, proj_name: str) -> str:
        # print(os.getcwd(), project)
        build_path = self.get_file_build_path(proj_name, proj.cfg.general, file)
        cmd = f"build {build_path}: cc_{self.cmd_gen.mode.name.lower()} {abs_path(file)}\n"
        cmd += f"    cflags = {add_escapes(self.cmd_gen.file_compile_flags(proj.cfg, file_compile))}\n"
        cmd += f"    compiler = ${proj_name}_compiler\n"
        return cmd
    
    
def add_escapes(string: str) -> str:
    return string.replace('$', '$$').replace(':', '$:')


def abs_path(path: str) -> str:
    return add_escapes(os.path.abspath(path))

