# Minimal Makefile for Sphinx documentation
SPHINXOPTS    ?= -W --keep-going
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source

BUILDDIR_HTML = build/html
BUILDDIR_MD   = build/markdown
ARTIFACTS_DIR = build/html

MD_TREE_FILE  = $(ARTIFACTS_DIR)/markdown_tree.txt
MD_ZIP_FILE   = $(ARTIFACTS_DIR)/markdown_bundle.zip

TAG           = external

help:
	@echo "Please use 'make <target>' where <target> is one of:"
	@echo "  html       to make HTML documentation (and overlay generated markdown)"
	@echo "  html-only  to make HTML documentation only"
	@echo "  md         to make Markdown documentation only"
	@echo "  clean      to clean up build directories"

.PHONY: help html html-only md overlay-md clean

# Build markdown docs only
md:
	@$(SPHINXBUILD) -t $(TAG) -b markdown "$(SOURCEDIR)" "$(BUILDDIR_MD)" $(SPHINXOPTS)
	@rm -rf "$(BUILDDIR_MD)/.doctrees" "$(BUILDDIR_MD)/_sphinx_design_static"
	@echo "Build finished. The Markdown pages are in $(BUILDDIR_MD)."

# Build html docs only
html-only:
	@$(SPHINXBUILD) -t $(TAG) -b html "$(SOURCEDIR)" "$(BUILDDIR_HTML)" $(SPHINXOPTS)
	@echo "Build finished. The HTML pages are in $(BUILDDIR_HTML)."

# Build markdown, build html, overlay .md next to html, then remove markdown build dir
html: md-artifacts html-only overlay-md
	@echo "Removing temporary Markdown build directory $(BUILDDIR_MD)..."
	@rm -rf "$(BUILDDIR_MD)"
	@echo "Artifacts written to $(ARTIFACTS_DIR)."

# Overlay markdown files into the html build tree (preserving relative paths)
overlay-md:
	@echo "Overlaying Markdown files from $(BUILDDIR_MD) onto $(BUILDDIR_HTML)..."
	@cd "$(BUILDDIR_MD)" && \
	find . -type f -name '*.md' | while read file; do \
		target="../../$(BUILDDIR_HTML)/$$file"; \
		mkdir -p "$$(dirname "$$target")"; \
		cp -f "$$file" "$$target"; \
	done

# Produce a simple folder tree + a zip of the markdown build.
md-artifacts: md
	@echo "Writing markdown tree to $(MD_TREE_FILE)..."
	@mkdir -p "$(ARTIFACTS_DIR)"
	@python create_tree.py "$(BUILDDIR_MD)" --max-depth 6 --ext .md --output "$(MD_TREE_FILE)"
	@echo "Creating markdown zip bundle at $(MD_ZIP_FILE)..."
	@cd "$(BUILDDIR_MD)" && zip -qr "../../$(MD_ZIP_FILE)" .

clean:
	- rm -rf "$(BUILDDIR_HTML)" "$(BUILDDIR_MD)" "$(ARTIFACTS_DIR)"
