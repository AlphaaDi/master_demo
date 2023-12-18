#!/bin/bash

python task_server.py & 
python task_manager.py --public_ip "$1" &
python app.py &

# Prevent the script from exiting
wait