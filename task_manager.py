import argparse
import time
import json
import os
import requests

from mongo_handler import TaskDatabase
from common import *

def parse_arguments():
    parser = argparse.ArgumentParser(description="Video Processing Service")
    parser.add_argument("--public_ip")
    parser.add_argument("--adresses_path", default='urls_path.txt')
    parser.add_argument("--worker_port", default='5000')
    parser.add_argument("--task_manager_port", default='6000')
    parser.add_argument("--process_api_method", default='process_video', help="API method for processing video")
    parser.add_argument("--check_api_method", default='get_worker_status', help="API method for checking worker status")
    parser.add_argument("--database_url", default='mongodb://localhost:27017/')
    parser.add_argument("--database_name", default='task_db')
    return parser.parse_args()


def send_video_processing_request(task, server_url, response_url):
    """
    Send a video processing request to the server.

    :param task: A dictionary containing task details.
    :param server_url: URL of the video processing server.
    :param response_url: URL to send the processed video to.
    """
    video_path = task['original_video_path']
    objects_info = json.dumps(task['objects'])  # Convert objects info to JSON string
    animate_config = json.dumps(json.load(
        open(task['config_path'], 'r')
    ))
    task_id = task['task_id']

    files = {'video': open(video_path, 'rb')}
    config_data = json.dumps({
        'objects': objects_info,
        'animate_config': animate_config,
        'response_url': response_url,
        'task_id': task_id,
    })
    data = {'config': config_data, 'response_url': response_url}
    response = requests.post(server_url, files=files, data=data)
    return response


if __name__ == "__main__":
    args = parse_arguments()
    result_endpoint = f'http://{args.public_ip}:{args.task_manager_port}/process_video_result'
    
    try:
        # Initialize TaskDatabase with MongoDB connection details
        task_db = TaskDatabase(args.database_url, args.database_name)

        while True:
            time.sleep(1)
            # Retrieve the oldest task from the 'waiting' collection
            task = task_db.retrieve_oldest_wait_task()
            if not task:
                print('No task')
                continue
            print('Task found:', task['task_id'])
            ip_addresses = read_servers_from_file(args.adresses_path)
            
            for ip_address in ip_addresses:
                url = f'http://{ip_address}:{args.worker_port}'
                print('Checking worker status at:', url)
                response = requests.get(os.path.join(url, args.check_api_method))
                status = json.loads(response.text)['status']
                
                if status == 'ready':
                    print(f"Sending task {task['task_id']} to {url} for {args.process_api_method}")
                    # Move task to 'in_progress' collection
                    task_db.move_task_to_in_progress(task['task_id'], ip_address) 
                    response = send_video_processing_request(
                        task, os.path.join(url, args.process_api_method),
                        result_endpoint
                    )
                    if response.status_code == 200:
                        print(f"Task {task['task_id']} is being processed.")
                    else:
                        print(f"Failed to start task {task['task_id']}.")

    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print(f"An error occurred: {e}")
