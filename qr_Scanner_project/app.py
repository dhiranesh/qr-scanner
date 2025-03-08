from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
import cv2
import pandas as pd
import requests
import time
import threading

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config["SESSION_PERMANENT"] = True  # Keep session active

# Google Apps Script Web App URL
GOOGLE_SHEET_URL = "https://script.google.com/macros/s/AKfycbwzUh8Ob83S9B5N0M0gc8ONSfS6Y0l9D22KMMxAJoL3fLWyICnUyAZKUDpCLMMnz64k/exec"

# Excel File
EXCEL_FILE = "scanned_data.xlsx"
scanned_qr_codes = []  # Store scanned QR codes for live updates
scanning_active = False  # Prevent multiple threads from running

# Initialize Camera
cap = cv2.VideoCapture(0)
detector = cv2.QRCodeDetector()


def send_to_google_sheets(data):
    """Send QR code data to Google Sheets via Google Apps Script."""
    try:
        params = {"data": data}
        response = requests.get(GOOGLE_SHEET_URL, params=params, timeout=5)  # 5-sec timeout
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"Error sending data to Google Sheets: {e}")
        return False


def scan_qr_codes():
    """Continuously scan QR codes and update Google Sheets & Excel."""
    global scanning_active
    if scanning_active:
        return

    scanning_active = True

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            data, _, _ = detector.detectAndDecode(frame)

            if data and data not in scanned_qr_codes:
                scanned_qr_codes.append(data)
                print(f"Scanned QR: {data}")

                # Send Data to Google Sheets
                success = send_to_google_sheets(data)
                print(f"Google Sheets Update: {'Success' if success else 'Failed'}")

                # Save data to Excel
                df = pd.DataFrame([[data]], columns=["Scanned Data"])
                try:
                    existing_df = pd.read_excel(EXCEL_FILE)
                    df = pd.concat([existing_df, df], ignore_index=True)
                except FileNotFoundError:
                    pass
                df.to_excel(EXCEL_FILE, index=False)

                time.sleep(1)  # Small delay to avoid duplicate scanning
    except Exception as e:
        print(f"Error during QR scanning: {e}")
    finally:
        scanning_active = False


def generate_frames():
    """Generate frames from the webcam for live preview."""
    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            _, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/')
def login():
    """Render the login page."""
    return render_template('login.html')


@app.route('/authenticate', methods=['POST'])
def authenticate():
    """Handle user authentication."""
    username = request.form.get('username')
    password = request.form.get('password')

    if username == 'admin' and password == 'password':
        session['logged_in'] = True
        return redirect(url_for('scan_qr'))
    else:
        return "Invalid Credentials", 401


@app.route('/scan_qr', methods=['GET'])
def scan_qr():
    """Render the QR scanner page and start scanning."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    # Start scanning thread if not already running
    threading.Thread(target=scan_qr_codes, daemon=True).start()
    return render_template('scan_qr.html')


@app.route('/video_feed')
def video_feed():
    """Provide live video feed to the frontend."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/get_scanned_data', methods=['GET'])
def get_scanned_data():
    """Send scanned QR data to the frontend."""
    return jsonify(scanned_qr_codes)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
