import pytest

from dandisets_linkml_status_tools.tools.md import escape


@pytest.mark.parametrize(
    ("input_text", "expected_output"),
    [
        (
            "Hello *Markdown* <World> | Use `code`!",
            r"Hello \*Markdown\* &lt;World&gt; &#124; Use \`code\`\!",
        ),
        ("No special chars", "No special chars"),
        ("", ""),
        (r"Nested \`Markdown\`", r"Nested \\\`Markdown\\\`"),
        (r"\`*_{}[]()#+-.!<>|", r"\\\`\*\_\{\}\[\]\(\)\#\+\-\.\!&lt;&gt;&#124;"),
        ("*Bold*", r"\*Bold\*"),
        ("_Italic_", r"\_Italic\_"),
        ("<Tag>", "&lt;Tag&gt;"),
        ("Pipe | Test", "Pipe &#124; Test"),
    ],
)
def test_escape(input_text, expected_output):
    assert escape(input_text) == expected_output
