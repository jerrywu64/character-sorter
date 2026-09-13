"""Parsing for the "add many characters" paste box.

A "[Fandom]" line sets the fandom for the bare names beneath it. A
"Name (Fandom)" or tab-separated line carries its own fandom for that line
only and does not displace the header.
"""
from collections import namedtuple

# Character.name and Character.fandom are both max_length=200. bulk_create
# skips model validation, so the length check has to happen here.
FIELD_LIMIT = 200

NO_NAME = "no name"
NO_FANDOM = "no fandom"
TOO_LONG = "over {} characters".format(FIELD_LIMIT)

ParsedEntry = namedtuple("ParsedEntry", ["name", "fandom"])
SkippedLine = namedtuple("SkippedLine", ["text", "reason"])

def parse_paste(text):
    """Returns (entries, skipped). A bare name with no header above it has
    no fandom to inherit, and the model requires one, so it is skipped."""
    entries = []
    skipped = []
    header = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if len(line) >= 2 and line.startswith("[") and line.endswith("]"):
            # "[]" clears the fandom rather than setting a blank one.
            header = line[1:-1].strip() or None
            continue
        name, own_fandom = split_entry(line)
        fandom = own_fandom or header
        if not name:
            skipped.append(SkippedLine(line, NO_NAME))
        elif not fandom:
            skipped.append(SkippedLine(line, NO_FANDOM))
        elif len(name) > FIELD_LIMIT or len(fandom) > FIELD_LIMIT:
            skipped.append(SkippedLine(line, TOO_LONG))
        else:
            entries.append(ParsedEntry(name, fandom))
    return entries, skipped

def split_entry(line):
    """A line's name and its own fandom, if it carries one. A tab wins over
    trailing parens: it only appears in a spreadsheet paste, where the split
    is unambiguous."""
    if "\t" in line:
        name, _, fandom = line.partition("\t")
        return name.strip(), fandom.strip()
    if line.endswith(")") and "(" in line:
        name, _, fandom = line.rpartition("(")
        return name.strip(), fandom[:-1].strip()
    return line, None

def new_entries(entries, existing):
    """The entries that would create a character, dropping both repeats
    within the paste and pairs already in the list. Matching is on name and
    fandom together, case-insensitively."""
    seen = set((name.lower(), fandom.lower()) for name, fandom in existing)
    unseen = []
    for entry in entries:
        key = (entry.name.lower(), entry.fandom.lower())
        if key not in seen:
            seen.add(key)
            unseen.append(entry)
    return unseen
