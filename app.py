# Required installations:
# pip install flask flask-session flask-socketio eventlet pandas

from eventlet import monkey_patch
# Only patch what’s needed (no 'os', no 'io')
monkey_patch(socket=True, select=True, time=True)

from flask import Flask, render_template, session, request
from flask_session import Session
from flask_socketio import SocketIO, emit
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'secret!'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './.flask_session/'
app.config['SESSION_PERMANENT'] = False
Session(app)

# Use eventlet (safe now since we didn’t patch file I/O)
socketio = SocketIO(app, async_mode='eventlet', manage_session=False)

# Per-connection in-memory DataFrame store (per socket, not global)
socket_df_map = {}

# Mock DataFrame loader
def load_dataframe_for_user(project_id):
    print(f"Loading DataFrame for project: {project_id}")
    data = {'A': [1, 2, 3], 'B': [4, 5, 6]}
    return pd.DataFrame(data)

# Execute Python code on user's DataFrame
def execute_query(df, code):
    local_vars = {'df': df}
    try:
        exec(code, {}, local_vars)
        return str(local_vars.get('result', 'No result returned'))
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/')
def index():
    session['username'] = 'jay'
    session['project_id'] = 'DFC-001'
    return render_template('chat.html')

@socketio.on('connect')
def on_connect():
    username = session.get('username')
    project_id = session.get('project_id')
    if username and project_id:
        df = load_dataframe_for_user(project_id)
        socket_df_map[request.sid] = df
        print(f"[{request.sid}] Connected. Loaded DataFrame for {username}.")
        emit('response', {'msg': 'Connected and DataFrame loaded.'})
    else:
        emit('response', {'msg': 'Session missing required info.'})

@socketio.on('user_message')
def handle_user_message(data):
    user_query = data.get('msg', '')
    df = socket_df_map.get(request.sid)
    if df is not None:
        answer = execute_query(df, user_query)
        emit('response', {'msg': answer})
    else:
        emit('response', {'msg': 'No DataFrame found for session.'})

@socketio.on('disconnect')
def on_disconnect():
    socket_df_map.pop(request.sid, None)
    print(f"[{request.sid}] Disconnected and DataFrame removed.")

if __name__ == '__main__':
    if not os.path.exists('./.flask_session/'):
        os.makedirs('./.flask_session/')
    socketio.run(app, debug=True)
