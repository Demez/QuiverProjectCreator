import sys
import os
import qpc_hash
from enum import Enum
from qpc_args import args
from qpc_base import BaseProjectGenerator


GENERATOR_PATH = os.path.dirname(__file__) + "/project_generators"
generator_list = [module[:-3] for module in os.listdir(GENERATOR_PATH) if module[-3:] == '.py']


def str_to_class(class_name: str):
    # return getattr(sys.modules[__name__], class_name)
    return sys.modules[class_name]


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
            else:
                print("Warning: Invalid Generator: " + project_generator_name)
            
        self.project_generators = []
        for project_generator_type in inheritors(BaseProjectGenerator):
            project_generator = project_generator_type()
            for generator_module in self.project_generator_modules.values():
                if project_generator_type in generator_module.__dict__.values():
                    project_generator.path = generator_module.__file__.replace("\\", "/")
                    break
            self.project_generators.append(project_generator)
            
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

