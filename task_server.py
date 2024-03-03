import argparse
from flask import Flask, jsonify, request, redirect, url_for, render_template
from flask import send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import csv
import json
import uuid
from pathlib import Path
from mongo_handler import TaskDatabase, TaskStatus  # Import your MongoDB TaskDatabase class and TaskStatus enum
from functools import wraps
from common import send_notification_to_popup

# Define Flask application
app = Flask(__name__)

# Parse arguments

parser = argparse.ArgumentParser(description="Run Flask and Gradio in parallel.")
parser.add_argument('--database_host', default='localhost', help='MongoDB host.')
parser.add_argument('--database_port', default=27017, help='MongoDB port.')
parser.add_argument('--database_name', default='app', help='MongoDB database name.')
parser.add_argument('--flask_port', type=int, default=8100, help='Port for the Flask server.')
parser.add_argument('--flask_host', default='0.0.0.0', help='Host for the Flask server.')
parser.add_argument('--blob_storage_path', type=str, default='files/blob_storage', help='Path to the blob storage directory.')
parser.add_argument('--template_config_path', type=str, default='files/styles_config.csv', help='Path to the template config')
parser.add_argument('--styles_config_storage', type=str, default='files/configs', help='Path to the blob storage directory.')
args = parser.parse_args()


blob_storage = Path(args.blob_storage_path)
blob_storage.mkdir(exist_ok=True)

task_db = TaskDatabase(
    db_host=args.database_host,
    db_port=args.database_port,
    db_name=args.database_name
)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,  # or any function that returns a unique identifier for each user
    default_limits=["200 per day", "50 per hour"]  # Example rate limits
)

def require_valid_uuid(task_db):
    def decorator(view_function):
        @wraps(view_function)
        def decorated_function(*args, **kwargs):
            data = request.get_json(force=True)
            token = data.get('token', None)
            if token and task_db.uuid_exists(token):
                return view_function(*args, **kwargs)
            else:
                return jsonify({"error": "Invalid or missing UUID key"}), 401
        return decorated_function
    return decorator


@app.route('/register_for_token', methods=['POST'])
def register_for_token():
    data = request.get_json(force=True)
    token = data.get('token', None)
    if not task_db.check_uuid_exists(token):
        token = str(uuid.uuid4())
        task_db.store_link_with_uuid(token)

    return jsonify({'token': token}), 200


@app.route('/store_apns', methods=['POST'])
@require_valid_uuid(task_db)
def store_apns():
    data = request.get_json(force=True)
    try:
        token = data['token']
        apns_token = data['apns_token']  
    except BaseException as e:
        return jsonify({'error': str(e)}), 400
    
    is_ok = task_db.update_collection_with_prop(token, apns_token, 'apns_token')
    if is_ok:
        return jsonify({'token': token}), 200
    else:
        return jsonify({'error': 'something wrong, zero object was modified'}), 400


@app.route('/get_templates', methods=['GET'])
@require_valid_uuid(task_db)
def get_templates():
    data = {'categories': {}}

    with open(args.template_config_path, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            category = row['type']
            if category not in data['categories']:
                data['categories'][category] = {
                    'name': category.capitalize() + ' styles',
                    'templates': []
                }

            image_url = url_for('get_image', filename=row['image_path'], _external=True)
            
            data['categories'][category]['templates'].append({
                'id': row['id'],
                'title': row['title'],
                'image_url': image_url, 
                'description': row['description'],
            })

    # Convert the categories dictionary to a list
    data['categories'] = list(data['categories'].values())

    return jsonify(data)


@app.route('/get_task_result/<task_id>')
@require_valid_uuid(task_db)
@limiter.limit("100 per minute")
def get_task_result(task_id):
    """
    Serve the result file for a given task_id.
    """
    # Use the new method to get the file path from the database
    file_path = task_db.get_file_path_by_task_id(task_id)

    if file_path:
        filename = os.path.basename(file_path)  # Extract the filename
        directory = os.path.dirname(file_path)  # Extract the directory path

        # Check if the file exists
        if os.path.isfile(file_path):
            return send_from_directory(directory, filename)
        else:
            return jsonify({"error": "File not found"}), 404
    else:
        return jsonify({"error": "Task not found or no result available"}), 404


@app.route('/upload_task', methods=['POST'])
@require_valid_uuid(task_db)
@limiter.limit("10 per minute") 
def upload_task():
    # Check if a video file is present in the request
    if 'video' not in request.files:
        return jsonify({'error': 'No video part in the request'}), 400
    file = request.files['video']
    
    # If the user does not select a file, the browser submits an empty file without a filename
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    data = request.get_json(force=True)
    
    token = data.get('token')
    objects = data.get('objects')
    config_text_box = data.get('config_text_box')
    task_type = data.get('task_type')
    
    task_id = str(uuid.uuid4())
    task_folder = blob_storage / task_id
    task_folder.mkdir(exist_ok=True)
    storage_video_path = str(task_folder / f'video.mp4')
    storage_json_path = str(task_folder / f'config.json')

    file.save(storage_video_path)

    with open(storage_json_path, 'w') as file:
        json.dump(
            json.loads(config_text_box), file, indent=4
        )

    # Insert task into the MongoDB database
    task_id = task_db.insert_task(
        objects=json.loads(objects),
        original_video_path=storage_video_path,
        config_path=storage_json_path,
        task_type=task_type,
        user_id=token,
    )

    result = {
        'message': f'Task {task_id} uploaded and saved successfully',
        'task_id': task_id,
    }
    return jsonify(result), 200


@app.route('/process_video_result', methods=['POST'])
@limiter.limit("10 per minute")
def process_video_result():
    task_id = request.form['task_id']
    video_file = request.files['video']
    task_dir = Path(args.blob_storage_path) / task_id
    task_dir.mkdir(exist_ok=True)
    video_path = os.path.join(str(task_dir), task_id + '_' + video_file.filename)
    
    # Save video in blob storage
    video_file.save(video_path)

    # Update task in MongoDB
    task_db.move_task_to_done(task_id, video_path)

    user_id = task_db.get_user_id_by_task_id(task_id)

    apns_token = task_db.get_user_db_property(user_id, 'apns_token')

    send_notification_to_popup(apns_token, f'process video result for task {task_id}')

    return jsonify({'message': 'Video processed and task updated successfully'}), 200


if __name__ == '__main__':
    app.run(host=args.flask_host, port=args.flask_port)