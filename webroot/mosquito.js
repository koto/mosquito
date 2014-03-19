/**
 * mosquito = silent, self setup malaria
 * @author Krzysztof Kotowicz kkotowicz@gmail.com
 * @see http://blog.kotowicz.net
 * @see https://github.com/koto/mosquito
 **/
(function(d) {

    SEPARATOR = "\n:WSEP:\n";
    // to be removed
    function log(m) {
        console.debug(m);
    }

    function bindf(scope, fn) {
        return function() {
            fn.apply(scope, arguments);
        };
    }

    if (!navigator.userAgent.match(/hrome/)) {
        log('Works in Chrome only, sorry');
        return;
    }

    // shims
    function ReconnectingWebSocket(a,prot){function f(g){c=new WebSocket(a,prot);var h=c;var i=setTimeout(function(){e=true;h.close();e=false},b.timeoutInterval);c.onopen=function(c){clearTimeout(i);b.readyState=WebSocket.OPEN;g=false;b.onopen(c)};c.onclose=function(h){clearTimeout(i);c=null;if(d){b.readyState=WebSocket.CLOSED;b.onclose(h)}else{b.readyState=WebSocket.CONNECTING;if(!g&&!e){b.onclose(h)}setTimeout(function(){f(true)},b.reconnectInterval)}};c.onmessage=function(c){b.onmessage(c)};c.onerror=function(c){b.onerror(c)}}this.debug=false;this.reconnectInterval=1e3;this.timeoutInterval=2e3;var b=this;var c;var d=false;var e=false;this.url=a;this.prot=prot;this.readyState=WebSocket.CONNECTING;this.URL=a;this.onopen=function(a){};this.onclose=function(a){};this.onmessage=function(a){};this.onerror=function(a){};f(a);this.send=function(d){if(c){return c.send(d)}else{throw"INVALID_STATE_ERR : Pausing to reconnect websocket"}};this.close=function(){if(c){d=true;c.close()}};this.refresh=function(){if(c){c.close()}}};

    function parseQuery(query, def) {
           var Params = def || {};
           if (!query) { return Params; } // return empty object
           var Pairs = query.split(/[;&]/);
           for (var i = 0; i < Pairs.length; i++) {
              var KeyVal = Pairs[i].split('=');
              if (!KeyVal || KeyVal.length != 2) {continue;}
              var key = unescape(KeyVal[0]);
              var val = unescape(KeyVal[1]);
              val = val.replace(/\+/g, ' ');
              Params[key] = val;
           }
           return Params;
    }

    var params = (typeof mosquito_params !== "undefined" ? mosquito_params : {});
    var scriptUrl = '';
    var scripts = d.getElementsByTagName('script');
    for (var i = 0; i < scripts.length ; i++) {
        if (scripts[i].src.match(/mosquito\.js/)) {
            var tmp = document.createElement('a');
            tmp.href = scripts[i].src.replace(/\?.*/, '');
            scriptUrl = tmp.href;

            params = parseQuery(scripts[i].src.replace(/^[^\?]+\??/,''), params);
            log(params);
        }
    }

// core stuff - this atually makes the cross origin connections
    var Connector = (function() {
        return {
            factory: function(type) {
                //console.log('Trying ' + type);
                switch (type) {
                case 'cors':
                case 'cors-withcredentials':
                    return (typeof XDomainRequest !== 'undefined' ? new XDomainRequest() : new XMLHttpRequest());
                case 'flash':
                    if (location.protocol == 'file:')
                        throw "Flash will only load from a http[s], not from file://";
                    if (typeof CrossXHR === 'undefined')
                        throw "Flash is not loaded!";

                    return new CrossXHR();
                }
                throw 'Unsupported request processor type: ' + type;
            },

            sendRequest: function(event, types, url, method, body, headers, xtra) {
                log("Sending XHR request to " + url);
                var current_type = types.shift();
                var xhr = this.factory(current_type);
                // get first available type
                xhr.open(method, url, true);
                xhr.responseType = 'arraybuffer';
                if (current_type === 'cors-withcredentials') {
                    xhr.withCredentials = 'true';
                }
                if (typeof xhr.overrideMimeType !== "undefined") {
                //    xhr.overrideMimeType('text/plain; charset=x-user-defined');
                }

                xhr._xtra = xtra;
                xhr._url = url;
                xhr._method = method;
                xhr._types_left = types;
                xhr._type = current_type;
                for (var i = 0; i < headers.length; i++) {
                    try {
                        xhr.setRequestHeader(headers[i][0], headers[i][1]);
                    } catch (e) {}
                }
                xhr._body = body;
                var self = this;
                xhr.onreadystatechange = function(e) {
                    self.handleResponse(e, this);
                };

                xhr._start_time = new Date().getTime();
                xhr.send(body);
            },

            fallback: function(xhr) {
                this.sendRequest(null, xhr._types_left, xhr._url, xhr._method, xhr._body);
            },

            handleSuccess: function(event, xhr) {
                xhr._end_time = new Date().getTime();
                jQuery('html').trigger('response-load', [xhr.response, xhr]);
            },

            handleError: function(event, xhr) {
                log('error');
                if (xhr._types_left.length == 0) {
                    jQuery('html').trigger('response-error', xhr);
                } else {
                    this.fallback(xhr);
                }
            },

            handleResponse: function(event, xhr) {
                if (xhr.readyState === 4) {
                    if (xhr.status == 200) {
                        this.handleSuccess(event, xhr);
                    } else {
                        this.handleError(event, xhr);
                    }
                }
            },

            alertError: function(xhr) {
                if (xhr instanceof jQuery.Event) {
                    xhr = arguments[1];
                }
                alert("Could not load " + xhr._url + (xhr.statusText ? " (" + xhr.statusText + ")": "")
                      + "\nUsed methods: " + JSON.stringify(Preferences.get('type')));
            }
        }
    })();

    var p;

    function requestXhr(request) {
        var use_methods = ['cors-withcredentials'];
        // USE ['flash'] instead to use flash only, see browser.html
        jQuery('html').trigger('request-start', [ 
            use_methods, 
            request[2].url, 
            request[2].method, 
            request[2].body,
            request[2].headers,
            request[0] // id
        ]);
    }

    function parseRequestFromProxy(req) {
        log("Received: " + req);
        var reqobj;
        try {
            reqobj = JSON.parse(req);
        } catch (e) {
            if (req.indexOf('][') !== -1) { // multiple reqests sent in one message
                // extract [req][req][req] requests manually 
                reqs = req.split('][');
                for (var i = 0; i < reqs.length; i++) {
                    if (i > 0) {
                        var reqstr = '[';
                    } else {
                        reqstr = ''
                    };

                    reqstr += reqs[i] + ((i == reqs.length -1) ? '' : ']');

                    reqobj = JSON.parse(reqstr);
                    processRequestObject(reqobj);
                }
                return;
            }

            throw e;
        }
        processRequestObject(reqobj);
    }

    function processRequestObject(reqobj) {
        if (reqobj[1] == 'xhr') {
            requestXhr(reqobj);
        }
    }

    var readByteAt = function(i, fileContents){
        return fileContents.charCodeAt(i) & 0xff;
    };

    function returnResponseToProxy(d) {

        if (d.response.bytes) {
            delete d.response.body;
        }

        var r = {
            id: d.id,
            data: d.response,
            result: d.result
        }

        log('sending response to req #' + r.id)
        p.send(JSON.stringify(r) + SEPARATOR);
        return;

    }

    function launchMosquitoConnector() {
        try {
            p = new ReconnectingWebSocket('ws://' + params.ws_host + ':' + params.ws_port, 'binary');
        } catch (e) {
            log("Cannot connect to WebSocket server:" + e.message);
        }

        if (p) {
            p.onopen = function() {
                log("Connected to Mosquito at " + p.URL);
                p.send(JSON.stringify({
                    hello: 'Hello mosquito!',
                    url: d.location.href
                }) + SEPARATOR);
                p.onmessage = function(e) {
                    var fr = new FileReader;
                    fr.onload = function(e) {
                        parseRequestFromProxy(e.target.result);
                    };
                    console.log(e.data);
                    fr.readAsBinaryString(e.data);
                    console.log('read success');
                };
            };
            p.onerror = function() {
                log("Cannot connect to WebSocket server at " + p.URL);
            };
        }
    }

    var remoteController = {
        source: null,
        // remote communication
        receive: function(event) {
            var reqparams;
            try {
                reqparams = JSON.parse(event.data);
                this.source = event.source;
                if (reqparams.length == 4) {
                    // types, url, method, body
                    jQuery('html').trigger('request-start', reqparams);
                }
            } catch(e) {}
        },
        prepareResult: function(xhr) {
            return {
                result: undefined,
                duration: xhr._end_time - xhr._start_time,
                id: xhr._xtra,
                response: {
                    body: undefined,
                    headers: undefined,
                    status: xhr.status,
                    statusText: xhr.statusText,
                    time: xhr._end_time
                },
                request: {
                    url: xhr._url,
                    method: xhr._method,
                    body: xhr._body,
                    type: xhr._type,
                    types_left: xhr._types_left,
                    time: xhr._start_time
                }
            }
        },
        str2ab: function(str) {
            var buf = new ArrayBuffer(str.length);
            var bufView = new Uint8Array(buf);
            for (var i=0, strLen=str.length; i<strLen; i++) {
                bufView[i] = str.charCodeAt(i);
            }
            return buf;
        },     
        sendError: function(event, xhr) {
            var obj = this.prepareResult(xhr);
            obj.result = 'error';
            obj.response.status = 500;
            obj.response.statusText = "Mosquito client error"
            obj.response.body = base64ArrayBuffer(this.str2ab("Mosquito client error (maybe no x-domain permissions?)"))
            returnResponseToProxy(obj);
        },
        sendResponse: function(event, text, xhr) {
            var obj = this.prepareResult(xhr);
            obj.result = 'ok';
            obj.response.body = base64ArrayBuffer(text);
            //obj.response.bytes = Array.prototype.map.call(text, this.byteValue);
            obj.response.headers = (xhr.getAllResponseHeaders ? xhr.getAllResponseHeaders() : null);
            returnResponseToProxy(obj);
        },
        byteValue: function(x) {
            return x.charCodeAt(0) & 0xff;
        }
    }

    function base64ArrayBuffer(arrayBuffer) {
      var base64    = ''
      var encodings = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
     
      var bytes         = new Uint8Array(arrayBuffer)
      var byteLength    = bytes.byteLength
      var byteRemainder = byteLength % 3
      var mainLength    = byteLength - byteRemainder
     
      var a, b, c, d
      var chunk
     
      // Main loop deals with bytes in chunks of 3
      for (var i = 0; i < mainLength; i = i + 3) {
        // Combine the three bytes into a single integer
        chunk = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2]
     
        // Use bitmasks to extract 6-bit segments from the triplet
        a = (chunk & 16515072) >> 18 // 16515072 = (2^6 - 1) << 18
        b = (chunk & 258048)   >> 12 // 258048   = (2^6 - 1) << 12
        c = (chunk & 4032)     >>  6 // 4032     = (2^6 - 1) << 6
        d = chunk & 63               // 63       = 2^6 - 1
     
        // Convert the raw binary segments to the appropriate ASCII encoding
        base64 += encodings[a] + encodings[b] + encodings[c] + encodings[d]
      }
     
      // Deal with the remaining bytes and padding
      if (byteRemainder == 1) {
        chunk = bytes[mainLength]
     
        a = (chunk & 252) >> 2 // 252 = (2^6 - 1) << 2
     
        // Set the 4 least significant bits to zero
        b = (chunk & 3)   << 4 // 3   = 2^2 - 1
     
        base64 += encodings[a] + encodings[b] + '=='
      } else if (byteRemainder == 2) {
        chunk = (bytes[mainLength] << 8) | bytes[mainLength + 1]
     
        a = (chunk & 64512) >> 10 // 64512 = (2^6 - 1) << 10
        b = (chunk & 1008)  >>  4 // 1008  = (2^6 - 1) << 4
     
        // Set the 2 least significant bits to zero
        c = (chunk & 15)    <<  2 // 15    = 2^4 - 1
     
        base64 += encodings[a] + encodings[b] + encodings[c] + '='
      }
      
      return base64
    }

    function init() {
        log('Mosquito init');
        jQuery('html').bind('request-start', bindf(Connector, Connector.sendRequest));
        jQuery('html').bind('response-load', bindf(remoteController, remoteController.sendResponse));
        jQuery('html').bind('response-error', bindf(remoteController, remoteController.sendError));
        launchMosquitoConnector();
    }

    // startup

    function pollJQuery() {
            if (typeof(jQuery) !== 'undefined') {
            clearInterval(interval);
            init(); // we have jquery, init
        }
    }

     //if the jQuery object isn't available
    if (typeof(jQuery) == 'undefined') {
        // load it
        var x = new XMLHttpRequest();
        x.open("GET", params.base_url+ 'jquery-1.6.4.min.js?_=' + Math.random(), false);
        x.onreadystatechange = function() {
            if (x.readyState == 4 && x.status == 200) {
                eval(x.responseText);
            }
        };
        x.send(null);

        var interval = setInterval(pollJQuery, 200); // check every 200 ms
    } else {
        init(); // init immediately
    }

})(document);