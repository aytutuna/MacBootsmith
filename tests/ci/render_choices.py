import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
DOC = os.path.join(ROOT, "docs", "reference", "choices.md")
sys.path.insert(0, ROOT)

from Scripts.datasets.explanations import decisions, glossary


def cell(text):
    return text.replace("|", "\\|")


def render():
    lines = [
        "# Prompts and what to answer",
        "",
        "Generated from `Scripts/datasets/explanations.py` by `tests/ci/render_choices.py`; change the dataset and run the script again instead of editing this file. "
        "The app shows the same text before each prompt in the terminal, in the window's question dialogs and pages, and in the express summary for the answers it took for you.",
        ""
    ]
    for decision in decisions.values():
        lines += ["## {}".format(decision["title"]), ""]
        if decision["prompt"]:
            lines.append("Asked at the prompt containing `{}`.".format(decision["prompt"].strip()))
        else:
            lines.append("No prompt of its own; the window shows it on the matching page.")
        lines += ["", decision["what"], "", decision["why"], "", "| Answer | Means | Pick it when |", "|---|---|---|"]
        lines += ["| {} | {} | {} |".format(cell(value), cell(label), cell(when)) for value, label, when in decision["options"]]
        lines += ["", "Default: {}".format(decision["default"]), ""]
    lines += ["## Glossary", ""]
    for term, text in glossary.items():
        lines += ["**{}**: {}".format(term, text), ""]
    return "\n".join(lines)


if __name__ == "__main__":
    # written here rather than redirected, so the file is UTF-8 with LF whatever the shell
    with io.open(DOC, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(render())
    print("Wrote {}".format(DOC))
