#!/bin/bash

python task_server.py & 
python task_manager.py --public_ip "$1" --task_manager_port "$2"&
python app.py --port "$3" &

# Prevent the script from exiting
wait