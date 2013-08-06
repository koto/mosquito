#!/usr/bin/env python
import socket
import threading
import SocketServer
from defer import *
import json
import re
import base64
import logging

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

    def handle(self):
        logging.debug("MosquitoRequestHandler.handle")
        self.server.last_client = self

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
                data=the_socket.recv(8192)
                if self.End in data:
                    total_data.append(data[:data.find(self.End)])
                    break
                total_data.append(data)
                if len(total_data)>1:
                    #check if end_of_data was split
                    last_pair=total_data[-2]+total_data[-1]
                    if self.End in last_pair:
                        total_data[-2]=last_pair[:last_pair.find(self.End)]
                        total_data.pop()
                        break
        return ''.join(total_data)

    def handle_hello(self, d):        
        logging.info("Mosquito client connected: %s", d)

    def handle_incoming_response(self, msg):
        logging.debug('Response to req #%d', msg['id'])
        self.server.call_defer(msg['id'], msg)

    def process_response(self, resp):
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
        self.server.add_defer(id, d)
        return d

    @inline_callbacks
    def _send_request_deferred(self, request):
        id = request.id
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


class MosquitoTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    """
        Mosquito TCP server, handling incoming connections in separate threads
    """

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass):
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
        self.defers = {}

    def add_defer(self, id, defer):
        self.defers[id] = defer
        logging.debug("Queue len: %d", len(self.defers))

    def call_defer(self, id, callback_params):
        if not id in self.defers:
            raise KeyError('fuuuuu!')
        d = self.defers[id]
        d.callback(callback_params)
        del(self.defers[id])

