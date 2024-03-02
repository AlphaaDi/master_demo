import argparse
from datetime import datetime, timedelta
import os
from mongo_handler import TaskDatabase  # Ensure this import works for your project structure

# USE: 0 2 * * * /usr/bin/python3 /path/to/your_script.py

# Setup argparse
parser = argparse.ArgumentParser(description="Delete videos stored for more than a specified number of days.")
parser.add_argument('--db_url', default='mongodb://localhost:27017/', help='MongoDB connection URL.')
parser.add_argument('--db_name', default='mydatabase', help='MongoDB database name.')
parser.add_argument('--days', type=int, default=7, help='Number of days after which videos should be deleted.')
args = parser.parse_args()

def delete_old_videos(db_url, db_name, days):
    task_db = TaskDatabase(db_url, db_name)
    cutoff_date = datetime.now() - timedelta(days=days)
    cutoff_timestamp = cutoff_date.isoformat()
    old_tasks = task_db.done.find({"done_timestamp": {"$lt": cutoff_timestamp}})
    for task in old_tasks:
        file_path = task.get('file_path')
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Deleted {file_path}")
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
        task_db.done.delete_one({"_id": task["_id"]})

if __name__ == "__main__":
    delete_old_videos(args.db_url, args.db_name, args.days)
