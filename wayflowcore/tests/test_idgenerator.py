# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

from wayflowcore.idgeneration import AUTO_GENERATED_SUFFIX, IdGenerator


def test_get_or_generate_id_with_provided_id():
    my_id = "custom_id"
    result = IdGenerator.get_or_generate_id(my_id)
    assert result == my_id


def test_get_or_generate_id_without_id_generates_new():
    result = IdGenerator.get_or_generate_id()
    assert isinstance(result, str)


def test_get_or_generate_name_with_custom_name():
    custom_name = "my_name"
    result = IdGenerator.get_or_generate_name(name=custom_name)
    assert result == custom_name
    assert IdGenerator.is_auto_generated(result) is False


def test_get_or_generate_name_auto_generated_default_that_is_auto_generated():
    result = IdGenerator.get_or_generate_name()
    assert IdGenerator.is_auto_generated(result) is True


def test_get_or_generate_name_did_not_auto_generate_default():
    result = IdGenerator.get_or_generate_name("hello")
    assert IdGenerator.is_auto_generated(result) is False


def test_get_or_generate_name_with_length_limit():
    result = IdGenerator.get_or_generate_name(length=8)
    assert result.endswith(AUTO_GENERATED_SUFFIX)
    assert len(result) == len(AUTO_GENERATED_SUFFIX) + 8
    assert IdGenerator.is_auto_generated(result) is True


def test_get_or_generate_name_with_prefix():
    result = IdGenerator.get_or_generate_name(prefix="myprefix_")
    assert result.startswith("myprefix_")
    assert result.endswith(AUTO_GENERATED_SUFFIX)
    assert IdGenerator.is_auto_generated(result) is True
