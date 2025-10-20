# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import os
import re

TEXT_HEADER_TEMPLATE = """
# %%[markdown]
{docs_title}
{docs_url}
# How to use:
# Create a new Python virtual environment and install the latest WayFlow version.
# ```bash
# python -m venv venv-wayflowcore
# source venv-wayflowcore/bin/activate
# pip install --upgrade pip
# pip install "wayflowcore=={version}" {install_extra}
# ```

# You can now run the script
# 1. As a Python file:
# ```bash
# python {filename}
# ```
# 2. As a Notebook (in VSCode):
# When viewing the file,
#  - press the keys Ctrl + Enter to run the selected cell
#  - or Shift + Enter to run the selected cell and move to the cell below
""".strip()


def parse_and_write_scripts(
    source_folder: str,
    destination_folder: str,
    version: str,
    install_extra: str = "",
    k: int = 3,
) -> None:
    os.makedirs(destination_folder, exist_ok=True)
    mypy_re = re.compile(r"#\s*mypy:\s*(.*)")
    fmt_re = re.compile(r"#\s*fmt:\s*(.*)")
    isort_re = re.compile(r"#\s*isort:\s*(.*)")
    title_re = re.compile(r"#\s*docs-title:\s*(.*)")
    url_re = re.compile(r"#\s*docs-url:\s*.*")
    start_re = re.compile(r"#\s*\.\.\s*start-(.*)")
    end_re = re.compile(r"#\s*\.\.\s*end-(.*)")

    for filename in os.listdir(source_folder):
        if not filename.endswith(".py"):
            continue

        src_path = os.path.join(source_folder, filename)
        dst_path = os.path.join(destination_folder, filename)
        with open(src_path, "r") as src_file:
            lines = src_file.readlines()
        if not any("# docs-title:" in x for x in lines):
            print(f"Skipping file {filename} (missing docs-title)")
            continue
        else:
            print(f"Including file {filename}")

        header = lines[:k]
        body_lines = []

        idx = k
        in_section = False
        title_name = ""
        url_name = ""
        section_name = ""
        while idx < len(lines):
            line = lines[idx]
            if m_title := title_re.match(line):  # get title and skip line
                title_name = m_title.group(1).strip()
                idx += 1
                continue
            if m_url := url_re.match(line):  # get url and skip line
                url_name = f"Read the full guide: {m_url.group(1)}"
                idx += 1
                continue
            if "docs-skiprow" in line:  # skip line
                idx += 1
                continue
            if any(
                (
                    mypy_re.match(line),
                    isort_re.match(line),
                    fmt_re.match(line),
                )
            ):
                idx += 1
                continue

            # Detect section start
            m_start = start_re.match(line)
            if m_start:
                section_name = m_start.group(1).replace("_", " ")
                body_lines.append(f"\n# %%[markdown]\n")
                body_lines.append(f"{section_name}\n\n")
                body_lines.append(f"# %%\n")
                in_section = True
                idx += 1
                continue
            # Detect section end
            m_end = end_re.match(line)
            if m_end and in_section:
                in_section = False
                idx += 1
                continue
            # Otherwise, add the line
            body_lines.append(line)
            idx += 1

        if not title_name:
            raise ValueError(
                f"Missing title for docs example '{filename}', please add the following "
                "comment: # docs-title: Title Name"
            )
        formatted_docs_title = f"# {title_name}\n# {'-'*len(title_name)}"
        rendered_text_header = TEXT_HEADER_TEMPLATE.format(
            docs_title=formatted_docs_title,
            docs_url=url_name,
            filename=filename,
            version=version,
            install_extra=install_extra,
        )

        with open(dst_path, "w") as dst_file:
            dst_file.writelines(header + [rendered_text_header] + body_lines)
