#!/usr/bin/env python
"""
    Startup file for mitmproxy-based HTTP(s) proxy forwarding all requests
    to Malaria TCP server
"""

import os
import inspect
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def add_to_path(relative_dir):
    # realpath() with make your script run, even if you symlink it :)
    cmd_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]))
    add_path = os.path.join(cmd_folder, relative_dir)
    logging.debug("Adding %s to Python sys.path, add_path")

    if add_path not in sys.path:
       sys.path.insert(0, add_path)

add_to_path('../externals/mitmproxy')
add_to_path('../externals/websockify')

from libmproxy import controller, proxy, flow
from connector import MosquitoToMitmproxyConnector
import threading

from optparse import OptionParser
from multiprocessing import Process

class OutOfBandMaster(flow.FlowMaster):
    """
    Forward all requests to code run in a separate thread
    """
    def __init__(self, server, state, request_handler):
        flow.FlowMaster.__init__(self, server, state)
        self.handler = request_handler

    def run(self):
        logging.info("Listening to incoming connections")
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
    usage = "Usage: %prog [options] <mosquito-port> <http-proxy-port>"
    
    parser = OptionParser(usage=usage, version=version)

    parser.add_option('-a', '--attacker-iface', dest="attacker_iface", default="127.0.0.1",
                  help="Interface for services that attacker will connect to [default: %default]")
    parser.add_option('-p', '--public-iface', dest="public_iface", default="0.0.0.0",
                  help="Interface for services victim access [default: %default]")    
    parser.add_option('-w', '--ws ', dest="ws_port", type="int", 
                  help="Start WebSocket server on port WS_PORT")
    parser.add_option('--http', dest="http_port", type="int", 
                  help="Start HTTP server on port HTTP_PORT. Will serve files under webroot/")


    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.print_help()
        parser.error("Incorrect number of arguments")

    config = proxy.ProxyConfig(
        cacert = os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")
    )

    mosquito_port = int(args[0])
    http_proxy_port = int(args[1])

    server = proxy.ProxyServer(config, http_proxy_port, options.attacker_iface) # start HTTP proxy on port 4444
    logging.info("Started HTTP proxy server on http://%s:%d", server.address, server.port)

    mosquito_ip = options.public_iface

    connector = MosquitoToMitmproxyConnector(mosquito_ip, mosquito_port) # start Malaria server on given IP, port
    logging.info("Started Mosquito TCP server on %s:%d", connector.ip, connector.port)

    m = OutOfBandMaster(server, flow.State(), connector.handle_flow_request)

    ws_p = None
    http_s = None

    if options.ws_port:
        if sys.platform == 'win32':
            # start websockify exe
            pass
        else:    
            # start WebSocket server in separate port
            from websockify.websocketproxy import WebSocketProxy
            ws_server = WebSocketProxy(
                target_host = connector.ip,
                target_port = connector.port,
                listen_port = options.ws_port,
                listen_host = connector.ip,
                #web = 'webroot',
                verbose = True,
                daemon= False
            )
            #ws_server.start_server()
            ws_p = Process(target=ws_server.start_server , args=[])
            ws_p.start()
            logging.info("Started WebSocket server on %s:%d", ws_server.listen_host, ws_server.listen_port)

    if options.http_port:
        import http_server
        http_s = http_server.start('webroot', connector.ip, options.http_port)
        #t = threading.Thread(target=http_server.start, args=['webroot', options.http_port])
        #t.start()

    m.run()
    #t2 = threading.Thread(target=start_ws , args=[ws_server])
    logging.info("Exiting...")


    if ws_p:
        ws_p.terminate()
    if http_s:
        http_s.shutdown()

if __name__ == '__main__':    
    main(sys.argv)