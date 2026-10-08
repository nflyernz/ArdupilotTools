"""Small terminal-text helpers shared by analysis presentations."""

import shutil
import textwrap


def wrap_report(report, width=None):
    """Wrap long report lines with continuations indented below their item."""
    if width is None:
        width = min(92, max(20, shutil.get_terminal_size(fallback=(92, 24)).columns - 2))
    else:
        width = max(20, width)
    lines = []
    for line in report.splitlines():
        if not line.strip() or len(line) <= width:
            lines.append(line)
            continue
        indent = line[:len(line) - len(line.lstrip())]
        wrapper = textwrap.TextWrapper(
            width=width, initial_indent=indent, subsequent_indent=indent + "  ",
            break_long_words=False, break_on_hyphens=False,
        )
        lines.extend(wrapper.wrap(line.strip()))
    return "\n".join(lines)
