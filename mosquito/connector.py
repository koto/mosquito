from server import MosquitoTCPServer, MosquitoRequestHandler, MosquitoRequest
import threading

class MosquitoConnector:
    def __init__(self, host, port):
        self.server = MosquitoTCPServer((host, port), MosquitoRequestHandler)
        ip, port = self.server.server_address

        # Start a thread with the server -- that thread will then start one
        # more thread for each request
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        # Exit the server thread when the main thread terminates
        self.server_thread.daemon = True
        self.server_thread.start()

    def shutdown(self):
        pass

    def handle_wsgi_request(self, environ, start_response):
        url = environ['wsgi.url_scheme'] + "://" + environ['HTTP_HOST'] + ':' + environ['SERVER_PORT'] + environ['PATH_INFO']
        if environ['QUERY_STRING']:
            url += '?' + environ['QUERY_STRING']

        hdrs = []
        print environ
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

        status, headers, body = self.server.last_client.send_request_and_wait(r)
        #print headers, body
        start_response(status, headers)
        print "end wsgi"
        return [body]
