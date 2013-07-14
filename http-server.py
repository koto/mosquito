#!/usr/bin/env python
import SimpleHTTPServer
import SocketServer
import sys
import os

class MyHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_my_headers()

        SimpleHTTPServer.SimpleHTTPRequestHandler.end_headers(self)

    def send_my_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")

DIR = sys.argv[1]
PORT = int(sys.argv[2])

Handler = MyHTTPRequestHandler

os.chdir(DIR)
httpd = SocketServer.TCPServer(("", PORT), Handler)

print "Starting HTTP server serving files under %s at port %d" % (DIR, PORT)

httpd.serve_forever()