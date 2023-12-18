#!/bin/bash

python task_server.py --public_ip "$1" & 
python task_manager.py &
python app.py &

# Prevent the script from exiting
wait