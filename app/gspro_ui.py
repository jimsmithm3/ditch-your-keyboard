"""GSPro screen layout for the voice-driven clicks.

GSPro exposes no accessibility tree and no API for menus, so the clicks use positions.
Each position is a fraction (0..1) of the GSPro window, read from screenshots of the
app at 16:9. Only positions and watch areas live here. The steps that use them are in
gspro_sequences.py.

Limit: GSPro must be in the screen the sequence expects. The app cannot see which
screen GSPro is on.
"""

GSPRO_TITLE = "GSPro"

# Home screen
PRACTICE_CARD = (0.317, 0.722)  # PRACTICE
MENU_BUTTON = (0.975, 0.039)  # game menu, upper right (hamburger)

# Practice screen
RANGE_CARD = (0.318, 0.712)  # GSPRO PRACTICE RANGE

# Any screen with a BACK button (upper left). Nested screens have one BACK each, so say
# "go back" again to go up another level.
BACK_BUTTON = (0.06, 0.044)  # BACK, upper left
EXIT_BUTTON = (0.06, 0.042)  # EXIT, upper left of the home screen
# Home has no BACK, so the upper left is blank there. "home screen" clicks BACK until
# this area stops changing, which means home. Everything below the header.
HOME_WATCH = (0.0, 0.17, 1.0, 0.95)

# On course practice: the course list. The search box starts with the cursor in it.
ON_COURSE_CARD = (0.5, 0.72)  # ON COURSE PRACTICE on the practice screen
ADDITIONAL_CARD = (0.682, 0.722)  # ADDITIONAL RANGES on the practice screen
LOCAL_CARD = (0.135, 0.722)  # PLAY on the home screen, which opens LOCAL MATCH (the course list)

# Mini map on the course screen. Its center is where a marker is dropped.
MAP_SMALL_CENTER = (0.921, 0.758)  # the small map, lower right
MAP_EXPANDED_CENTER = (0.855, 0.544)  # the map when expanded with S
SEARCH_BOX = (0.35, 0.123)  # "What course do you want to play?"
CLEAR_SEARCH_CLICK = (0.052, 0.125)  # first letter of the search text; a click here selects all of it
FIRST_PLAY = (0.612, 0.208)  # PLAY on the first row of the list
FILTER_INSTALLED = (0.731, 0.266)  # the Installed filter button (the whole list)
FILTER_FAVORITES = (0.934, 0.266)  # the Favorites filter button
COURSE_LIST_WATCH = (0.0, 0.17, 0.66, 0.95)  # the course rows; change when the search results change

# Course play (after PLAY on round settings). MENU_BUTTON opens the game menu; MENU_CLOSE is its X.
MENU_CLOSE = (0.970, 0.040)

# Round settings (opens after a course's Play). The lower right button is "PLAY <course>".
ROUND_PLAY = (0.884, 0.954)
# Round settings tabs, along the top (read from the round settings screenshots at 16:9)
ROUND_TAB_PLAYERS = (0.363, 0.129)
ROUND_TAB_MATCH = (0.500, 0.129)
ROUND_TAB_HOLES = (0.623, 0.129)
# Practice range: the driving range panel (open with the chevron, edit distance with the pencil)
PREFERENCES_CHEVRON = (0.313, 0.052)  # the chevron at the top right of the panel (moved up and right from the first try)
DISTANCE_PENCIL = (0.268, 0.289)  # the pencil on the Driving Range Distance box
APPLY_BUTTON = (0.276, 0.496)  # APPLY at the bottom of the panel
RANDOMIZER_ICON = (0.113, 0.341)  # the two arrows next to Randomizer On/Off
# Shots Per boxes, on the same row as Randomizer On/Off (x read from the screenshot at 1999 wide)
SHOTS_1 = (0.1886, 0.3407)
SHOTS_3 = (0.2066, 0.3407)
SHOTS_5 = (0.2246, 0.3407)
SHOTS_10 = (0.2426, 0.3407)
SHOTS_15 = (0.2606, 0.3407)
PANEL_CLOSE_CHEVRON = (0.298, 0.123)  # the up arrow at the top right of the open panel (closes it)
# Sliders: the left end of each track (where a press puts the thumb) and the right end's x, on the same row.
MAX_SLIDER_LEFT = (0.024, 0.395)  # 5 px right of the first try (that landed just left of the track), then 2 px back left; the click was pulling the slider
MIN_SLIDER_LEFT = (0.0245, 0.4475)
SLIDER_RIGHT_X = 0.2066

# Game menu (opens over the upper right of the range)
END_ROUND_BUTTON = (0.903, 0.636)  # END ROUND at the bottom of the menu

# Confirmation dialog (opens in the middle of the screen)
CONFIRM_BUTTON = (0.443, 0.579)  # CONFIRM

# Watch areas: a sequence step waits for one of these to change after its click.
# Each is (left, top, right, bottom) as fractions of the window.
WATCH_SCREEN = (0.55, 0.12, 0.95, 0.34)  # upper-right sky and hills: changes between screens
WATCH_MENU = (0.82, 0.02, 0.99, 0.60)  # the game menu panel on the right
WATCH_DIALOG = (0.38, 0.38, 0.62, 0.62)  # the confirmation dialog in the middle

NEUTRAL_POINT = (0.5, 0.97)  # bottom middle: grass, no button
