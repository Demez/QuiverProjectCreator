import sys
import os
import qpc_hash
from enum import Enum
from qpc_args import args
from qpc_base import BaseProjectGenerator

'''
for module in os.listdir(os.path.dirname(__file__) + "/project_generators"):
    if module[-3:] == '.py':
        __import__("project_generators." + module[:-3], locals(), globals())
'''

generator_list = []
for module in os.listdir(os.path.dirname(__file__) + "/project_generators"):
    if module[-3:] == '.py':
        generator_list.append(module[:-3])


def str_to_class(classname):
    # return getattr(sys.modules[__name__], classname)
    return sys.modules[classname]


# https://stackoverflow.com/questions/5881873/python-find-all-classes-which-inherit-from-this-one
def inheritors(klass):
    subclasses = set()
    work = [klass]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return subclasses
    
    
class GeneratorHandler:
    def __init__(self):
        self.project_generator_modules = {}
        for project_generator_name in args.generators:
            if project_generator_name in generator_list:
                __import__("project_generators." + project_generator_name, locals(), globals())
                self.project_generator_modules[project_generator_name] = \
                    str_to_class("project_generators." + project_generator_name)
            
        self.project_generators = []
        for project_generator_type in inheritors(BaseProjectGenerator):
            self.project_generators.append(project_generator_type())
            
    def get_generator_names(self) -> list:
        return [project_generator.output_type for project_generator in self.project_generators]
            
    def get_generator(self, generator_name: str) -> BaseProjectGenerator:
        for project_generator in self.project_generators:
            if project_generator.output_type == generator_name:
                return project_generator
            
    def get_generator_supported_platforms(self, generator_name: str) -> list:
        generator = self.get_generator(generator_name)
        if generator:
            return generator.get_supported_platforms()
            
    def does_project_exist(self, project_path: str, generator_name: str) -> bool:
        generator = self.get_generator(generator_name)
        if generator:
            return generator.does_project_exist(project_path)


def FindProject(project_path: str, project_type: Enum = None) -> bool:
    # we can't check this if we are putting it somewhere else
    # we would have to parse first, then check
    if args.project_dir:
        return True
    
    base_path, project_name = os.path.split(project_path)
    split_ext_path = os.path.splitext(project_path)[0]
    base_path += "/"

    # if project_type == OutputTypes.VISUAL_STUDIO:
    if "vstudio" in args.types:
        return os.path.isfile(split_ext_path + ".vcxproj") and os.path.isfile(split_ext_path + ".vcxproj.filters")

    # elif project_type == OutputTypes.MAKEFILE:
    if "makefile" in args.types:
        # return path.isfile(split_ext_path + ".makefile")
        return os.path.isfile(base_path + "makefile")


def FindMasterFile(file_path):
    base_path, project_name = os.path.split(file_path)
    split_ext_path = os.path.splitext(file_path)[0]
    base_path += "/"
    if "vstudio" in args.types:
        if os.path.isfile(split_ext_path + ".sln"):
            return True
        else:
            return False
