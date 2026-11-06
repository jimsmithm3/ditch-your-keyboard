import socket
import json
import time

def inject_api_test_shot():
    # Use the same port configured in your GSPro Open Connect settings (usually 921 or 2483)
    HOST = '127.0.0.1'
    PORT = 921 
    
    # Standard GSPro Open Connect shot data packet format
    shot_packet = {
        "Type": "ShotData",
        "BallData": {
            "Speed": 150.0,       # mph
            "LaunchAngle": 12.5,   # degrees vertical
            "Direction": 0.0,      # degrees horizontal (straight)
            "SpinAxis": 0.0,       # no side spin
            "TotalSpin": 2500.0    # rpm backspin
        },
        "ClubData": {
            "Speed": 105.0
        }
    }
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((HOST, PORT))
        
        # Serialize to JSON string and append a newline if your connection settings require it
        payload = json.dumps(shot_packet) + "\n"
        s.sendall(payload.encode('utf-8'))
        
        print("🚀 Success! Sent an official shot packet through the Open Connect API.")
        s.close()
    except Exception as e:
        print(f"Failed to connect to GSPro API: {e}")
        print("Make sure GSPro is running and the Open Connect window is actively listening.")

if __name__ == "__main__":
    inject_api_test_shot()