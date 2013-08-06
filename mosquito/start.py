#!/usr/bin/env python
"""
    Startup file for mitmproxy-based HTTP(s) proxy forwarding all requests
    to Malaria TCP server
"""
from libmproxy import controller, proxy, flow
import os
import sys
from connector import MosquitoToMitmproxyConnector
import threading
import logging
from optparse import OptionParser

class OutOfBandMaster(flow.FlowMaster):
    """
    Forward all requests to code run in a separate thread
    """
    def __init__(self, server, state, request_handler):
        flow.FlowMaster.__init__(self, server, state)
        self.handler = request_handler

    def run(self):
        try:
            return flow.FlowMaster.run(self)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
            self.shutdown()

    def handle_request(self, r):
        t = threading.Thread(target=self.handler,args=[r])
        t.start()

def main(argv):    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    print "Mosquito by Krzysztof Kotowicz\n"
    usage = "Usage: %prog [options] <mosquito-port> <http-proxy-port>"
    parser = OptionParser(usage)
    parser.add_option('-i', '--proxy-iface', dest="proxy_iface", default="127.0.0.1",
                  help="HTTP Proxy interface [default: %default]")
    parser.add_option('-m', '--mosquito-iface', dest="mosquito_iface", default="127.0.0.1",
                  help="Mosquito interface [default: %default]")    

    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.print_help()
        parser.error("Incorrect number of arguments")
        


    config = proxy.ProxyConfig(
        cacert = os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")
    )

    http_proxy_port = int(args[1])
    server = proxy.ProxyServer(config, http_proxy_port, options.proxy_iface) # start HTTP proxy on port 4444
    logging.info("Started HTTP proxy server on http://%s:%d", server.address, server.port)

    mosquito_ip = options.mosquito_iface
    mosquito_port = int(args[0])
    
    connector = MosquitoToMitmproxyConnector(mosquito_ip, mosquito_port) # start Malaria server on given IP, port
    logging.info("Started Mosquito TCP server on %s:%d", connector.ip, connector.port)

    m = OutOfBandMaster(server, flow.State(), connector.handle_flow_request)
    m.run()

if __name__ == '__main__':    
    main(sys.argv)