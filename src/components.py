import ast
import importlib
import inspect
import os
from pathlib import Path
from typing import Dict
from typing import List
from typing import NoReturn
from typing import Optional

from src.dtos import ASPoint
from src.icomponents import Component
from src.icomponents import ComponentLoader


class ModuleComponent(Component):
    name: Optional[str] = None
    path: Optional[Path] = None

    def __init__(
        self, path: Optional[Path] = None, name: Optional[str] = None, *args, **kwargs
    ):
        super().__init__(self, *args, **kwargs)
        if path and not name:
            name = self._get_name_from_path(path)

        if name and not path:
            path = self._get_path_from_name(name)

        self.path = path
        self.name = name

    @staticmethod
    def _is_abstract_class(_class):
        return inspect.isabstract(_class)

    @staticmethod
    def _get_path_from_name(name: str):
        obj = importlib.import_module(name)
        module_path = name.replace(".", "/")
        if inspect.ismodule(obj):
            path = f"{module_path}.py"
        else:
            path = f"{module_path}/__init__.py"

        return Path(path)

    @staticmethod
    def _get_name_from_path(path: Path):
        parent_name = str(path.parent).replace("/", ".")

        if "__init__.py" == path.name:
            return parent_name
        else:
            return f"{parent_name}.{path.stem}"

    def get_abstraction(self):
        self.load_classes()
        self.calculate_abstraction()
        return self.abstraction

    def depend_of(self, component_name: str):
        for component in self.external_dependencies:
            if component.name == component_name:
                return True

        return False

    def load_classes(self):
        if self.no_abstract_classes or self.abstract_classes:
            return None

        module = importlib.import_module(self.name)
        for module_name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and not self.depend_of(obj.__module__):
                self.add_class(
                    _class=obj,
                    is_abstract=self._is_abstract_class(obj),
                )

    @staticmethod
    def _import_module(module_path):
        try:
            module = importlib.import_module(module_path)
            return module
        except ImportError:
            pass

    def _eval_dependency(self, dep) -> set:
        _imports = set()

        if isinstance(dep, ast.Import):
            for alias in dep.names:
                _imports.add(alias.name)
        elif isinstance(dep, ast.ImportFrom):
            modules = set()

            for alias in dep.names:
                module_path = f"{dep.module}.{alias.name}"
                module = self._import_module(module_path)
                if module:
                    modules.add(module_path)

            _imports = _imports | modules
            if len(modules) != len(dep.names):
                _imports.add(dep.module)

        return _imports

    def get_dependencies(self):
        with open(self.path, "r") as archivo:
            tree_imports = ast.parse(archivo.read())

        _imports = set()
        for node in ast.walk(tree_imports):
            deps = self._eval_dependency(node)
            _imports = _imports | deps

        return _imports

    def load_dependencies(self, ignore_dependencies: Optional[List[str]] = None):
        if self.external_dependencies:
            return None

        dependencies = self.get_dependencies()

        for module in dependencies:
            if ignore_dependencies and module in ignore_dependencies:
                continue

            dep_comp = ModuleComponent(name=module)
            self.add_dependency(dep_comp)

    def get_instability(self, ignore_dependencies: Optional[List[str]] = None) -> float:
        self.calculate_instability()
        return self.instability


class ModuleComponentLoader(ComponentLoader):
    def __init__(self, root_path=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root_path = root_path
        self._ignore_native_library()

    def _ignore_native_library(self):
        self.ignore_deps(["abc", "typing"])

    def load_components(self, root_path: Optional[Path] = None, ignore_dependencies: Optional[List[str]] = None) -> NoReturn:
        if not root_path:
            root_path = self.root_path

        self._load_components(root_path)
        self._load_dependencies(ignore_dependencies)
        self._load_classes()

    def _load_components(self, root_path):
        for module in self.get_py_modules(root_path):
            component = ModuleComponent(path=module)
            self.components[component.name] = component

    def _load_classes(self):
        for component in self.components.values():
            component.load_classes()

    def _load_dependencies(self, ignore_dependencies: Optional[List[str]] = None):
        
        if not ignore_dependencies:
            ignore_dependencies = []
        
        ignore_dependencies += self.ignore_dependencies
        
        for component_name, component in self.components.items():
            component.load_dependencies(ignore_dependencies=ignore_dependencies)
            self.components[component_name] = component
            for comp_ext_deps in component.external_dependencies:
                if comp_ext_deps.name in self.components:
                    comp_deps = self.components.get(comp_ext_deps.name)
                    comp_deps.add_dependency(component, is_internal=True)

    def _find_py_modules(self, root, modules) -> List[Path]:
        py_modules = []
        for module in modules:
            if not module.endswith(".py"):
                continue

            module_path = Path(os.path.join(root, module))
            py_modules.append(module_path)

        return py_modules

    def get_as_plane(self) -> Dict[str, ASPoint]:
        as_plane = {}
        for component_name, component in self.components.items():
            instability = component.get_instability()
            abstraction = component.get_abstraction()
            distance = component.get_distance()
            as_point = ASPoint(x=instability, y=abstraction, d=distance)

            as_plane[component_name] = as_point

        return as_plane

    def calculate_main_distance(self, decimals: int = 2):
        main_distance = 0
        distances = []

        for component_name, component in self.components.items():
            comp_distance = component.get_distance()
            distances.append(comp_distance)

        if distances:
            main_distance = sum(distances) / len(distances)

        return round(main_distance, decimals)

    def get_py_modules(self, root_path: str):
        py_modules = []

        for root, packages, modules in os.walk(root_path, topdown=True):
            if "__init__.py" not in modules:
                continue

            py_modules.extend(self._find_py_modules(root, modules))

        return py_modules

    def get_components(self) -> List[ModuleComponent]:
        return list(self.components.values())
