# Copyright (c) 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if the user wants to use 'uv' as the installation tool
for arg in "$@"; do
    if [ "$arg" = "--use=uv" ]; then
        export INSTALL_TOOL="uv"
    else
        echo "Warning: Ignoring unknown argument: $arg"
    fi
done
INSTALL_TOOL="${INSTALL_TOOL:-pip}"

# Helper to run pip or uv depending on flag
run_pip() {
    if [ "$INSTALL_TOOL" = "uv" ]; then
        uv pip "$@"
    else
        python -m pip "$@"
    fi
}

install_with_pip_or_uv() {
    run_pip install "$@"
}

# Sets up internal PyPI mirror for pip or uv
setup_pypi_mirror() {
    local PUBLIC_PYPI_MIRROR="https://pypi.org"

    if [ "$INSTALL_TOOL" = "pip" ]; then
        python -m pip config --user set global.index "$PUBLIC_PYPI_MIRROR/pypi"
        python -m pip config --user set global.index-url "$PUBLIC_PYPI_MIRROR/simple"
    elif [ "$INSTALL_TOOL" = "uv" ]; then
        export UV_INDEX_URL="$PUBLIC_PYPI_MIRROR/simple"
    fi
}

# Creates a virtual environment using pip's venv or uv
create_venv() {
    local VENV_DIR=".venv-wayflowcore"

    echo -e "${BLUE}Creating virtual environment using $INSTALL_TOOL and $PYTHON_CMD...${NC}"

    if [ "$INSTALL_TOOL" = "pip" ]; then
        "$PYTHON_CMD" -m venv "$VENV_DIR"
    elif [ "$INSTALL_TOOL" = "uv" ]; then
        uv venv "$VENV_DIR" --python "$PYTHON_CMD"
    else
        echo -e "${RED}Unsupported INSTALL_TOOL: $INSTALL_TOOL${NC}" >&2
        return 1
    fi

    echo -e "${GREEN}Virtual environment created at .venv-wayflowcore${NC}"

    # Activate the environment
    source "$VENV_DIR/bin/activate"
    echo -e "${BLUE}Virtual environment activated.${NC}"
}

# Upgrades pip or updates uv
upgrade_pip_or_uv() {
    echo -e "${BLUE}Upgrading package installer (${INSTALL_TOOL})...${NC}"
    install_with_pip_or_uv --upgrade pip
}

prepare_package_installation() {
    package_name=$(basename "$1")

    if run_pip show "$package_name" &> /dev/null; then
        echo -e "${GREEN}Package $package_name is already locally installed.${NC}"
        return 1
    else
        echo -e "${BLUE}Package $package_name not found. Installing from local source \"$1\" ...${NC}"

        if [ -d "$1" ]; then
            cd "$1"
            return 0
        else
            echo -e "${RED}Error: the local directory $package_name does not exist.  cwd: $(pwd)${NC}"
            exit 1
        fi
    fi
}

install_python_package() {
    prepare_package_installation "$1"
    install_status=$?

    if [ "$install_status" -eq 0 ]; then
        bash install.sh
        cd -
    fi
}

install_dev_python_package() {
    prepare_package_installation "$1"
    install_status=$?

    if [ "$install_status" -eq 0 ]; then
        bash install-dev.sh
        cd -
    fi
}

install_requirements_dev() {
    echo -e "Installing requirements-dev.txt from $(pwd)..."
    install_with_pip_or_uv -r requirements-dev.txt
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}$(pwd)/requirements-dev.txt installed successfully${NC}"
    else
        echo -e "${RED}$(pwd)/requirements-dev.txt installation failed. Exiting.${NC}"
        exit 1
    fi
}
