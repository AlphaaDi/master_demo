import argparse
from flask import Flask, jsonify, request
import json
import sqlite3
import os
from pathlib import Path
from sql_handler import *

# Define Flask application
app = Flask(__name__)


parser = argparse.ArgumentParser(description="Run Flask and Gradio in parallel.")
parser.add_argument('--database', type=str, default='files/task_database.db', help='Path to the SQLite database file.')
parser.add_argument('--flask_port', type=int, default=6000, help='Port for the Flask server.')
parser.add_argument('--flask_host', default='0.0.0.0', help='Host for the Flask server.')

parser.add_argument('--blob_storage_path', type=str, default='files/blob_storage', help='Path to the blob storage directory.')

args = parser.parse_args()

# Ensure blob storage directory exists
if not os.path.exists(args.blob_storage_path):
    os.makedirs(args.blob_storage_path)


@app.route('/process_video_result', methods=['POST'])
def process_video_result():
    task_id = request.form['task_id']
    video_file = request.files['video']
    task_dir = Path(args.blob_storage_path) / task_id
    task_dir.mkdir(exist_ok=True)
    video_path = os.path.join(str(task_dir), task_id + '_' + video_file.filename)
    
    # Save video in blob storage
    video_file.save(video_path)

    # Update SQLite database
    task_db = TaskDatabase(args.database)
    task_db.update_task_status(task_id, video_path, status='ready')

    return jsonify({'message': 'Video processed and task updated successfully'})


if __name__ == '__main__':
    app.run(host=args.flask_host, port=args.flask_port)