# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

"""
Test that wayflowcore does not alter the root log level and
respects the logger configuration provided by the application.
"""

import logging


def test_wayflowcore_logging_does_not_alter_application_logger():
    # When application provides a loggingconfig
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    assert root_logger.getEffectiveLevel() == logging.INFO

    # Then wayflowcore should not alter root loglevel
    assert root_logger.getEffectiveLevel() == logging.INFO

    # instead it should use the application logger
    assert logging.getLogger("wayflowcore").getEffectiveLevel() == logging.INFO

    # similar to how named loggers in the primary application behave
    app_logger = logging.getLogger("my.application")
    assert app_logger.getEffectiveLevel() == logging.INFO


if __name__ == "__main__":
    test_wayflowcore_logging_does_not_alter_application_logger()
