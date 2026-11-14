"""Club catalog and the player's bag.

The catalog is bag order, driver toward putter. Dialog columns follow it.
The bag is the checked subset, saved as one name per line in current_bag.txt.
Stepping uses that subset only, so adding a club here does not change the
up/down math.
"""

from pathlib import Path

from app.paths import writable_dir

CLUB_UP = "i"
CLUB_DOWN = "k"
PUTT = "u"


class Club:
    def __init__(self, name: str, phrases: tuple[str, ...], group: str) -> None:
        self.name = name
        self.phrases = phrases
        self.group = group


# Bag order, driver toward putter. Spoken phrases are words in the small Vosk lexicon.
# Club phrases start with "club" so a club name is not heard as a digit or another word.
CATALOG = (
    Club("Driver", ("club driver",), "woods"),
    Club("3 wood", ("club three wood",), "woods"),
    Club("5 wood", ("club five wood",), "woods"),
    Club("3 iron", ("club three iron",), "irons"),
    Club("4 iron", ("club four iron",), "irons"),
    Club("5 iron", ("club five iron",), "irons"),
    Club("6 iron", ("club six iron",), "irons"),
    Club("7 iron", ("club seven iron",), "irons"),
    Club("8 iron", ("club eight iron",), "irons"),
    Club("9 iron", ("club nine iron",), "irons"),
    Club("Utility iron", ("club utility iron",), "irons"),
    Club("Pitching wedge", ("club pitching wedge",), "wedges"),
    Club("Gap wedge", ("club gap wedge",), "wedges"),
    Club("Sand wedge", ("club sand wedge",), "wedges"),
    Club("56 wedge", ("club fifty six wedge", "club fifty six"), "wedges"),
    Club("Lob wedge", ("club lob wedge",), "wedges"),
    Club("Putter", ("club putter",), "other"),
)

# Used when current_bag.txt does not exist yet. 3 iron, utility, and lob are off.
DEFAULT_BAG = (
    "Driver",
    "3 wood",
    "5 wood",
    "4 iron",
    "5 iron",
    "6 iron",
    "7 iron",
    "8 iron",
    "9 iron",
    "Pitching wedge",
    "Gap wedge",
    "Sand wedge",
    "56 wedge",
    "Putter",
)

_BY_PHRASE = {phrase: club.name for club in CATALOG for phrase in club.phrases}
_MOVE_PHRASES: tuple[str, ...] = ()  # club up and club down are keystrokes now, not bag moves


def spoken_phrases() -> tuple[str, ...]:
    """Catalog phrases plus the active player's nicknames."""
    from app.players import nickname_phrases

    return tuple(_BY_PHRASE) + nickname_phrases() + _MOVE_PHRASES


class Move:
    def __init__(self, keys: list[str], detail: str) -> None:
        self.keys = keys
        self.detail = detail


def bag_file() -> Path:
    return writable_dir() / "current_bag.txt"


def load_bag_names() -> list[str]:
    path = bag_file()
    if not path.is_file():
        return list(DEFAULT_BAG)
    chosen: set[str] = set()
    known = {club.name for club in CATALOG}
    for line in path.read_text(encoding="utf-8").splitlines():
        name = line.split("#", 1)[0].strip()
        if name in known:
            chosen.add(name)
    if not chosen:
        return list(DEFAULT_BAG)
    return [club.name for club in CATALOG if club.name in chosen]


def save_bag_names(names: list[str]) -> None:
    chosen = set(names)
    ordered = [club.name for club in CATALOG if club.name in chosen]
    bag_file().write_text("\n".join(ordered) + "\n", encoding="utf-8")


