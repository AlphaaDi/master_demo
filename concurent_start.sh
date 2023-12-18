#!/bin/bash

python task_server.py &
python task_manager.py &
python app.py &

# Prevent the script from exiting
wait