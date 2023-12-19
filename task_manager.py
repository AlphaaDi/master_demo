import argparse
import time
import json
import os
import requests

from sql_handler import *
from common import *

def parse_arguments():
    parser = argparse.ArgumentParser(description="Video Processing Service")
    parser.add_argument("--public_ip")
    parser.add_argument("--database", default='files/task_database.db', help="Path to the database file")
    parser.add_argument("--adresses_path", default='urls_path.txt')
    parser.add_argument("--worker_port", default='5000')
    parser.add_argument("--task_manager_port", default='6000')
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
    result_endpoint = f'http://{args.public_ip}:{args.task_manager_port}/process_video_result'
    try:
        task_db = TaskDatabase(args.database)
        while True:
            time.sleep(1)
            task = task_db.retrieve_oldest_wait_task()
            if not task:
                print('no task')
                continue
            print('task')
            ip_adresses = read_servers_from_file(args.adresses_path)
            for ip_adress in ip_adresses:
                url = f'http://{ip_adress}:{args.worker_port}'
                print('url ', url)
                response = requests.get(os.path.join(url, args.check_api_method))
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
