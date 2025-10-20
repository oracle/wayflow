# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import importlib
import pkgutil


def import_all_submodules(package: str, recursive: bool = True) -> None:
    package_ = importlib.import_module(package)
    for _, name, is_pkg in pkgutil.walk_packages(package_.__path__):
        full_name = package_.__name__ + "." + name
        try:
            importlib.import_module(full_name)
        except ModuleNotFoundError:
            continue
        if recursive and is_pkg:
            import_all_submodules(full_name)
