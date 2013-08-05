#!/usr/bin/env python
"""
This example builds on mitmproxy's base proxying infrastructure to
implement functionality similar to the "sticky cookies" option. This is at
a lower level than the Flow mechanism, so we're dealing directly with
request and response objects.
"""
from libmproxy import controller, proxy, flow
import os
import sys
from connector import MosquitoConnector
import threading


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
            print "shutdown"
            self.shutdown()

    def handle_request(self, r):
        t = threading.Thread(target=self.handler,args=[r])
        t.start()


# class MalariaProxyServer(proxy.ProxyServer):
#     def __init__(self, config, port, address=''):    
#         proxy.ProxyServer.__init__(self, config, port, address)

#         class DefaultAppRegistry(proxy.AppRegistry):
#             """
#                 WSGI Application registry supporting setting a default app handling all requests
#             """
            
#             def __init__(self, apps = {}):
#                 self.apps = apps
#                 self.app_default = None

#             def add_default(self, app):
#                 """
#                     Add a default WSGI application
#                 """
#                 self.app_default = app

#             def get(self, request):
#                 """
#                     Returns application matched to the host/port or a default app
#                 """
#                 f = proxy.AppRegistry.get(self,request)
#                 if f:
#                     return f
#                 if self.app_default:           
#                     return wsgi.WSGIAdaptor(self.app_default, request.host, request.port, "")

#         self.apps = DefaultAppRegistry(self.apps.apps)

    # def handle_connection(self, request, client_address):
    #     h = MalariaProxyHandler(self.config, request, client_address, self, self.channel, self.server_version)
    #     h.handle()
    #     h.finish()

# class MalariaProxyHandler(proxy.ProxyHandler):
#     def get_server_connection(self, cc, scheme, host, port, sni):
#         print host
#         return proxy.ProxyHandler.get_server_connection(self, cc, scheme, host, port, sni)

def main(argv):

    config = proxy.ProxyConfig(
        cacert = os.path.expanduser("~/.mitmproxy/mitmproxy-ca.pem")
    )

    server = proxy.ProxyServer(config, 4444)

    # all request to proxy should be handled by mosquito.Connector wsgi app
    connector = MosquitoConnector('127.0.0.1', 8081)
    # server.apps.add_default(connector.handle_wsgi_request)

    m = OutOfBandMaster(server, flow.State(), connector.handle_flow_request)
    m.run()
    #connector.shutdown()

if __name__ == '__main__':
    main(sys.argv)