rem start whole mosquito toolkit in windows
rem requires python on path

start cmd /k "python mosquito/start.py 8082 4444 --http 8000"
start http://localhost:8000/generate.html
