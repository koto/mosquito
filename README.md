Mosquito
========
by [Krzysztof Kotowicz](http://blog.kotowicz.net) - kkotowicz@gmail.com

Mosquito is a **Google Chrome extension exploitation tool** allowing an attacker to leverage XSS found in extension content script to issue arbitrary cross-domain HTTP requests with victim browser (and victim cookies).

With this tool attacker can exploit content-script XSS vulnerabilities in extensions based on manifest v1 and v2.

Introduction
-----------
Mosquito is a tool to exploit common XSS vulnerabilities in Google Chrome extensions. Chrome extensions can often submit unrestricted XHR requests to any domain, making them a perfect tool to abuse. It allows the attacker to easily generate XSS payloads that setup peristent connection from victim browsers to given Mosquito server. Mosquito server in turn allows the attacker to instrument victim's XMLHttpRequest object via setting up a HTTP Proxy. 

Upon successful exploitation attacker can access websites through victim's browser and easily hijack user sessions (sort of like [XSS-Proxy](http://xss-proxy.sourceforge.net/)). If exploited Google Chrome extension had wildcard URL patterns (and lots of them do), attacker can also navigate to sites outside exploited origin (e.g. Gmail domain, intranet addresses etc.). Think of it as *XSS in Chrome Extesion to HTTP Proxy bridge*

Mosquito was originally based on [MalaRIA](http://erlend.oftedal.no/blog/?blogid=107), a proof-of-concept made by [Erlend Oftedal](http://erlend.oftedal.no) demonstrating a proxy abusing unrestricted cross domain policies and it is heavily influenced by its architecture. However lots of changes have been introduced, and the project is now fully Python-based, multi-threaded, HTTPS compatible thanks to [mitmproxy](http://mitmproxy.org), and [WebSockets](http://dev.w3.org/html5/websockets/) protocol is used for transport.


Requirements
------------

  * Python 2.x (http://www.python.org/download/)
  * [PyOpenSSL](https://pypi.python.org/pypi/pyOpenSSL)
  * [pyasn1](https://pypi.python.org/pypi/pyasn1)
  * [flask](https://pypi.python.org/pypi/flask)


  * a confirmed content-script XSS vulnerability in Google Chrome extension

Installation
------------

  1. Clone the repository

  		$ git clone git://github.com/koto/mosquito.git
  		$ cd mosquito
  		$ git submodule update --init --recursive

  2. Install dependencies

      $ easy_install pyopenssl
      $ easy_install pyasn1
      $ easy_install flask

Usage
-----

  1. Find XSS vulnerability in Google Chrome extension

     Scan, review the code etc. See e.g. [I'm in your browser, pwning your stuff](https://www.hackinparis.com/talk-krzysztof-kotowicz) presentation or [my blog](http://blog.kotowicz.net/search/label/chrome)

  2. Do the [dance](http://www.youtube.com/watch?v=qkthxBsIeGQ)!

  3. Launch Mosquito server

	    $ python mosquito/start.py 8082 4444 --http 8000
    
     This will launch Mosquito server with HTTP proxy on `127.0.0.1:4444` and Mosquito WebSocket proxy on `*:8082`.
     Additionally `webroot/` dir will be served over `*:8000`

  4. Generate mosquito hook at `http://localhost:8000/generate.html`. Victim MUST be able
     to connect to `base_url` HTTP server and to `ws_host:ws_port` WebSocket server.

  5. Inject hook into extension installed in victim's browser

  6. Use `localhost:4444` as your HTTP proxy. You now can use Burp or your browser to send
     requests and receive responses.


License
-------
Mosquito - Chrome Extension exploitation tool Copyright (C) 2013 Krzysztof Kotowicz - http://blog.kotowicz.net

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see http://www.gnu.org/licenses/.


See also
--------
  * [cors-proxy-browser](http://koto.github.io/cors-proxy-browser/)
  * [mitmproxy](http://mitmproxy.org/)
  * [websockify](https://github.com/kanaka/websockify)