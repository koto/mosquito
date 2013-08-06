import SimpleHTTPServer
import SocketServer
import sys
import os
import logging
import threading

class MyTCPServer(SocketServer.TCPServer):
    allow_reuse_address = True

class MyHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_my_headers()

        SimpleHTTPServer.SimpleHTTPRequestHandler.end_headers(self)

    def send_my_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")

    def log_message(self, format, *args):
        logging.info("%s %s" % (self.client_address[0], format%args))


def start(webroot_dir, iface, port):
    Handler = MyHTTPRequestHandler

    os.chdir(webroot_dir)
    httpd = MyTCPServer((iface, port), Handler)
    logging.info("Starting HTTP server serving files under %s at port %d", webroot_dir, port)
    s_thread = threading.Thread(target=httpd.serve_forever)
    s_thread.daemon = True
    s_thread.start()
    return httpd

