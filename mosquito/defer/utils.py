#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Utils for using deferreds with D-Bus."""
# Copyright (C) 2008-2010 Sebastian Heinlein <devel@glatzor.de>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

__author__  = "Sebastian Heinlein <devel@glatzor.de>"

__all__ = ("dbus_deferred_method", "deferable")

from functools import wraps
import inspect

import dbus

from . import defer, Deferred, DeferredException


def dbus_deferred_method(*args, **kwargs):
    """Export the decorated method on the D-Bus and handle a maybe
    returned Deferred.

    This decorator can be applied to methods in the same way as the
    @dbus.service.method method, but it correctly handles the case where
    the method returns a Deferred.

    This decorator was kindly taken from James Henstridge blog post and
    adopted:
    http://blogs.gnome.org/jamesh/2009/07/06/watching-iview-with-rygel/
    """
    def decorator(function):
        function = dbus.service.method(*args, **kwargs)(function)
        @wraps(function)
        def wrapper(*args, **kwargs):
            def ignore_none_callback(*cb_args):
                # The deferred method at least returns an tuple containing
                # only None. Ignore this case.
                if cb_args == (None,):
                    dbus_callback()
                else:
                    dbus_callback(*cb_args)
            dbus_callback = kwargs.pop('_dbus_callback')
            dbus_errback = kwargs.pop('_dbus_errback')
            deferred = defer(function, *args, **kwargs)
            deferred.add_callback(ignore_none_callback)
            deferred.add_errback(lambda error: dbus_errback(error.value))
        # The @wraps decorator has copied over the attributes added by
        # the @dbus.service.method decorator, but we need to manually
        # set the async callback attributes.
        wrapper._dbus_async_callbacks = ('_dbus_callback', '_dbus_errback')
        return wrapper
    return decorator

def deferable(func):
    """Add a defer attribute to the decorated function and return a Deferred
    object. The callback of the Deferred will be passed as reply_handler
    argument and the errback as the error_handler argument to the decorated
    function.

    This decorator allows to easily make use of Deferreds in a DBus client.
    """
    @wraps(func)
    def _deferable(*args, **kwargs):
        def on_error(error, deferred):
            # Make sure that we return a deferred exception
            if isinstance(error, DeferredException):
                deferred.errback(error)
            else:
                deferred.errback(DeferredException(error))

        try:
            # Check if the defer argument was specified
            to_defer = kwargs.pop("defer")
        except KeyError:
            # Check if this function was called from an inline_callbacks
            # decorated method
            stack = inspect.stack()
            try:
                to_defer = stack[2][3] == "_inline_callbacks"
            except IndexError:
                to_defer = False

        if to_defer:
            deferred = Deferred()
            kwargs["reply_handler"] = deferred.callback
            kwargs["error_handler"] = lambda err: on_error(err, deferred)
            func(*args, **kwargs)
            return deferred
        return func(*args, **kwargs)
    return _deferable

# vim:tw=4:sw=4:et
