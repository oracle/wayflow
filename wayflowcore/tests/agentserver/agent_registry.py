# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

from wayflowcore.tools import tool


@tool(description_mode="only_docstring")
def search_hr_database(query: str) -> str:
    """Function that searches the HR database for employee benefits.

    Parameters
    ----------
    query:
        a query string

    Returns
    -------
        a JSON response

    """
    return '{"John Smith": {"benefits": "Unlimited PTO", "salary": "$1,000"}, "Mary Jones": {"benefits": "25 days", "salary": "$10,000"}}'


tool_registry = {search_hr_database.name: search_hr_database}
