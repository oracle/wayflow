# Minimal Makefile for Sphinx documentation
#

SPHINXOPTS    ?= -W --keep-going
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = build/html
TAG           = external

# Put it first so that "make" without argument is like "make help".
help:
	@echo "Please use 'make <target>' where <target> is one of:"
	@echo "  html    to make HTML documentation"
	@echo "  clean   to clean up build directory"

.PHONY: help html clean

# Build HTML
html:
	@$(SPHINXBUILD) -t $(TAG) -b html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR)."

# Clean up build directory
clean:
	- rm -rf "$(BUILDDIR)"
