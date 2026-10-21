import re
import threading
import traceback

from Scripts import utils

YES_NO = re.compile(r"\(\s*(y(?:es)?)\s*/\s*(n(?:o)?)\s*\)", re.IGNORECASE)
MENU_LINE = re.compile(r"^\s*(\d{1,3})\.\s+(\S.*?)\s*$")
LETTER_LINE = re.compile(r"^\s*([A-Za-z])\.\s+(\S.*?)\s*$")
DEFAULT_VALUE = re.compile(r"\(default:\s*([^)]*)\)", re.IGNORECASE)
SGR = re.compile(r"\x1b\[([0-9;]*)m")
OTHER_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-ln-z]")
PARTIAL_ESCAPE = re.compile(r"\x1b(\[[0-9;?]*)?$")
PERCENT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")

SGR_TAGS = {
    "31": "red", "91": "red",
    "32": "green", "92": "green",
    "33": "yellow", "93": "yellow",
    "36": "cyan", "96": "cyan",
    "90": "grey"
}

MAX_BUTTONS = 24
MAX_LABEL = 60
PRESET_REPEAT_LIMIT = 3


def strip_ansi(text):
    return OTHER_ESCAPE.sub("", SGR.sub("", text or ""))


def is_press_enter(prompt):
    return str(prompt).strip().lower().startswith("press enter")


def default_answer(prompt):
    match = DEFAULT_VALUE.search(str(prompt))
    return match.group(1).strip() if match else None


def parse_choices(prompt, captured=""):
    prompt = strip_ansi(str(prompt))
    match = YES_NO.search(prompt)
    if match:
        yes, no = match.group(1), match.group(2)
        return [("Yes", yes.lower()), ("No", no.lower())]

    numbered = []
    letters = []
    seen = set()
    for line in strip_ansi(captured or "").splitlines():
        menu = MENU_LINE.match(line)
        if menu:
            value = menu.group(1)
            if value in seen:
                numbered = [item for item in numbered if item[1] != value]
            seen.add(value)
            numbered.append(("{}. {}".format(value, menu.group(2))[:MAX_LABEL], value))
            continue
        letter = LETTER_LINE.match(line)
        if letter and not line.startswith(" " * 4):
            value = letter.group(1).upper()
            if value not in [item[1] for item in letters]:
                letters.append(("{}. {}".format(value, letter.group(2))[:MAX_LABEL], value))

    choices = numbered[:MAX_BUTTONS]
    if choices or letters:
        choices.extend(letters[:6])
    return choices


class AnsiStream:
    def __init__(self):
        self.tag = None
        self.pending = ""

    def _apply(self, codes):
        parts = [part for part in codes.split(";") if part]
        if not parts:
            self.tag = None
            return
        for part in parts:
            if part == "0":
                self.tag = None
            elif part in SGR_TAGS:
                self.tag = SGR_TAGS[part]

    def feed(self, text):
        text = self.pending + (text or "")
        self.pending = ""
        partial = PARTIAL_ESCAPE.search(text)
        if partial:
            self.pending = text[partial.start():]
            text = text[:partial.start()]
        text = OTHER_ESCAPE.sub("", text)
        segments = []
        position = 0
        for match in SGR.finditer(text):
            if match.start() > position:
                segments.append((text[position:match.start()], self.tag))
            self._apply(match.group(1))
            position = match.end()
        if position < len(text):
            segments.append((text[position:], self.tag))
        return segments


def last_percent(line):
    found = PERCENT.findall(line or "")
    if not found:
        return None
    try:
        value = float(found[-1])
    except ValueError:
        return None
    return value if 0 <= value <= 100 else None


class PromptRequest:
    def __init__(self, prompt, captured, choices, default=None):
        self.prompt = prompt
        self.captured = captured
        self.choices = choices
        self.default = default
        self.answer = None
        self.cancelled = False
        self.event = threading.Event()

    def reply(self, answer):
        self.answer = "" if answer is None else str(answer)
        self.event.set()

    def cancel(self):
        self.cancelled = True
        self.event.set()


class PromptBroker:
    def __init__(self, post):
        self.post = post
        self.presets = []
        self.cancel_event = threading.Event()
        self.worker_ident = None
        self.last_prompt = None
        self.last_captured = ""
        self.pending = None
        self._preset_prompt = None
        self._preset_count = 0

    def set_presets(self, mapping):
        self.presets = [(str(key).lower(), "" if value is None else str(value)) for key, value in (mapping or {}).items() if key]
        self._preset_prompt = None
        self._preset_count = 0

    def clear_presets(self):
        self.set_presets({})

    def preset_for(self, prompt):
        lowered = str(prompt).lower()
        for key, value in self.presets:
            if key in lowered:
                if prompt == self._preset_prompt:
                    self._preset_count += 1
                else:
                    self._preset_prompt = prompt
                    self._preset_count = 1
                if self._preset_count > PRESET_REPEAT_LIMIT:
                    return None
                return value
        return None

    def in_worker(self):
        return self.worker_ident is not None and threading.get_ident() == self.worker_ident

    def check_cancel(self):
        if self.cancel_event.is_set() and self.in_worker():
            raise utils.GuiExit("Cancelled by the user", reason="cancel")

    def cancel(self):
        self.cancel_event.set()
        request = self.pending
        if request is not None:
            request.cancel()

    def reset(self):
        self.cancel_event.clear()
        self.last_prompt = None
        self.last_captured = ""

    def sink(self, text):
        self.post(("log", text))
        self.check_cancel()

    def progress(self, title, steps, index, done):
        self.post(("progress", title, list(steps), index, done))

    def __call__(self, prompt, captured):
        self.check_cancel()
        prompt = str(prompt)
        if is_press_enter(prompt):
            return ""

        preset = self.preset_for(prompt)
        if preset is not None:
            return preset

        context = captured or ""
        if prompt == self.last_prompt and self.last_captured and self.last_captured not in context:
            context = self.last_captured.rstrip("\n") + "\n" + context
        self.last_prompt = prompt
        self.last_captured = context

        request = PromptRequest(prompt, context, parse_choices(prompt, context), default_answer(prompt))
        self.pending = request
        try:
            self.post(("prompt", request))
            while not request.event.wait(0.1):
                if self.cancel_event.is_set():
                    request.cancelled = True
                    break
        finally:
            self.pending = None
        if request.cancelled:
            raise utils.GuiExit("Cancelled by the user", reason="cancel")
        return request.answer


class StageRunner:
    def __init__(self, broker, post):
        self.broker = broker
        self.post = post
        self.thread = None
        self.token = 0
        self.label = None
        self.active = None

    def busy(self):
        return self.active is not None

    def finish(self, token):
        if self.active == token:
            self.active = None

    def start(self, label, func):
        if self.busy():
            return None
        self.token += 1
        token = self.token
        self.label = label
        self.active = token
        self.broker.reset()
        self.thread = threading.Thread(target=self._run, args=(token, label, func), name="stage-{}".format(token))
        self.thread.daemon = True
        self.thread.start()
        return token

    def _run(self, token, label, func):
        self.broker.worker_ident = threading.get_ident()
        try:
            result = func()
        except utils.GuiExit as e:
            message = ("stopped", token, label, getattr(e, "reason", "exit"), str(e))
        except BaseException as e:
            message = ("error", token, label, e, traceback.format_exc())
        else:
            message = ("done", token, label, result)
        finally:
            self.broker.worker_ident = None
        self.post(message)
