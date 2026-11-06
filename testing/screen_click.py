import time
import pygetwindow as gw
import pydirectinput

print("Locating GSPro window...")
windows = gw.getWindowsWithTitle("GSPro")

if windows:
    gspro_win = windows[0]
    
    # 1. Bring the window to the front safely
    gspro_win.activate()
    time.sleep(1) # Give the OS a second to animate and focus
    
    # 2. Calculate the exact center coordinates of your GSPro window
    center_x = gspro_win.left + (gspro_win.width // 2)
    center_y = gspro_win.top + (gspro_win.height // 2)
    
    print(f"Forcing focus click at screen coordinates: ({center_x}, {center_y})")
    
    # 3. Inject a hard hardware click right on the fairway terrain
    pydirectinput.click(center_x, center_y)
    print("Click sent! Your target marker flag should now be on the screen.")
    
else:
    print("Could not find a window titled 'GSPro'. Make sure the game is running!")