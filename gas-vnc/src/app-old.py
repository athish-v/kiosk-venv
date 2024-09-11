from flask import Flask, request, jsonify, render_template_string, abort
import os
import time
import subprocess
import threading
import logging
import shutil
from functools import wraps  # Import wraps for decorators

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Password for accessing VNC sessions
ACCESS_PASSWORD = 'HAIE_password'  # Set your desired password here

# Set of currently used ports and displays
used_ports = set()
used_displays = set()
vnc_sessions = {}  # Map display numbers to (vnc_process, novnc_process)

# Define port ranges for VNC and noVNC
VNC_PORT_RANGE = range(5901, 5904)
NOVNC_PORT_RANGE = range(6901, 6904)
DISPLAY_RANGE = range(1, 4)  # X11 display numbers

# URL sets for different tasks
TASK_URLS = {
    'task1': ['https://clemson.ca1.qualtrics.com/jfe/form/SV_0cakjlkRVqAdw6q', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_43oeyeXXXSl4E8C', 'https://chatgpt.com/g/g-0rpi2I0gR-task-manager-model-1', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_1GL7c2KFjChBR4O', 'https://calendar.google.com', 'https://tasks.google.com'],
    'task2': ['https://clemson.ca1.qualtrics.com/jfe/form/SV_0k6ohyxgZhdk0JM', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_8BUBBh1TRuWDzee', 'https://chatgpt.com/g/g-gYHcYVU5e-task-manager-model-2', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_eM78KRHM7fMh6Rw', 'https://mail.google.com', 'https://tasks.google.com'],
    'task3': ['https://clemson.ca1.qualtrics.com/jfe/form/SV_3XcESDgWHGftsLc', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_2mMI61VntgSVXWm', 'https://chatgpt.com/g/g-Bj9mwN7K1-task-manager-model-3', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_6XpcBAHmQynzqke', 'https://drive.google.com', 'https://tasks.google.com']
}

# Basic authentication setup
USERNAME = 'athishv'  # Replace with your username
PASSWORD = 'Edupassword1'  # Replace with your password

def check_auth(username, password):
    """Check if a username/password combination is valid."""
    return username == USERNAME and password == PASSWORD

def authenticate():
    """Send a 401 response that enables basic auth."""
    return jsonify({"error": "Unauthorized access"}), 401

def requires_auth(f):
    """Decorator to enforce basic authentication."""
    @wraps(f)  # Use wraps to preserve function metadata
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def home():
    return render_template_string("""
        <html>
        <head>
            <title>HAIE Lab Virtual Environment</title>
            <meta charset="utf-8">
            <meta name="description" content="Welcome to the HAIE Lab Virtual Environment">
        </head>
        <body>
            <h1>Welcome to the HAIE Lab Virtual Environment!</h1>
            <p>This is a secure platform for managing your virtual sessions.</p>
        </body>
        </html>
    """)

@app.route('/env')
def env_page():
    return render_template_string("""
        <html>
        <head>
            <title>Task Selection</title>
            <meta charset="utf-8">
            <meta name="description" content="Select a task to start a VNC session">
            <style>
                body {font-family: Arial, sans-serif; text-align: center; margin-top: 50px;}
                h1 {color: #333;}
                button {padding: 10px 20px; font-size: 16px; margin: 10px; cursor: pointer; border-radius: 5px; border: none; background-color: #4CAF50; color: white;}
                button:hover {background-color: #45a049;}
                input[type="password"] {padding: 10px; font-size: 16px; margin: 10px;}
            </style>
        </head>
        <body>
            <h1>Select a Task</h1>
            <input type="password" id="accessPassword" placeholder="Enter Access Password" required>
            <div>
                <button onclick="startSession('task1')">Start Task 1</button>
                <button onclick="startSession('task2')">Start Task 2</button>
                <button onclick="startSession('task3')">Start Task 3</button>
            </div>
            <p id="statusMessage"></p>

            <script>
                function startSession(task) {
                    const password = document.getElementById('accessPassword').value;

                    fetch(`/env/${task}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({password: password})
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            document.getElementById('statusMessage').innerText = data.error;
                        } else {
                            window.location.href = data.url;
                        }
                    })
                    .catch(error => {
                        document.getElementById('statusMessage').innerText = "An error occurred.";
                    });
                }
            </script>
        </body>
        </html>
    """)

@app.route('/env/<task>', methods=['POST'])
def start_vnc(task):
    # Get password from the request
    data = request.json
    password = data.get('password', '')

    # Verify the password
    if password != ACCESS_PASSWORD:
        app.logger.error(f"Unauthorized access attempt with incorrect password.")
        return jsonify({"error": "Unauthorized access: Incorrect password."}), 401

    if task not in TASK_URLS:
        app.logger.error(f"Invalid task: {task}")
        return jsonify({"error": "Invalid task"}), 400

    try:
        display_num = allocate_display(DISPLAY_RANGE)
        vnc_port = allocate_port(VNC_PORT_RANGE)
        no_vnc_port = allocate_port(NOVNC_PORT_RANGE)
        vnc_process, novnc_process = start_vnc_server(display_num, vnc_port, no_vnc_port, TASK_URLS[task])
        vnc_sessions[display_num] = (vnc_process, novnc_process)
        schedule_shutdown(display_num, vnc_port, no_vnc_port, 2 * 60 * 60)  # 2 hours

        # Return the URL for the VNC session
        vnc_url = f'http://{request.host.split(":")[0]}/vm/?session={display_num}'
        return jsonify({"url": vnc_url}), 200

    except RuntimeError as e:
        app.logger.error(f"Runtime error: {str(e)}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred."}), 500

@app.route('/stop/<int:display_num>')
@requires_auth
def stop_vnc(display_num):
    """Manually stop a VNC session based on the display number."""
    if display_num not in vnc_sessions:
        app.logger.error(f"Attempt to stop non-existent session: display {display_num}")
        return jsonify({"error": "Session not found"}), 404

    try:
        stop_vnc_session(display_num)
        return jsonify({"message": f"Session stopped for display {display_num}"}), 200
    except Exception as e:
        app.logger.error(f"Failed to stop session for display {display_num}: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to stop session"}), 500

def stop_vnc_session(display_num):
    """Stop the VNC session and release resources."""
    if display_num in vnc_sessions:
        vnc_process, novnc_process = vnc_sessions.pop(display_num)
        vnc_process.terminate()
        novnc_process.terminate()
        os.system(f'vncserver -kill :{display_num}')
        release_display(display_num)
        release_port(display_num + 5900)
        release_port(display_num + 6900)
        app.logger.info(f"Session stopped for display {display_num}")

def allocate_port(port_range):
    for port in port_range:
        if port not in used_ports:
            used_ports.add(port)
            return port
    raise RuntimeError("No available ports in range")

def release_port(port):
    used_ports.discard(port)

def allocate_display(display_range):
    for display in display_range:
        if display not in used_displays:
            used_displays.add(display)
            return display
    raise RuntimeError("No available displays in range")

def release_display(display):
    used_displays.discard(display)

def start_vnc_server(display_num, vnc_port, no_vnc_port, urls):
    os.environ['VNC_PORT'] = f'{vnc_port}'
    os.environ['NO_VNC_PORT'] = f'{no_vnc_port}'
    os.environ['DISPLAY'] = f':{display_num}'

    PROFILE_DIR = f"/browserProf/firefox-profile-{display_num}"
    CACHE_DIR = f"/browserProf/firefox-cache-{display_num}"

    # Check if profile directory exists, if not create and copy the master profile
    if not os.path.exists(PROFILE_DIR):
        os.makedirs(PROFILE_DIR)
        os.makedirs(CACHE_DIR)

        # Copy master profile files
        master_profile_dir = os.path.expanduser('/headless/broProf')  # Path to the master profile
        if os.path.exists(master_profile_dir):
            for item in os.listdir(master_profile_dir):
                s = os.path.join(master_profile_dir, item)
                d = os.path.join(PROFILE_DIR, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
        else:
            app.logger.error("Master profile directory does not exist.")
            raise RuntimeError("Master profile directory not found.")

    vnc_startup_script = f'''
#!/bin/bash
set -e

export DISPLAY=:{display_num}

#cp $HOME/prefs.js $PROFILE_DIR/prefs.js

# Launch Firefox using OpenKiosk with the copied profile
XDG_CACHE_HOME={CACHE_DIR} OpenKiosk --profile {PROFILE_DIR} --new-instance {' '.join(urls)} &

'''

    script_path = f'/tmp/start_browser_{display_num}.sh'
    with open(script_path, 'w') as script_file:
        script_file.write(vnc_startup_script)
    os.chmod(script_path, 0o755)

    try:
        vnc_process = subprocess.Popen(['bash', '/dockerstartup/vnc_startup.sh'])
        time.sleep(5)  # Ensure the VNC server starts
        novnc_process = subprocess.Popen(['bash', script_path])
    except Exception as e:
        app.logger.error(f"Error starting VNC or noVNC: {str(e)}", exc_info=True)
        raise RuntimeError("Failed to start VNC or noVNC processes.")

    return vnc_process, novnc_process

def schedule_shutdown(display_num, vnc_port, no_vnc_port, delay):
    def shutdown():
        time.sleep(delay)
        if display_num in vnc_sessions:
            try:
                stop_vnc_session(display_num)
                app.logger.info(f"Shutdown complete for display {display_num}, VNC port {vnc_port}, noVNC port {no_vnc_port}")
            except Exception as e:
                app.logger.error(f"Error during scheduled shutdown for display {display_num}: {str(e)}", exc_info=True)

    thread = threading.Thread(target=shutdown)
    thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
