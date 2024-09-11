from flask import Flask, request, jsonify, Response, make_response, render_template_string
import os
import time
import subprocess
import logging
import shutil
from functools import wraps
import threading
import uuid
import psutil



app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Disable Gunicorn log propagation to avoid conflicts
logging.getLogger('gunicorn.error').propagate = False

# Dictionary to track active VNC sessions
vnc_sessions = {}  # Initialize the vnc_sessions dictionary
max_sessions = 3  # Maximum number of simultaneous VNC sessions

# Basic authentication setup
USERNAME = 'haie'  # Replace with your username
PASSWORD = 'haie_password'  # Replace with your password

# URL sets for different tasks
TASK_URLS = {
    'task1': ['https://clemson.ca1.qualtrics.com/jfe/form/SV_43oeyeXXXSl4E8C', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_0cakjlkRVqAdw6q', 'https://chatgpt.com/g/g-0rpi2I0gR-task-manager-model-1?temporary-chat=true', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_1GL7c2KFjChBR4O', 'https://calendar.google.com', 'https://tasksboard.com/app'],
    'task2': ['https://clemson.ca1.qualtrics.com/jfe/form/SV_8BUBBh1TRuWDzee', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_0k6ohyxgZhdk0JM', 'https://chatgpt.com/g/g-gYHcYVU5e-task-manager-model-2?temporary-chat=true', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_eM78KRHM7fMh6Rw', 'https://mail.google.com', 'https://tasksboard.com/app'],
    'task3': ['https://clemson.ca1.qualtrics.com/jfe/form/SV_2mMI61VntgSVXWm', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_3XcESDgWHGftsLc', 'https://chatgpt.com/g/g-Bj9mwN7K1-task-manager-model-3?temporary-chat=true', 'https://clemson.ca1.qualtrics.com/jfe/form/SV_6XpcBAHmQynzqke', 'https://drive.google.com', 'https://tasksboard.com/app']
}

# Task to display and port mapping
TASK_CONFIG = {
    'task1': {'display': 1, 'vnc_port': 5901, 'novnc_port': 6901},
    'task2': {'display': 2, 'vnc_port': 5902, 'novnc_port': 6902},
    'task3': {'display': 3, 'vnc_port': 5903, 'novnc_port': 6903},
}


def requires_auth(f):
    """Decorator to enforce basic authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def check_auth(username, password):
    """Check if a username/password combination is valid."""
    return username == USERNAME and password == PASSWORD

def authenticate():
    """Sends a 401 response that enables basic auth, with a varying realm to prevent caching."""
    realm = f"Login Required {int(time.time())}"  # Use time to create a unique realm
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {
            'WWW-Authenticate': 'Basic',
            'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Expires': '0'
        })
        
def no_cache(view):
    """Decorator to add no-cache headers to a response."""
    @wraps(view)
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return no_cache_view

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


@app.route('/thank-you')
def thank_you():
    return render_template_string("""
        <html>
        <head><title>Thank You</title></head>
        <body>
            <h1>Thank You!</h1>
            <p>Your session has been successfully stopped. Thank you for your time.</p>
        </body>
        </html>
    """)

    
@app.route('/env/task1', methods=['GET'])
@app.route('/env/task2', methods=['GET'])
@app.route('/env/task3', methods=['GET'])
#@requires_auth
@no_cache
def start_vnc_task():
    task = request.path.strip('/env/')  # Extract task from URL

    if task not in TASK_URLS:
        app.logger.error(f"Invalid task: {task}")
        return jsonify({"error": "Invalid task"}), 400

    # Check if the task is already running
    if TASK_CONFIG[task]['display'] in vnc_sessions:
        app.logger.info(f"Task {task} is already running.")
        return render_template_string("""
            <html>
            <head><title>VM in Use</title></head>
            <body>
                <h1>VM in use</h1>
                <p>This VM is already in use. Please try again later.</p>
            </body>
            </html>
        """)

    # Check if the maximum number of VNC sessions is reached
    if len(vnc_sessions) >= max_sessions:
        app.logger.info(f"Maximum number of VNC sessions reached.")
        return render_template_string("""
            <html>
            <head><title>No VM Available</title></head>
            <body>
                <h1>No Vitual Machines Available</h1>
                <p>All Machines are currently in use. Please try again later.</p>
            </body>
            </html>
        """)

    try:
        display_num = TASK_CONFIG[task]['display']
        vnc_port = TASK_CONFIG[task]['vnc_port']
        no_vnc_port = TASK_CONFIG[task]['novnc_port']

        vnc_process, novnc_process, session_id = start_vnc_server(display_num, vnc_port, no_vnc_port, TASK_URLS[task])
        vnc_sessions[display_num] = (vnc_process, novnc_process)
        schedule_shutdown(display_num, vnc_port, no_vnc_port, 2 * 60 * 60, session_id)  # 2 hours

        # Return the HTML page with an automatic redirect
        vnc_url = f'http://{request.host.split(":")[0]}/vm/?session={display_num}&scale=true'
        return render_template_string(f"""
            <html>
            <head>
                <title>Redirecting...</title>
                <meta http-equiv="refresh" content="0; url={vnc_url}" />
            </head>
            <body>
                <p>Redirecting to your VNC session. If you are not redirected, <a href="{vnc_url}">click here</a>.</p>
                <script type="text/javascript">
                    window.location.href = "{vnc_url}";
                </script>
            </body>
            </html>
        """)

    except RuntimeError as e:
        app.logger.error(f"Runtime error: {str(e)}")
        return jsonify({"error": f"Runtime error: {str(e)}"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


def start_vnc_server(display_num, vnc_port, no_vnc_port, urls):
    try:
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

    # Launch Firefox using OpenKiosk with the copied profile
    XDG_CACHE_HOME={CACHE_DIR} OpenKiosk --profile {PROFILE_DIR} --new-instance {' '.join(urls)} &

    '''

        script_path = f'/tmp/start_browser_{display_num}.sh'
        with open(script_path, 'w') as script_file:
            script_file.write(vnc_startup_script)
        os.chmod(script_path, 0o755)

        time.sleep(2)
        vnc_process = subprocess.Popen(['bash', '/dockerstartup/vnc_startup.sh'])
        time.sleep(5)  # Ensure the VNC server starts
        novnc_process = subprocess.Popen(['bash', script_path])

        session_id = str(uuid.uuid4())  # Generate a unique session ID
        vnc_sessions[display_num] = (vnc_process, novnc_process, session_id)

        return vnc_process, novnc_process, session_id

    except Exception as e:
        app.logger.error(f"Error in start_vnc_server: {str(e)}", exc_info=True)
        raise RuntimeError(f"Failed to start VNC or noVNC processes: {str(e)}")

# @app.route('/stop/<int:display_num>')
# # @requires_auth
# def stop_vnc(display_num):
#     """Manually stop a VNC session based on the display number."""
#     if display_num not in vnc_sessions:
#         app.logger.error(f"Attempt to stop non-existent session: display {display_num}")
#         return jsonify({"error": "Session not found"}), 404

#     try:
#         stop_vnc_session(display_num)
#         return jsonify({"message": f"Session stopped for display {display_num}"}), 200
#     except Exception as e:
#         app.logger.error(f"Failed to stop session for display {display_num}: {str(e)}", exc_info=True)
#         return jsonify({"error": "Failed to stop session"}), 500

# @app.route('/stop/<int:display_num>', methods=['POST'])
# def stop_vnc(display_num):
#     """Manually stop a VNC session based on the display number, with POST request and header validation."""
#     # Validate the custom header
#     # header_value = request.headers.get('X-Auth-Token')  # Replace 'X-Auth-Token' with your preferred header name
#     # if header_value != 'mp01k3VEVC2URGuLMJy4GgF9iV9NNP':
#     #     return render_template_string("""
#     #         <html>
#     #         <head><title>Unauthorized</title></head>
#     #         <body>
#     #             <h1>Unauthorized Access</h1>
#     #         </body>
#     #         </html>
#     #     """), 403

#     # Check if the display number exists in active sessions
#     if display_num not in vnc_sessions:
#         app.logger.error(f"Attempt to stop non-existent session: display {display_num}")
#         return render_template_string("""
#             <html>
#             <head><title>Session Not Found</title></head>
#             <body>
#                 <h1>Session Not Found</h1>
#                 <p>The session you are trying to stop does not exist.</p>
#             </body>
#             </html>
#         """), 404

#     try:
#         stop_vnc_session(display_num)
#         return render_template_string("""
#             <html>
#             <head><title>Session Stopped</title></head>
#             <body>
#                 <h1>Thank you for your time!</h1>
#                 <p>The Environment has been successfully stopped.</p>
#             </body>
#             </html>
#         """, display_num=display_num)
#     except Exception as e:
#         app.logger.error(f"Failed to stop session for display {display_num}: {str(e)}", exc_info=True)
#         return render_template_string("""
#             <html>
#             <head><title>Error</title></head>
#             <body>
#                 <h1>Error</h1>
#                 <p>There was an error stopping the session. Please try again later.</p>
#             </body>
#             </html>
#         """), 500


@app.route('/stop/<int:display_num>', methods=['POST'])
def stop_vnc(display_num):
    """Manually stop a VNC session based on the display number."""
    if stop_vnc_session(display_num):
        return render_template_string("""
            <html>
            <head><title>Session Stopped</title></head>
            <body>
                <h1>Thank you for your time!</h1>
                <p>The Environment has been successfully stopped.</p>
            </body>
            </html>
        """, display_num=display_num)
    else:
        return render_template_string("""
            <html>
            <head><title>Session Not Found</title></head>
            <body>
                <h1>Session Not Found</h1>
                <p>The session you are trying to stop does not exist or is already stopped.</p>
            </body>
            </html>
        """), 404



# def stop_vnc_session(display_num):
#     """Stop the VNC session and release resources."""
#     if display_num in vnc_sessions:
#         vnc_process, novnc_process = vnc_sessions.pop(display_num)
#         vnc_process.terminate()
#         novnc_process.terminate()
#         os.system(f'vncserver -kill :{display_num}')
#         app.logger.info(f"Session stopped for display {display_num}")

def stop_vnc_session(display_num):
    """Stop the VNC session and release resources."""
    vnc_port = TASK_CONFIG[f'task{display_num}']['vnc_port']
    
    # Check if the VNC port is in use and kill the process using it
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'Xvnc' in proc.info['name'] or 'Xtigervnc' in proc.info['name']:
                cmdline = proc.info['cmdline']
                if f':{display_num}' in cmdline:
                    proc.terminate()
                    proc.wait(timeout=15)
                    #app.logger.info(f"Session on display {display_num} stopped.")
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    #app.logger.error(f"No active VNC session found on display {display_num}")
    return False



def schedule_shutdown(display_num, vnc_port, no_vnc_port, delay, session_id):
    def shutdown():
        time.sleep(delay)
        if display_num in vnc_sessions and vnc_sessions[display_num][2] == session_id:
            try:
                stop_vnc_session(display_num)
                # app.logger.info(f"Shutdown complete for display {display_num}, VNC port {vnc_port}, noVNC port {no_vnc_port}")
            except Exception as e:
                pass
                # app.logger.error(f"Error during scheduled shutdown for display {display_num}: {str(e)}", exc_info=True)

    threading.Thread(target=shutdown).start()




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
