/**
 * mosquito = silent, self setup malaria
 * @author Krzysztof Kotowicz kkotowicz@gmail.com
 * @see http://blog.kotowicz.net
 * @see https://github.com/koto/mosquito
 **/
(function(d) {

    // to be removed
    function log(m) {
        console.debug(m);
    }

    function bind(scope, fn) {
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
        log(scripts[i]);
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

            sendRequest: function(event, types, url, method, body) {
                log("Sending XHR request to " + url);
                var current_type = types.shift();
                var xhr = this.factory(current_type);
                // get first available type
                xhr.open(method, url, true);
                if (current_type === 'cors-withcredentials') {
                    xhr.withCredentials = 'true';
                }
                if (typeof xhr.overrideMimeType !== "undefined") {
                    xhr.overrideMimeType('text/plain; charset=x-user-defined');
                }

                xhr._url = url;
                xhr._method = method;
                xhr._types_left = types;
                xhr._type = current_type;
                if (body) {
                    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
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
                $('body').trigger('response-load', [xhr.responseText, xhr]);
            },

            handleError: function(event, xhr) {
                log('error');
                if (xhr._types_left.length == 0) {
                    $('body').trigger('response-error', xhr);
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

    var fr = new FileReader;

    function requestUrl(url, method) {
        var use_methods = ['cors-withcredentials'];
        // USE ['flash'] instead to use flash only, see browser.html
        $('body').trigger('request-start', [ use_methods, url, method, null ]);
    }

    function parseRequestFromProxy(req) {
        // req = "METHOD URL ACCEPT-HEADER-VALUE"
        var parts = req.split(' ');

        log("Received: " + req);
        if (parts.length >= 2)
            requestUrl(parts[1], parts[0]); // we ignore the accept type for now
    }

    var readByteAt = function(i, fileContents){
        return fileContents.charCodeAt(i) & 0xff;
    };

    function returnResponseToProxy(d) {
        var response = '';
        var binaryBody = null;
        if (d.result === 'ok') {
            log("Received success XHR response from " + d.request.type);
            if (d.response.bytes) {
              binaryBody = new Uint8Array(d.response.bytes.length); // Note:not xhr.responseText
              for (var i  = 0 ; i < d.response.bytes.length; i++) {
                binaryBody[i] = d.response.bytes[i];
              }
            }
            response = d.response.body; // MalaRIA does not report headers back to proxy clients
        } else {
            log("Received error XHR response");
            // todo 502
            //document.getElementById('response').value = event.data;
            response = 'HTTP/1.1 502 Not accessible - ' + d;
        }

        if (binaryBody) {
            log("Sending " + binaryBody.length + " bytes to MalaRIA");
            p.send(binaryBody.length + ":");
            p.send(binaryBody.buffer);
        } else {
            log("Sending " + response.length + " characters to MalaRIA");
            response = response.length + ":" + response;
            p.send(response);
        }
    }

    function launchMalariaConnector() {
        try {
            p = new ReconnectingWebSocket('ws://' + params.ws_host + ':' + params.ws_port, 'binary');
        } catch (e) {
            log("Cannot connect to WebSocket server:" + e.message);
        }

        if (p) {
            p.onopen = function() {
                log("Connected to MalaRIA at " + p.URL);
                fr.onload = function(e) {
                    parseRequestFromProxy(e.target.result);
                };
                p.send('Hello from ' + d.location.href);
                p.onmessage = function(e) {
                    fr.readAsBinaryString(e.data);
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
                    $('body').trigger('request-start', reqparams);
                }
            } catch(e) {}
        },
        prepareResult: function(xhr) {
            return {
                result: undefined,
                duration: xhr._end_time - xhr._start_time,
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
        sendError: function(event, xhr) {
            var obj = this.prepareResult(xhr);
            obj.result = 'error';
            var data = JSON.stringify(obj);
            returnResponseToProxy(obj);
        },
        sendResponse: function(event, text, xhr) {
            var obj = this.prepareResult(xhr);
            obj.result = 'ok';
            obj.response.body = text;
            obj.response.bytes = Array.prototype.map.call(text, this.byteValue);
            obj.response.headers = (xhr.getAllResponseHeaders ? xhr.getAllResponseHeaders() : null);
            returnResponseToProxy(obj);
        },
        byteValue: function(x) {
            return x.charCodeAt(0) & 0xff;
        }
    }

    function init() {
        log('Mosquito init');
        $('body').bind('request-start', bind(Connector, Connector.sendRequest));
        $('body').bind('response-load', bind(remoteController, remoteController.sendResponse));
        $('body').bind('response-error', bind(remoteController, remoteController.sendError));
        launchMalariaConnector();
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