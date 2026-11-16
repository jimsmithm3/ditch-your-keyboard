"""The common words the spoken grammars are built from, in one place.

Change a word here and every phrase built from it changes with it, so a word that keeps getting misheard can be
swapped without editing each phrase. Phrases are written as f-strings that use these names.
"""

NAV = "begin"  # the screen-navigation word: "begin practice", "begin on course practice now", "start application"
TOGGLE = "toggle"  # the on/off word: "toggle ui", "toggle favorite three", "toggle listening"
