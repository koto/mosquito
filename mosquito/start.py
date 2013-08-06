#!/usr/bin/env python
"""
    Startup file for mitmproxy-based HTTP(s) proxy forwarding all requests
    to Malaria TCP server
"""

import os
import inspect
import logging
import sys
from subprocess import call

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

script_dir = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]))
def add_to_path(relative_dir):
    # realpath() with make your script run, even if you symlink it :)
    add_path = os.path.join(script_dir, relative_dir)
    logging.debug("Adding %s to Python sys.path, add_path")

    if add_path not in sys.path:
       sys.path.insert(0, add_path)

add_to_path('../externals/mitmproxy')
add_to_path('../externals/netlib')
add_to_path('../externals/websockify')

from libmproxy import controller, proxy, flow
from connector import MosquitoToMitmproxyConnector
import threading

from optparse import OptionParser
from multiprocessing import Process

def start_ws_exe(script_dir, ws_port, ip, port):
    logging.info("Starting websockify.exe binary")
    call([os.path.join(script_dir, "..\externals\websockify-exe\websockify.exe"), str(ws_port), ip+':'+str(port)])

class OutOfBandMaster(flow.FlowMaster):
    """
    Forward all requests to code run in a separate thread
    """
    def __init__(self, server, state, request_handler):
        flow.FlowMaster.__init__(self, server, state)
        self.handler = request_handler

    def run(self):
        logging.info("Listening for incoming connections")
        try:
            return flow.FlowMaster.run(self)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
            self.shutdown()

    def handle_request(self, r):
        t = threading.Thread(target=self.handler,args=[r])
        t.start()

def main(argv):

    version = "1.0"
    usage = "Usage: %prog [options] <mosquito-websockets-port> <http-proxy-port>"
    
    parser = OptionParser(usage=usage, version=version)

    parser.add_option('-a', '--attacker-iface', dest="attacker_iface", default="127.0.0.1",
                  help="Interface for services that attacker will connect to [default: %default]")
    parser.add_option('-p', '--public-iface', dest="public_iface", default="0.0.0.0",
                  help="Interface for services victim access [default: %default]")
    parser.add_option('--http', dest="http_port", type="int", 
                  help="Start HTTP server on port HTTP_PORT. Will serve files under webroot/")
    parser.add_option('-w', '--webroot', dest="webroot", default="webroot",
                  help="Directory to serve files from [default: %default]")
    

    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.print_help()
        parser.error("Incorrect number of arguments")

    config = proxy.ProxyConfig(
        cacert = os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")
    )
    if not os.path.exists(config.cacert):
        logging.info("Generating SSL CA certificate")
        import netlib
        netlib.certutils.dummy_ca(config.cacert)

    logging.info("Install CA cert %s in your browser for best experience", config.cacert)

    ws_port = int(args[0])
    http_proxy_port = int(args[1])

    server = proxy.ProxyServer(config, http_proxy_port, options.attacker_iface) # start HTTP proxy on port 4444
    logging.info("Started HTTP proxy server on http://%s:%d", server.address, server.port)

    mosquito_ip = '127.0.0.1'

    connector = MosquitoToMitmproxyConnector(mosquito_ip, 0) # start Malaria server on given IP, any high port
    logging.info("Started Mosquito TCP server on %s:%d", connector.ip, connector.port)

    m = OutOfBandMaster(server, flow.State(), connector.handle_flow_request)

    ws_p = None
    http_s = None

    if ws_port:
        if sys.platform == 'win32':
            # start websockify.exe
            ws_p = Process(target=start_ws_exe, args=[script_dir, ws_port, connector.ip, connector.port])
            ws_p.start()
        else:    
            # start WebSocket server in separate port
            from websockify.websocketproxy import WebSocketProxy
            ws_server = WebSocketProxy(
                target_host = connector.ip,
                target_port = connector.port,
                listen_port = ws_port,
                listen_host = options.public_iface,
                daemon= False
            )
            ws_p = Process(target=ws_server.start_server , args=[])
            ws_p.start()
            logging.info("Started WebSocket server on ws://%s:%d", ws_server.listen_host, ws_server.listen_port)

    if options.http_port:
        import http_server
        http_s = http_server.start(options.webroot, options.public_iface, options.http_port)

    m.run()
    logging.info("Exiting...")


    if ws_p:
        ws_p.terminate()
    if http_s:
        http_s.shutdown()

if __name__ == '__main__':
    main(sys.argv)