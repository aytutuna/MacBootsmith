import re
import textwrap

from Scripts.datasets import os_data
from Scripts.datasets.explanations import decisions, glossary, stages

WIDTH = 68
DEFAULT_VALUE = re.compile(r"\(default:\s*([^)]*)\)", re.IGNORECASE)
# the capitalised word in (Yes/no) or (yes/No) is what Enter means
YES_NO_DEFAULT = re.compile(r"\((Yes)/no\)|\(yes/(No)\)")

# progress step titles (express run, EFI build, hardware scan) and the stage they belong to
STEP_STAGES = {
    "Hardware scan": ("scan", "verdict"),
    "Gathering PnP devices": ("scan",),
    "Configuration": ("macos", "smbios"),
    "EFI build": ("kexts", "validate"),
    "Applying ACPI patches": ("acpi",),
    "Generating config.plist": ("config",),
    "macOS recovery": ("recovery",),
    "Post-install kit": ("kit",),
}


def decision_for_prompt(prompt):
    lowered = str(prompt).lower()
    found = None
    for key, decision in decisions.items():
        text = decision["prompt"]
        if text and text.lower() in lowered and (found is None or len(text) > len(decisions[found]["prompt"])):
            found = key
    return found


def wrap(text, width, indent=""):
    return textwrap.fill(text, width, subsequent_indent=indent)


def render_decision(key, width=WIDTH):
    decision = decisions[key]
    lines = ["\033[1;93m{}\033[0m".format(decision["title"]),
             wrap("What: " + decision["what"], width, "  "),
             wrap("Why: " + decision["why"], width, "  ")]
    for value, label, when in decision["options"]:
        text = wrap("  {}: {}. {}".format(value, label, when), width, "    ")
        lines.append("  \033[1m{}\033[0m{}".format(value, text[2 + len(value):]))
    lines.append(wrap("Default: " + decision["default"], width, "  "))
    return "\n".join(lines)


def render_glossary(width=WIDTH):
    return [wrap("{}: {}".format(term, text), width, "    ") for term, text in glossary.items()]


def choice(key, answer, prompt=""):
    options = decisions[key]["options"]
    match = DEFAULT_VALUE.search(str(prompt))
    default = match.group(1).strip() if match else None
    yes_no = YES_NO_DEFAULT.search(str(prompt))
    if yes_no:
        default = (yes_no.group(1) or yes_no.group(2)).lower()
    value = str(answer).strip() or default or ""
    if key == "macos_version" and value[:2].isdigit():
        value = os_data.get_macos_name_by_darwin(value) or value
    wanted = {"y": "yes", "n": "no"}.get(value.lower(), value.lower())
    for option in options:
        if wanted in (option[0].lower(), option[1].lower()):
            return option
    if value and value == default:
        for option in options:
            if option[0] == "Enter":
                return (option[0], "{} ({})".format(option[1], value), option[2])
    return (value, value or "[Enter]", "")


def decision_line(key, answer, prompt=""):
    value, label, when = choice(key, answer, prompt)
    # named answers such as a kext name go in front, so the line says what was picked
    if when and not value.isdigit() and value.lower() not in ("enter", "yes", "no") and value.lower() not in label.lower():
        label = "{}, {}".format(value, label)
    return "{}: {}.{}".format(decisions[key]["title"], label, " " + when if when else "")
