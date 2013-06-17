#!/bin/bash
# start whole mosquito toolkit in Ubuntu based systems
gnome-terminal -t SimpleHTTPServer -x sh -c "cd webroot && python -m SimpleHTTPServer"
gnome-terminal -t MalaRIA -x sh -c "cd externals/MalaRIA-Proxy/proxy-backend && java malaria.MalariaServer dummy 8081 4444"
gnome-terminal -t websockify -x sh -c "cd externals/websockify && python ./websockify.py 8082 localhost:8081"
xdg-open http://localhost:8000/generate.html