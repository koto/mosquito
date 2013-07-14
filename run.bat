rem start whole mosquito toolkit in windows
rem requires python on path

start cmd /k "python http-server.py webroot 8000"
start cmd /k "cd externals\MalaRIA-Proxy\proxy-backend & java malaria.MalariaServer dummy 8081 4444"
start cmd /k "cd externals\websockify-exe & websockify.exe 8082 localhost:8081"
start http://localhost:8000/generate.html