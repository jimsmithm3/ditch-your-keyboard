import socket
import json


REPLY_TIMEOUT_SECONDS = 5.0  # how long to wait for the connector's reply before giving up


def fire_gspro_tcp_shot():
    # Target localhost Open Connect API port
    GSPRO_IP = "127.0.0.1"
    GSPRO_PORT = 921

    # Standard Open Connect spec payload structure
    shot_payload = {
        "DeviceID": "PythonAutomationClient",
        "Units": "Yards",
        "ShotNumber": 4,
        "APIversion": "1",
        "BallData": {
            "Speed": 152.3,  # Ball Speed (mph)
            "SpinAxis": -2.1,  # Spin Axis
            "TotalSpin": 2450.0,  # Total Spin (rpm)
            "BackSpin": 2400.0,  # Back Spin
            "SideSpin": -120.0,  # Side Spin
            "HLA": -0.8,  # Horizontal Launch Angle (degrees)
            "VLA": 11.8  # Vertical Launch Angle (degrees)
        },
        "ClubData": {
            "Speed": 102.5,
            "Path": 1.1,
            "FaceToPath": -0.4,
            "AoA": 2.2
        },
        "ShotDataOptions": {
            "ContainsBallData": True,
            "ContainsClubData": True,
            "LaunchMonitorIsReady": True,
            "LaunchMonitorBallDetected": True,
            "IsHeartBeat": False
        }
    }

    try:
        # FIX: Using socket.SOCK_STREAM to establish a proper TCP link
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # A timeout, so the script cannot hang waiting for a reply. Ctrl+C does not interrupt a blocked
            # socket call on Windows, so the timeout is the way out.
            sock.settimeout(REPLY_TIMEOUT_SECONDS)
            print(f"[*] Attempting TCP connection to GSPro Connect on port {GSPRO_PORT}...")
            sock.connect((GSPRO_IP, GSPRO_PORT))

            # Encode and send the payload data string
            json_data = json.dumps(shot_payload)
            sock.sendall(json_data.encode('utf-8'))
            print("[+] Payload transmitted successfully!")

            # Read the confirmation response code directly from the API connector
            try:
                raw_response = sock.recv(2048)
            except socket.timeout:
                print(f"[!] No reply within {REPLY_TIMEOUT_SECONDS:.0f} seconds; stopping. The shot was sent.")
                return
            if raw_response:
                print(f"[+] API Connector Feedback: {raw_response.decode('utf-8')}")
            else:
                print("[!] The connector closed the connection without a reply.")

    except Exception as e:
        print(f"[!] Connection failed: {e}")


if __name__ == "__main__":
    fire_gspro_tcp_shot()