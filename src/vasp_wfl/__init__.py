import importlib
import pkgutil

__all__ = []

for _, module_name, _ in pkgutil.walk_packages(__path__):
    module = importlib.import_module(f"{__name__}.{module_name}")
    if hasattr(module, "__all__"):
        globals().update({k: getattr(module, k) for k in module.__all__})
        __all__.extend(module.__all__)
    else:
        globals()[module_name] = module
        __all__.append(module_name)
