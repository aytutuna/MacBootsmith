import re

TRUSTED_AUTHORS = ("Mirone", "InsanelyDeepak", "Toleda", "DalianSky")

SUBSYSTEM_VENDORS = {
    "1458": "Gigabyte",
    "1043": "ASUS",
    "1462": "MSI",
    "1849": "ASRock",
    "1028": "Dell",
    "17AA": "Lenovo",
    "103C": "HP",
    "1025": "Acer",
    "1558": "Clevo",
    "1D05": "Tongfang",
    "8086": "Intel",
    "106B": "Apple"
}

VENDOR_WORDS = dict({name.upper(): name for name in SUBSYSTEM_VENDORS.values()}, **{
    "AORUS": "Gigabyte",
    "ASUSTEK": "ASUS",
    "ROG": "ASUS",
    "ZENBOOK": "ASUS",
    "VIVOBOOK": "ASUS",
    "ALIENWARE": "Dell",
    "THINKPAD": "Lenovo",
    "IDEAPAD": "Lenovo",
    "NUC": "Intel",
    "SAMSUNG": "Samsung",
    "XIAOMI": "Xiaomi",
    "HASEE": "Hasee",
    "SONY": "Sony",
    "TOSHIBA": "Toshiba",
    "HUAWEI": "Huawei"
})
CODEC_PREFIXES = ("ALC", "CX", "IDT", "STAC", "92HD", "VT1", "AD1", "AD2", "CS4", "CA0")
COMPANY_WORDS = ("INC", "CO", "LTD", "CORP", "CORPORATION", "COMPUTER", "TECHNOLOGY", "INTERNATIONAL", "ELECTRONICS")
# "SP/HP" and "front HP" in layout comments mean headphones, not the vendor
PHRASES = (("MICRO-STAR", "MSI"), ("MICRO STAR", "MSI"), ("HEWLETT-PACKARD", "HP"), ("SP/HP", " "), ("FRONT HP", "FRONT"))


def tokens(text):
    text = str(text or "").upper()
    for phrase, word in PHRASES:
        text = text.replace(phrase, word)
    result = []
    for token in re.split(r"[^0-9A-Z]+", text):
        if not token:
            continue
        result.append(token)
        # comments glue the vendor to the model now and then, as in "Dell7570"
        vendor = next((word for word in VENDOR_WORDS if token.startswith(word) and len(token) > len(word)), None)
        if vendor and any(char.isdigit() for char in token[len(vendor):]):
            result += [vendor, token[len(vendor):]]
    return result


def board_tokens(board_name):
    # sub-brands such as AORUS or ROG stay; they help pick between layouts for the same chipset
    makers = set(name.upper() for name in SUBSYSTEM_VENDORS.values()) | {"ASUSTEK"}
    return [token for token in tokens(board_name) if token not in makers and token not in COMPANY_WORDS]


def model_token(board_name):
    candidates = [token for token in board_tokens(board_name) if len(token) >= 3 and any(char.isdigit() for char in token)]
    return max(candidates, key=len) if candidates else None


def vendors(text):
    return set(VENDOR_WORDS[token] for token in tokens(text) if token in VENDOR_WORDS)


def subsystem_vendor(subsystem_id):
    return SUBSYSTEM_VENDORS.get(str(subsystem_id or "")[:4].upper())


def board_vendors(board_name, subsystem_id):
    found = vendors(board_name)
    if subsystem_vendor(subsystem_id):
        found.add(subsystem_vendor(subsystem_id))
    return found


def chipset_like(token):
    return bool(re.match(r"^[A-Z]\d{2,3}[A-Z]?$", token))


def comment_board(comment, model, makers):
    match = re.search(r"\bfor\s+(.+)$", comment.strip(), re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return " ".join(sorted(vendors(comment) or makers) + [model])


def has_digit(token):
    return any(char.isdigit() for char in token)


def rank_layouts(layouts, board_name, subsystem_id, platform=None):
    laptop = str(platform or "").lower() == "laptop"
    model = model_token(board_name)
    wanted = set(board_tokens(board_name))
    makers = board_vendors(board_name, subsystem_id)
    # the subsystem ID only confirms a maker; on its own it says nothing about the board
    board_named = bool(vendors(board_name) or model)
    lone_model = model and [token for token in wanted if has_digit(token)] == [model]
    scored = []
    for layout in layouts:
        words = set(tokens(layout.comment))
        named = vendors(layout.comment)
        same_maker = not named or named <= makers
        extra = 0
        if model and model in words and same_maker:
            # a chipset such as Z490 only says the board is similar; every word of the board name,
            # a laptop model number, or a laptop model that is the only number on both sides says it is this board
            others = [word for word in words if len(word) >= 3 and has_digit(word) and model not in word and not word.startswith(CODEC_PREFIXES)]
            exact = wanted <= words or not chipset_like(model) or (laptop and lone_model and not others)
            score = 4 if exact else 3
            extra = len(wanted & words)
        elif named and named <= makers and board_named:
            score = 2
        elif any(author.lower() in layout.comment.lower() for author in TRUSTED_AUTHORS):
            score = 1
        else:
            score = 0
        scored.append((layout, score, extra))

    # laptop wiring differs per model, so another laptop of the same maker ranks below a trusted general layout
    order = {4: 0, 3: 1, 2: 3, 1: 2, 0: 4} if laptop else {4: 0, 3: 1, 2: 2, 1: 3, 0: 4}
    # stable sort: by level, then by how many board words the comment shares, then dataset order
    scored.sort(key=lambda item: (order[item[1]], -item[2]))
    best = scored[0][1] if scored else 0
    if best == 3:
        # a similar board's layout stays first, but the trusted general one is the next thing to try
        trusted = next((item for item in scored if item[1] == 1), None)
        if trusted:
            scored.remove(trusted)
            scored.insert(1, trusted)
    model_match = best >= 3

    ranked = []
    for layout, score, _ in scored:
        if score == 4:
            reason = "made for " + comment_board(layout.comment, model, makers)
        elif score == 3:
            maker = " / ".join(sorted(vendors(layout.comment) or makers))
            reason = "made for {}, a similar {} board; try the others if a jack is dead".format(
                comment_board(layout.comment, model, makers), " ".join(part for part in (maker, model) if part))
        elif score == 2:
            reason = "made for another {} {}".format(" / ".join(sorted(vendors(layout.comment))), "laptop" if laptop else "board")
            if not model_match:
                reason += "; no layout names your model"
        elif score == 1:
            reason = "a trusted general layout"
            if not model_match:
                reason += "; no layout names your board"
        elif not ranked:
            reason = "the first layout listed for this codec; none names your board or comes from a trusted author"
        else:
            reason = ""
        ranked.append((layout, score, reason))
    return ranked
