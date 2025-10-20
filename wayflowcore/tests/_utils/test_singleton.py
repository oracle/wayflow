# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore._utils.singleton import Singleton


class MySingletonCustomObject(metaclass=Singleton):
    def __init__(self):
        self.a = None


class MyCustomObject:
    def __init__(self):
        self.a = None


def test_instantiating_singleton_returns_same_instance():
    o1 = MySingletonCustomObject()
    o2 = MySingletonCustomObject()
    assert id(o1) == id(o2)


def test_instantiating_non_singleton_returns_different_instances():
    o1 = MyCustomObject()
    o2 = MyCustomObject()
    assert id(o1) != id(o2)
