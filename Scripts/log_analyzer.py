from Scripts.datasets import boot_log_patterns
from Scripts import utils
import codecs
import os
import re

LOG_NAME = re.compile(r"^opencore-(\d{4}-\d{2}-\d{2}-\d{6})\.txt$", re.IGNORECASE)
LOG_PREFIX = "opencore-"
FALLBACK_NAMES = ("serial.log",)
TIMESTAMP = re.compile(r"^\d{2,}:\d{3} \d{2,}:\d{3} ")
ESCAPE = re.compile(r"\x1b\[[0-9;=?]*[A-Za-z]|\x1b[()][A-Za-z0-9]|[\x00-\x08\x0b-\x1f\x7f]")
TAIL_SIZE = 15
MAX_READ = 16 * 1024 * 1024
BOOT_START = re.compile(r"BS: Starting OpenCore application")
FILE_LOG = re.compile(r"^opencore-.*\.txt$", re.IGNORECASE)

class LogAnalyzer:
    def __init__(self, patterns=None):
        self.utils = utils.Utils()
        self.patterns = [dict(pattern, compiled=re.compile(pattern["regex"])) for pattern in (patterns or boot_log_patterns.patterns)]
        self.stage_keys = [key for key, _ in boot_log_patterns.stages]
        self.stage_labels = dict(boot_log_patterns.stages)
        self.stage_markers = [(key, [re.compile(regex) for regex in boot_log_patterns.stage_markers.get(key, [])]) for key in self.stage_keys]
        self.mask_rules = [(re.compile(regex), replacement) for regex, replacement in boot_log_patterns.mask_rules]
        self.banner = re.compile(boot_log_patterns.banner)
        self.driver_loading = re.compile(boot_log_patterns.driver_loading)
        self.driver_loaded = re.compile(boot_log_patterns.driver_loaded)
        self.path = None
        self.raw_lines = []
        self.parsed = None

    def mask(self, text):
        for rule, replacement in self.mask_rules:
            text = rule.sub(replacement, text)
        return text

    def _drive_root(self, location):
        if os.name == "nt" and re.match(r"^[A-Za-z]:?\\?$", location):
            return location[0].upper() + ":\\"
        return location

    def _newest_log(self, folder):
        try:
            names = os.listdir(folder)
        except OSError:
            return None

        candidates = []
        for name in names:
            path = os.path.join(folder, name)
            if not name.lower().startswith(LOG_PREFIX) or not name.lower().endswith(".txt") or not os.path.isfile(path):
                continue
            match = LOG_NAME.match(name)
            try:
                modified = os.path.getmtime(path)
            except OSError:
                modified = 0
            candidates.append(((match.group(1) if match else "", modified), path))

        if candidates:
            return max(candidates)[1]

        for name in FALLBACK_NAMES:
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                return path
        return None

    def find_log(self, location):
        if location is None:
            return None
        location = self._drive_root(os.path.expanduser(str(location).strip().strip('"')))
        if not location:
            return None
        if os.path.isfile(location):
            return location
        if os.path.isdir(location):
            return self._newest_log(location)
        return None

    def decode(self, data):
        if data.startswith(codecs.BOM_UTF8):
            return data[len(codecs.BOM_UTF8):].decode("utf-8", errors="replace")
        if data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
            return data.decode("utf-16", errors="replace")

        sample = data[:4096]
        if len(sample) >= 4:
            odd_nulls = sample[1::2].count(0)
            even_nulls = sample[0::2].count(0)
            if odd_nulls > len(sample[1::2]) * 0.6 and even_nulls < len(sample[0::2]) * 0.1:
                return data.decode("utf-16-le", errors="replace")
            if even_nulls > len(sample[0::2]) * 0.6 and odd_nulls < len(sample[1::2]) * 0.1:
                return data.decode("utf-16-be", errors="replace")
        return data.decode("utf-8", errors="replace")

    def split_lines(self, text):
        return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def load_text(self, text, source="<text>"):
        self.path = source
        self.raw_lines = self.split_lines(text)
        self.parsed = None
        return source

    def load(self, path_or_drive):
        path = self.find_log(path_or_drive)
        if not path:
            self.path = None
            self.raw_lines = []
            self.parsed = None
            return None
        with open(path, "rb") as log_file:
            log_file.seek(0, os.SEEK_END)
            size = log_file.tell()
            log_file.seek(max(0, size - MAX_READ))
            data = log_file.read()
            if size > MAX_READ and not data.startswith((codecs.BOM_UTF8, codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
                data = data[data.find(b"\n") + 1:] if b"\n" in data else data
        return self.load_text(self.decode(data), path)

    def clean_line(self, line):
        line = ESCAPE.sub("", line)
        line = TIMESTAMP.sub("", line.strip())
        return line.strip()

    def parse(self):
        lines = []
        for number, raw in enumerate(self.raw_lines, start=1):
            text = self.clean_line(raw)
            if text:
                lines.append((number, text))

        starts = [index for index, (_, text) in enumerate(lines) if BOOT_START.search(text)]
        if starts:
            lines = lines[starts[-1]:]

        version = build = mode = None
        for _, text in lines:
            match = self.banner.search(text)
            if match:
                build = boot_log_patterns.build_types.get(match.group(2), match.group(2))
                version = "{}.{}.{}".format(match.group(3), match.group(4), match.group(5))
                mode = match.group(7)
                break

        stage_index = 0
        stage_line = None
        for number, text in lines:
            for index in range(len(self.stage_markers) - 1, stage_index, -1):
                if any(marker.search(text) for marker in self.stage_markers[index][1]):
                    stage_index = index
                    stage_line = number
                    break

        if build is None and any(re.match(r"^[A-Z]{2,6}: ", text) for _, text in lines) and stage_index > 0:
            build = "DEBUG (inferred: a RELEASE build writes almost nothing)"

        self.parsed = {
            "lines": lines,
            "version": version,
            "build": build,
            "mode": mode,
            "stage": self.stage_keys[stage_index],
            "stage_index": stage_index,
            "stage_line": stage_line
        }
        return self.parsed

    def _fill(self, text, match):
        try:
            return text.format(*[self.mask(group or "") for group in match.groups()])
        except (IndexError, KeyError):
            return text

    def match_patterns(self, lines):
        matches = []
        by_id = {}
        for number, text in lines:
            for pattern in self.patterns:
                match = pattern["compiled"].search(text)
                if not match:
                    continue
                if pattern["id"] in by_id:
                    by_id[pattern["id"]]["count"] += 1
                    continue
                entry = {
                    "id": pattern["id"],
                    "severity": pattern["severity"],
                    "category": pattern["category"],
                    "stage": pattern["stage"],
                    "cause": self._fill(pattern["cause"], match),
                    "fix": self._fill(pattern["fix"], match),
                    "doc": pattern["doc"],
                    "line_number": number,
                    "line": self.mask(text),
                    "count": 1
                }
                by_id[pattern["id"]] = entry
                matches.append(entry)
        return matches

    def is_noise(self, text):
        if not re.search(r"[A-Za-z]{2}", text):
            return True
        return any(pattern["category"] == "noise" and pattern["compiled"].search(text) for pattern in self.patterns)

    def crashed_driver(self, lines, crash_line):
        pending = None
        for number, text in lines:
            if number >= crash_line:
                break
            loading = self.driver_loading.search(text)
            if loading:
                pending = loading.group(1)
                continue
            loaded = self.driver_loaded.search(text)
            if loaded and loaded.group(1) == pending:
                pending = None
        return pending

    def verdict(self, parsed, matches):
        stage = parsed["stage"]
        label = self.stage_labels[stage]
        stage_line = parsed.get("stage_line")
        fatal = next((match for match in matches if match["severity"] == "fatal" and (stage_line is None or match["line_number"] >= stage_line)), None)

        if fatal and fatal["category"] == "crash":
            driver = self.crashed_driver(parsed["lines"], fatal["line_number"])
            if driver:
                return "Crashed while loading driver {}".format(driver)
            return "Crashed after {}: {}".format(label, fatal["cause"])
        if fatal and fatal["category"] == "config":
            return "Config error: {}".format(fatal["cause"])
        if fatal:
            return "Stopped after {}: {}".format(label, fatal["cause"])

        if stage == "kernel_started":
            return "Reached the macOS kernel: read the last verbose lines on screen for later stalls"
        if stage == "booter_handoff" and self.path and FILE_LOG.match(os.path.basename(str(self.path))):
            return "The file log always ends at the booter handoff: tell what the screen showed. Only if it froze right after EXITBS:START, see Booter quirks"
        if stage == "booter_handoff":
            return "Stalled after booter handoff: see Booter quirks"
        if stage == "entry_chosen":
            return "Stalled after the boot entry was chosen: boot.efi did not report back (see Booter quirks and SecureBootModel)"
        if stage == "picker_shown":
            return "Reached the boot picker"

        config_warning = next((match for match in matches if match["category"] == "config" and match["severity"] == "warning"), None)
        if config_warning:
            return "Config error: {}".format(config_warning["cause"])
        if stage == "none":
            return "No OpenCore lines found: use the DEBUG build (Build a DEBUG EFI) and boot once to create a log"
        return "Stalled after {}: read the last lines below".format(label)

    def analyze(self):
        parsed = self.parsed or self.parse()
        matches = self.match_patterns(parsed["lines"])
        findings = [match for match in matches if match["category"] != "noise"]
        benign = sum(match["count"] for match in matches if match["category"] == "noise")
        tail = [self.mask(text) for _, text in parsed["lines"] if not self.is_noise(text)][-TAIL_SIZE:]
        return {
            "source": self.path,
            "line_count": len(self.raw_lines),
            "version": parsed["version"],
            "build": parsed["build"],
            "mode": parsed["mode"],
            "stage": parsed["stage"],
            "stage_label": self.stage_labels[parsed["stage"]],
            "picker_reached": parsed["stage_index"] >= self.stage_keys.index("picker_shown"),
            "verdict": self.verdict(parsed, matches),
            "findings": findings,
            "benign_lines": benign,
            "tail": tail
        }

    def format_report(self, report):
        out = []
        out.append("Boot log:      {}".format(report["source"]))
        if report["version"]:
            out.append("OpenCore:      {} {}{}".format(report["version"], report["build"], " ({} vault mode)".format(report["mode"]) if report["mode"] else ""))
        else:
            out.append("OpenCore:      version not in log{}".format(", build " + report["build"] if report["build"] else ""))
        out.append("Lines:         {}".format(report["line_count"]))
        out.append("Stage reached: {}".format(report["stage_label"]))
        out.append("Verdict:       {}".format(report["verdict"]))
        out.append("")
        out.append("Findings:")
        if not report["findings"]:
            out.append("  none")
        for finding in report["findings"]:
            out.append("  [{}] line {}{}: {}".format(finding["severity"].upper(), finding["line_number"], " (x{})".format(finding["count"]) if finding["count"] > 1 else "", finding["line"]))
            out.append("      Cause: {}".format(finding["cause"]))
            out.append("      Fix:   {}".format(finding["fix"]))
            out.append("      See:   {}".format(finding["doc"]))
        if report["benign_lines"]:
            out.append("  ({} known harmless lines skipped)".format(report["benign_lines"]))
        out.append("")
        out.append("Last {} lines:".format(len(report["tail"])))
        for line in report["tail"]:
            out.append("  {}".format(line))
        return "\n".join(out)

    def render(self, report=None):
        report = report or self.analyze()
        text = self.format_report(report)
        self.utils.head("Boot Log Analysis")
        print("")
        if utils.Utils.is_headless():
            print(text)
            return text

        color = "\033[92m" if report["picker_reached"] and not any(f["severity"] == "fatal" for f in report["findings"]) else "\033[1;93m"
        for line in text.split("\n"):
            if line.startswith("Verdict:"):
                print("{}{}\033[0m".format(color, line))
            elif line.startswith("  [FATAL]"):
                print("\033[91m{}\033[0m".format(line))
            else:
                print(line)
        return text
