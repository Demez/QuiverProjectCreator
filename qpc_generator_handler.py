import sys
import os
# import qpc_hash
from enum import Enum
from glob import glob
from qpc_args import args
from qpc_base import BaseProjectGenerator, QPC_DIR, QPC_GENERATOR_DIR, post_args_init


GENERATOR_FOLDER = os.path.split(QPC_GENERATOR_DIR)[1]
GENERATOR_PATH = QPC_GENERATOR_DIR + "/**"
# GENERATOR_LIST = [module[:-3] for module in os.listdir(GENERATOR_PATH) if module[-3:] == '.py']
GENERATOR_LIST = []
GENERATOR_PATHS = []

for generator_folder in glob(GENERATOR_PATH):
    __generator = generator_folder + os.sep + os.path.split(generator_folder)[1] + ".py"
    if os.path.isfile(__generator):
        GENERATOR_LIST.append(os.path.basename(__generator)[:-3])
        GENERATOR_PATHS.append(__generator)


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
        self.project_generators_all = []
        self.project_generators = []
        
        [self._import_generator(name) for name in GENERATOR_LIST]
        [self._init_generator(project_generator_type) for project_generator_type in inheritors(BaseProjectGenerator)]
            
    def _import_generator(self, name: str):
        __import__(f"{GENERATOR_FOLDER}.{name}.{name}", locals(), globals())
        self.project_generator_modules[name] = str_to_class(f"{GENERATOR_FOLDER}.{name}.{name}")
        
    def _init_generator(self, project_generator_type: type):
        project_generator = project_generator_type()
        for index, generator_module in enumerate(self.project_generator_modules.values()):
            if project_generator_type in generator_module.__dict__.values():
                project_generator.path = generator_module.__file__.replace("\\", "/")
                project_generator.filename = os.path.basename(project_generator.path)[:-3]
                project_generator.id = index
                break
        self.project_generators_all.append(project_generator)
        
    def post_args_init(self):
        post_args_init()
        for generator in self.project_generators_all:
            if generator.filename in args.generators:
                self.project_generators.append(generator)
        [generator.post_args_init() for generator in self.project_generators]
            
    def get_generator_names(self) -> list:
        return [project_generator.output_type for project_generator in self.project_generators]
    
    def get_generator_args(self):
        return [project_generator.filename for project_generator in self.project_generators_all]
    
    def get_generators(self, generator_names: list) -> list:
        return [self.get_generator(name) for name in generator_names]
            
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

