Mosquito
========

Chrome Extension exploitation tool

This is a chrome extension exploitation tool allowing an attacker to lerverage XSS found
in extension content script to issue arbitrary cross-domain HTTP requests with victim browser (and victim cookies).

This tool allows to abuse content-script XSS vulnerabilities in extensions based on manifest v1 and v2.

Introduction
-----------
Mosquito relies on MalaRIA, a proof-of-concept made by [Erlend Oftedal](http://erlend.oftedal.no) demonstrating a proxy abusing unrestricted cross domain policies.
MalaRIA is made of two parts: the Flash/Silverlight connector(s) launched on a victim browser, and a Java-based server. Victim visits the page with the connector, it establishes connection with server and from now on victim's browser can be used as a proxy by the attacker (Flash/Sliverlight processes the requests from the MalaRIA server and sends the responses back).Attacker controls MalaRIA in his browser by simply pointing to the HTTP proxy opened by MalaRIA.

Originally MalaRIA demonstrated that permissive crossdomain.xml files are bad (because attacker can read it e.g. via the MalaRIA proxy) and used Flash files to issuerequests.

Mosquito instead of using FLash files leverages common XSS vulnerabilities in Chrome extensions. Chrome extensions can often submit urestricted XHR requests to any domain, making them a perfect tool to abuse.

To communicate with MalaRIA I use [WebSockets](http://dev.w3.org/html5/websockets/) protocol (because I don't have raw flash/silverlight sockets available).


Requirements
------------

    * [malaRIA](https://github.com/koto/MalaRIA-Proxy) (JDK to compile)
    * [websockify](https://github.com/kanaka/websockify) (Python and some libs to run it)>
    * a confirmed content-script XSS vulnerability in Google Chrome extension

Installation
------------

    1. Clone the repository
    2. Compile MalaRIA
        $ cd externals/MalaRIA-Proxy/proxy-backend
        $ javac malaria/*.java
    3. Compile websockify
        https://github.com/kanaka/websockify

       Windows builds are already compiled in externals/websockify-exe

Usage
-----

	1. Serve webroot\ directory via HTTP server
		e.g.
		$ cd webroot
		$ python -m SimpleHTTPServer

    2. Launch MalaRIA server

	    $ cd externals/MalaRIA-Proxy/proxy-backend
	    $ sudo java malaria.MalariaServer dummy 8081 4444
	    # launch malaria server with HTTP proxy on 4444 and connector proxy on 8081

	3. Launch Websockify proxy
	    [2nd shell]
	    $ cd externals/websockify
	    $ ./websockify 8082 localhost:8081
	    # forward WebSocket connection from TCP:8082 via MalaRIA running on 8081

	    or

	    $ cd externals\websockify-exe
	    $ websockify.exe 8082 localhost:8081

	4. Find XSS vulnerability in Google Chrome extension

	5. Generate mosquito hook at http://localhost:8000/generate.html. Victim MUST be able to connect to base_url HTTP server and to ws_host:ws_port WebSocket server.

	6. Inject hook into extension

    7. Use localhost:4444 as your HTTP proxy. You now can use Burp or your browser to send
    requests and receive reqponses.
