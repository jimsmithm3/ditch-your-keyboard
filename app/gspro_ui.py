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
# Home has no BACK, so the upper left is blank there. "home screen" clicks BACK until
# this area stops changing, which means home. Everything below the header.
HOME_WATCH = (0.0, 0.17, 1.0, 0.95)

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
