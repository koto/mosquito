#!/bin/bash
# start whole mosquito toolkit in Ubuntu based systems
gnome-terminal -t Mosquito -x sh -c "python mosquito/start.py 8082 4444 --http 8000"
xdg-open http://localhost:8000/generate.html
