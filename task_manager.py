import argparse
import time
import json
import os
import requests

from sql_handler import *
from common import *

def parse_arguments():
    parser = argparse.ArgumentParser(description="Video Processing Service")
    parser.add_argument("--database", default='files/task_database.db', help="Path to the database file")
    parser.add_argument("--urls_path", default='urls_path.json')
    parser.add_argument("--result_endpoint", default='http://10.9.236.73:6000/process_video_result')
    parser.add_argument("--process_api_method", default='process_video', help="API method for processing video")
    parser.add_argument("--check_api_method", default='get_worker_status', help="API method for checking worker status")
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
    urls_file = args.urls_path
    try:
        task_db = TaskDatabase(args.database)
        while True:
            time.sleep(1)
            task = task_db.retrieve_oldest_wait_task()
            if not task:
                continue
            urls = read_worker_urls(args.urls_path)
            for url in urls:
                try:
                    response = requests.get(os.path.join(url, args.check_api_method))
                except BaseException as e:
                    print(e)
                    continue
                status = json.loads(response.text)['status']
                if status == 'ready':
                    print(f"Send task {task['task_id']} to {url} for {args.process_api_method}")
                    task_db.update_task_status(task['task_id'], status='processing')
                    response = send_video_processing_request(
                        task, os.path.join(url, args.process_api_method),
                        args.result_endpoint
                    )
    except KeyboardInterrupt:
        print("Shutting down...")
    # except BaseException as e:
    #     print(e)
