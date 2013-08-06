from server import MosquitoTCPServer, MosquitoRequestHandler, MosquitoRequest
import threading
from libmproxy import flow
from netlib.odict import ODictCaseless
import logging

class MosquitoToMitmproxyConnector:
    """
        Class used to get HTTP(s) requests from mitmproxy codebase and proxy them
        via Mosquito TCP server.
    """
    
    def __init__(self, host, port):
        """
            Starts Mosquito TCP server
        """
        self.server = MosquitoTCPServer((host, port), MosquitoRequestHandler)
        ip, port = self.server.server_address
        self.ip = ip
        self.port = port

        # Start a thread with the server -- that thread will then start one
        # more thread for each request
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        # Exit the server thread when the main thread terminates
        self.server_thread.daemon = True
        self.server_thread.start()

    def build_mosquito_request(self, r):
        flatheaders = []
        for i in r.headers.keys():
            flatheaders.append([i, "".join(r.headers.get(i))])
        
        logging.info("%s %s", r.method, r.get_url())

        m_r = MosquitoRequest('xhr',{
            'url': r.get_url(), 
            'method': r.method, 
            'headers': flatheaders,
            'body': r.content,
        })
        return m_r        
    
    def build_flow_response(self, req, status, status_text, headers, body):
        headers = ODictCaseless()
        for k,v in headers:
            headers[k] = v
        logging.info("%d %s (%d) [%s %s]: ", status, status_text, len(body), req.method, req.get_url())
        resp = flow.Response(req,
                [1,1],
                status, status_text,
                headers,
                body,
                None)
        return resp

    def handle_flow_request(self, r):
        m_req = self.build_mosquito_request(r)

        status, statusText, headers, body = self.server.last_client.send_request_and_wait(m_req)
        m_resp = self.build_flow_response(r, status, statusText, headers, body)
        r.reply(m_resp)

    def handle_wsgi_request(self, environ, start_response):
        url = environ['wsgi.url_scheme'] + "://" + environ['HTTP_HOST'] + ':' + environ['SERVER_PORT'] + environ['PATH_INFO']
        if environ['QUERY_STRING']:
            url += '?' + environ['QUERY_STRING']

        hdrs = []

        for k, v in environ.iteritems():
            if k.startswith('HTTP_'):
                hdrs.append([k[5:].capitalize().replace('_', '-'), v])
        
        if environ['CONTENT_TYPE']:
            hdrs.append(['Content-Type', environ['CONTENT_TYPE']])

        r = MosquitoRequest('xhr',{
            'url': url, 
            'method': environ['REQUEST_METHOD'], 
            'headers': hdrs,
            'body': environ['wsgi.input'].read(),
        })

        status, status_text, headers, body = self.server.last_client.send_request_and_wait(r)
        status = "%d %s" % (resp['data']['status'], resp['data']['statusText'])
        start_response(status, headers)
        logging.debug("end wsgi")
        return [body]
