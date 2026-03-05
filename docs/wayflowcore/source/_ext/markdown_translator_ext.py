# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.
# mypy: ignore-errors

from __future__ import annotations

from docutils import nodes
from sphinx_markdown_builder.contexts import SubContext, SubContextParams, TableContext
from sphinx_markdown_builder.translator import MarkdownTranslator, pushing_context


class MarkdownTranslatorPlus(MarkdownTranslator):
    def astext(self):
        text = super().astext()
        return (
            text.replace("<br/>\n", "\n")
            .replace("<br/>", "\n")
            .replace("<br/>", "\n")
            .replace("<!-- :orphan: -->", "")
            .replace("<!-- :no-search: -->", "")
        )

    # -------------------------
    # Admonitions
    # -------------------------
    @pushing_context
    def visit_admonition(self, node: nodes.admonition) -> None:
        title = _get_admonition_title(node, "ADMONITION")
        self._push_box(title)

    # Specific admonition directives in RST map to specific node types
    @pushing_context
    def visit_tip(self, node: nodes.tip) -> None:
        self._push_box(_get_admonition_title(node, "TIP"))

    @pushing_context
    def visit_danger(self, node: nodes.danger) -> None:
        self._push_box(_get_admonition_title(node, "DANGER"))

    @pushing_context
    def visit_caution(self, node: nodes.caution) -> None:
        self._push_box(_get_admonition_title(node, "CAUTION"))

    def visit_title(self, node: nodes.title) -> None:
        if isinstance(node.parent, nodes.admonition):
            # skip the actual title child inside admonition to avoid duplicating it
            raise nodes.SkipNode
        return super().visit_title(node)

    # -------------------------
    # option_list (RST options)
    # -------------------------
    @pushing_context
    def visit_option_list(self, node: nodes.option_list) -> None:
        # simplest Markdown representation: a bullet list
        self._start_list("*")

    def depart_option_list(self, node: nodes.option_list) -> None:
        self._end_list(node)

    @pushing_context
    def visit_option_list_item(self, node: nodes.option_list_item) -> None:
        self._start_list_item(node)

    def depart_option_list_item(self, node: nodes.option_list_item) -> None:
        self._end_list_item(node)

    def visit_option_group(self, node: nodes.option_group) -> None:
        # Render like `-h, --help` (inline)
        # Let children (option / option_string) render
        pass

    def visit_option(self, node: nodes.option) -> None:
        pass

    def visit_option_string(self, node: nodes.option_string) -> None:
        self._push_status(escape_text=False)
        self.add("`")

    def depart_option_string(self, node: nodes.option_string) -> None:
        self.add("`")
        self._pop_status()

    def visit_description(self, node: nodes.description) -> None:
        # " - description" on same list item
        self.add(" — ")

    # -------------------------
    # abbreviation
    # -------------------------
    def visit_abbreviation(self, node: nodes.abbreviation) -> None:
        # Markdown has no native abbreviation syntax; simplest is to emit text.
        title = node.get("explanation")
        if title:
            self.add(f'<abbr title="{title}">')
        # allow children/text to render

    def depart_abbreviation(self, node: nodes.abbreviation) -> None:
        if node.get("explanation"):
            self.add("</abbr>")

    # -------------------------
    # sphinx_toolbox.collapse: CollapseNode
    # -------------------------
    @pushing_context
    def visit_CollapseNode(self, node) -> None:
        summary = getattr(node, "summary", None) or node.get("summary", None) or "Details"

        self.add("<details>", prefix_eol=2, suffix_eol=1)
        self.add(f"<summary>{summary}</summary>", prefix_eol=1, suffix_eol=2)

        self._push_context(SubContext(SubContextParams(prefix_eol=1, suffix_eol=2)))

    def depart_CollapseNode(self, node) -> None:
        self._pop_context()
        self.add("</details>", prefix_eol=1, suffix_eol=2)

    # -------------------------
    # PassthroughTextElement
    # -------------------------
    def visit_PassthroughTextElement(self, node) -> None:
        # Letting traversal continue to process children (image + text)
        pass

    def depart_PassthroughTextElement(self, node) -> None:
        pass

    # -------------------------
    # Table fix
    # -------------------------
    def _find_table_ctx(self):
        # Walk up the context stack from innermost to outermost
        for c in reversed(self._ctx_queue):
            if isinstance(c, TableContext):
                return c
        return None

    def visit_table(self, node):
        # Always push a TableContext for any table node
        self._push_context(TableContext(params=SubContextParams(2, 1)))

    def visit_thead(self, node: nodes.thead):
        table_ctx = self._find_table_ctx()
        if table_ctx is None:
            raise nodes.SkipNode
        table_ctx.enter_head()

    def depart_thead(self, node):
        table_ctx = self._find_table_ctx()
        if table_ctx is not None:
            table_ctx.exit_head()

    def visit_tbody(self, node):
        table_ctx = self._find_table_ctx()
        if table_ctx is None:
            raise nodes.SkipNode
        table_ctx.enter_body()

    def depart_tbody(self, node):
        table_ctx = self._find_table_ctx()
        if table_ctx is not None:
            table_ctx.exit_body()

    def visit_row(self, node):
        table_ctx = self._find_table_ctx()
        if table_ctx is None:
            raise nodes.SkipNode
        table_ctx.enter_row()

    def depart_row(self, node):
        table_ctx = self._find_table_ctx()
        if table_ctx is not None:
            table_ctx.exit_row()

    def visit_entry(self, node):
        table_ctx = self._find_table_ctx()
        if table_ctx is None:
            raise nodes.SkipNode
        table_ctx.enter_entry()

    def depart_entry(self, node):
        table_ctx = self._find_table_ctx()
        if table_ctx is not None:
            table_ctx.exit_entry()


def _get_admonition_title(node: nodes.Node, default: str) -> str:
    # If it's a generic ".. admonition:: My Title", docutils adds a title node as first child.
    for child in node.children:
        if isinstance(child, nodes.title):
            return child.astext()
    return default


def setup(app):
    # Register for the "markdown" builder to override the translator used by sphinx_markdown_builder.
    app.set_translator("markdown", MarkdownTranslatorPlus, override=True)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