class Bag:
    def __init__(self) -> None:
        from app.players import active_player_id, bag_names

        self.player_id = active_player_id()
        self._extra: dict[str, tuple[str, ...]] = {}
        if self.player_id is None:
            self._names = load_bag_names()
        else:
            self._names, self._extra = bag_names(self.player_id)
            if not self._names:
                self._names = load_bag_names()
        self.index = 0
        # False until a club has been called: GSPro may be on any club until then, so the first one goes via
        # the putter (see apply), which is the one club GSPro's keys set exactly.
        self._synced = False
        self._phrase_index = self._indexes()

    def reload(self) -> None:
        """Load the active player's clubs again."""
        self.__init__()

    @property
    def club(self) -> str:
        return self._names[self.index]

    def enabled_names(self) -> list[str]:
        return list(self._names)

    def summary(self) -> str:
        parts: list[str] = []
        for name in self._names:
            extra = self._extra.get(name, ())
            parts.append(f"{name} ({extra[0]})" if extra else name)
        return ", ".join(parts)

    def set_enabled(self, names: list[str]) -> bool:
        if self.player_id is None:
            ordered = [club.name for club in CATALOG if club.name in set(names)]
            if not ordered:
                return False
            current = self.club
            save_bag_names(ordered)
            self._names = ordered
        else:
            from app.players import set_active_names

            ordered = set_active_names(self.player_id, names)
            if not ordered:
                return False
            current = self.club
            self._names, self._extra = ordered, self._extra_for(ordered)
        self._phrase_index = self._indexes()
        self.index = self._names.index(current) if current in self._names else 0
        return True

    def _extra_for(self, names: list[str]) -> dict[str, tuple[str, ...]]:
        return {name: self._extra[name] for name in names if name in self._extra}

    def apply(self, phrase: str) -> Move | None:
        if phrase in _BY_PHRASE:
            if phrase not in self._phrase_index:
                return Move([], "not in bag")
            target = self._phrase_index[phrase]
            if self._names[target] == "Putter":
                self._synced = True
                return self._putter(target)
            if not self._synced:
                self._synced = True
                return self._first_call(target)
            if target == self.index:
                return self._realign(target)
            return self._go(target)
        if phrase in ("club up", "club down"):
            return self._step(+1 if phrase == "club up" else -1)  # club up is toward the putter: the next index
        return None

    def _step(self, delta: int) -> Move:
        """One club toward the putter (delta +1) or the driver (-1). Until a club has been called, GSPro may be on
        any club, so the putter comes first (as with a named club), then the step from there."""
        last = len(self._names) - 1
        if not self._synced:
            self._synced = True
            putter = self._names.index("Putter") if "Putter" in self._names else last
            start = putter  # U leaves GSPro on the putter, whatever it was on
            keys = [PUTT]
        else:
            start = self.index
            keys = []
        new = min(max(start + delta, 0), last)
        self.index = new
        if new > start:
            keys += [CLUB_UP] * (new - start)
        elif new < start:
            keys += [CLUB_DOWN] * (start - new)
        if not keys:
            return Move([], f"already at {self.club}, the {'putter' if delta > 0 else 'driver'} end")
        return Move(keys, _detail(keys))

    def _indexes(self) -> dict[str, int]:
        phrases_for = {club.name: club.phrases for club in CATALOG}
        indexes: dict[str, int] = {}
        for index, name in enumerate(self._names):
            for phrase in phrases_for.get(name, ()):
                indexes[phrase] = index
            for phrase in self._extra.get(name, ()):
                indexes[phrase] = index
        return indexes

    def _putter(self, target: int) -> Move:
        """U jumps straight to the putter. Remember that for the next step."""
        if target == self.index:
            return Move([], f"already on {self.club}")
        self.index = target
        return Move([PUTT], "U")

    def _go(self, target: int) -> Move:
        delta = target - self.index
        self.index = target
        if delta > 0:
            keys = [CLUB_UP] * delta
        elif delta < 0:
            keys = [CLUB_DOWN] * -delta
        else:
            keys = []
        if not keys:
            return Move([], f"already on {self.club}")
        return Move(keys, _detail(keys))

    def _first_call(self, target: int) -> Move:
        """The first club called: GSPro may be on any club, so press Putter (U) to know where it is, then walk
        down to the club called. With no putter in the bag, the walk goes from the top of the bag."""
        putter = self._names.index("Putter") if "Putter" in self._names else -1
        if putter < 0:
            downs = [CLUB_DOWN] * len(self._names)
            ups = [CLUB_UP] * target
            self.index = target
            return Move(downs + ups, _detail(downs + ups))
        keys = [PUTT] + [CLUB_DOWN] * (putter - target)
        self.index = target
        return Move(keys, _detail(keys))

    def _realign(self, target: int) -> Move:
        """Same club again. Jump to the putter, then walk back to that club."""
        putter = self._names.index("Putter") if "Putter" in self._names else -1
        if putter > target:
            keys = [PUTT] + [CLUB_DOWN] * (putter - target)
            self.index = target
            return Move(keys, _detail(keys))
        downs = [CLUB_DOWN] * len(self._names)
        ups = [CLUB_UP] * target
        self.index = target
        return Move(downs + ups, _detail(downs + ups))


def _detail(keys: list[str]) -> str:
    parts: list[str] = []
    index = 0
    while index < len(keys):
        key = keys[index]
        count = 1
        while index + count < len(keys) and keys[index + count] == key:
            count += 1
        letter = key.upper()
        parts.append(letter if count == 1 else f"{letter} x{count}")
        index += count
    return ", ".join(parts)
