from pymongo import MongoClient
from copy import deepcopy
import uuid
from datetime import datetime
import json
from enum import Enum


def parse_task(task_org):
    task = deepcopy(task_org)
    task['objects'] = json.loads(task['objects_json'])
    del task['objects_json']
    return task


class TaskStatus(Enum):
    WAITING = 'waiting_tasks'
    IN_PROGRESS = 'in_progress_tasks'
    DONE = 'done_tasks'


class TaskDatabase:
    def __init__(self, db_url, db_name):
        """
        Initialize the MongoDB connection and specify the collections.
        :param db_url: MongoDB connection URL.
        :param db_name: Database name.
        :param waiting_collection: Collection name for waiting tasks.
        :param in_progress_collection: Collection name for tasks in progress.
        :param done_collection: Collection name for done tasks.
        """
        self.client = MongoClient(db_url)
        self.db = self.client[db_name]
        self.collections = {
            TaskStatus.WAITING: self.db[TaskStatus.WAITING.value],
            TaskStatus.IN_PROGRESS: self.db[TaskStatus.IN_PROGRESS.value],
            TaskStatus.DONE: self.db[TaskStatus.DONE.value]
        }
        self.waiting = self.db[TaskStatus.WAITING.value]
        self.in_progress = self.db[TaskStatus.IN_PROGRESS.value]
        self.done = self.db[TaskStatus.DONE.value]
        self.user_db = self.db['user_db']


    def get_collection(self, status: TaskStatus):
        return self.collections[status]
    
    def store_link_with_uuid(self, uuid4, link):
        document = {
            "uuid": uuid4,
            "link": link,
            "created_at": datetime.now().isoformat(),
        }
        self.user_db.insert_one(document)
    
    def uuid_exists(self, uuid):
        return self.user_db.find_one({"uuid": uuid}) is not None
    
    def get_popup_link_by_user_id(self, user_id):
        document = self.user_db.find_one({"uuid": user_id})
        return document['link'] if document else None

    def insert_task(
            self, objects, user_id,
            original_video_path,
            config_path, task_id=None,
            file_path='', task_type='video'
        ):
        """
        Insert a new task into the waiting collection.
        :param objects: A dictionary of objects with keys like 'Object_1'.
        :param file_path: The file path to the result.
        :return: The unique task ID.
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        current_timestamp = datetime.now().isoformat()
        if type(objects) == str:
            objects_json = objects
        else:
            objects_json = json.dumps(objects)

        task_document = {
            "task_id": task_id,
            "timestamp": current_timestamp,
            "objects_json": objects_json,
            "original_video_path": original_video_path,
            "config_path": config_path,
            "file_path": file_path,
            "task_type": task_type,
            "user_id": user_id,
        }
        self.waiting.insert_one(task_document)
        return task_id

    def move_task_to_in_progress(self, task_id, machine_ip):
        """
        Move a task from waiting to in-progress collection and set the machine IP.
        :param task_id: The unique task ID.
        :param machine_ip: The IP address of the machine processing the task.
        """
        task = self.waiting.find_one_and_delete({"task_id": task_id})
        if task:
            task['machine_ip'] = machine_ip  # Set the machine IP address on the task document
            self.in_progress.insert_one(task)

    def move_task_to_done(self, task_id, file_path=''):
        """
        Move a task from in-progress to done collection.
        :param task_id: The unique task ID.
        :param file_path: The new file path for the task result.
        """
        task = self.in_progress.find_one_and_delete({"task_id": task_id})
        if task:
            task['file_path'] = file_path
            task['done_timestamp'] = datetime.now().isoformat()
            self.done.insert_one(task)

    def get_user_id_by_task_id(self, task_id):
        for status in [TaskStatus.DONE, TaskStatus.WAITING, TaskStatus.IN_PROGRESS]:
            collection = self.get_collection(status)
            task = collection.find_one({"task_id": task_id})
            if task:
                return task.get("user_id")  # Assuming 'user_id' is the field name
        return None


    def get_file_path_by_task_id(self, task_id):
        """
        Retrieve the file path for the result associated with a given task ID from the 'done' collection.

        :param task_id: The unique identifier of the task.
        :return: The file path of the task's result or None if not found.
        """
        task_document = self.done.find_one({"task_id": task_id})
        if task_document:
            return task_document.get("file_path")  # Assuming 'file_path' is the key for the file path
        else:
            return None


    def retrieve_oldest_wait_task(self):
        """
        Retrieve the oldest waiting task.
        :return: A dictionary containing task details or None if not found.
        """
        task = self.waiting.find_one(sort=[("timestamp", 1)])
        return parse_task(task) if task else None

    def retrieve_all_tasks(self, collection):
        """
        Retrieve all tasks from a specified collection.
        :param collection: The collection to retrieve tasks from.
        :return: A list of task dictionaries.
        """
        if collection == 'waiting':
            tasks = self.waiting.find(sort=[("timestamp", 1)])
        elif collection == 'in_progress':
            tasks = self.in_progress.find()
        elif collection == 'done':
            tasks = self.done.find()
        else:
            return None

        return [parse_task(task) for task in tasks] if tasks else None

    def close(self):
        self.client.close()

    def remove_task(self, task_id, collection):
        """
        Remove a task from a specified collection.
        :param task_id: The unique task ID.
        :param collection: The collection to remove the task from.
        """
        if collection == 'waiting':
            self.waiting.delete_one({"task_id": task_id})
        elif collection == 'in_progress':
            self.in_progress.delete_one({"task_id": task_id})
        elif collection == 'done':
            self.done.delete_one({"task_id": task_id})

    def remove_all_tasks(self, collection):
        """
        Remove all tasks from a specified collection.
        :param collection: The collection to remove all tasks from.
        """
        if collection == 'waiting':
            self.waiting.delete_many({})
        elif collection == 'in_progress':
            self.in_progress.delete_many({})
        elif collection == 'done':
            self.done.delete_many({})
