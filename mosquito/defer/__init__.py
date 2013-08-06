#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Small framework for asynchronous programming."""
# Copyright (C) 2008-2010 Sebastian Heinlein <devel@glatzor.de>
# Copyright (c) 2001-2010
# Allen Short
# Andy Gayton
# Andrew Bennetts
# Antoine Pitrou
# Apple Computer, Inc.
# Benjamin Bruheim
# Bob Ippolito
# Canonical Limited
# Christopher Armstrong
# David Reid
# Donovan Preston
# Eric Mangold
# Eyal Lotem
# Itamar Shtull-Trauring
# James Knight
# Jason A. Mobarak
# Jean-Paul Calderone
# Jessica McKellar
# Jonathan Jacobs
# Jonathan Lange
# Jonathan D. Simms
# Jürgen Hermann
# Kevin Horn
# Kevin Turner
# Mary Gardiner
# Matthew Lefkowitz
# Massachusetts Institute of Technology
# Moshe Zadka
# Paul Swartz
# Pavel Pergamenshchik
# Ralph Meijer
# Sean Riley
# Software Freedom Conservancy
# Travis B. Hartwell
# Thijs Triemstra
# Thomas Herve
# Timothy Allen
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

__all__ = ("Deferred", "AlreadyCalledDeferred", "DeferredException",
           "defer", "inline_callbacks", "return_value")

from . import version
import collections
__version__ = version.VERSION

from functools import wraps
import sys
import warnings


class _DefGen_Return(BaseException):
    """Exception to return a result from an inline callback."""
    def __init__(self, value):
        self.value = value


class AlreadyCalledDeferred(Exception):
    """The Deferred is already running a callback."""


class DeferredException(object):
    """Allows to defer exceptions."""

    def __init__(self, type=None, value=None, traceback=None):
        """Return a new DeferredException instance.

        If type, value and traceback are not specified the infotmation
        will be retreieved from the last caught exception:

        >>> try:
        ...     raise Exception("Test")
        ... except:
        ...     deferred_exc = DeferredException()
        >>> deferred_exc.raise_exception()
        Traceback (most recent call last):
            ...
        Exception: Test

        Alternatively you can set the exception manually:

        >>> exception = Exception("Test 2")
        >>> deferred_exc = DeferredException(exception)
        >>> deferred_exc.raise_exception()
        Traceback (most recent call last):
            ...
        Exception: Test 2
        """
        self.type = type
        self.value = value
        self.traceback = traceback
        if isinstance(type, Exception):
            self.type = type.__class__
            self.value = type
        elif not type or not value:
            self.type, self.value, self.traceback = sys.exc_info()

    def raise_exception(self):
        """Raise the stored exception."""
        raise self.type(self.value).with_traceback(self.traceback)

    def catch(self, *errors):
        """Check if the stored exception is a subclass of one of the
        provided exception classes. If this is the case return the
        matching exception class. Otherwise raise the stored exception.

        >>> exc = DeferredException(SystemError())
        >>> exc.catch(Exception) # Will catch the exception and return it
        <type 'exceptions.Exception'>
        >>> exc.catch(OSError)   # Won't catch and raise the stored exception
        Traceback (most recent call last):
            ...
        SystemError

        This method can be used in errbacks of a Deferred:

        >>> def dummy_errback(deferred_exception):
        ...     '''Error handler for OSError'''
        ...     deferred_exception.catch(OSError)
        ...     return "catched"

        The above errback can handle an OSError:

        >>> deferred = Deferred()
        >>> deferred.add_errback(dummy_errback)
        >>> deferred.errback(OSError())
        >>> deferred.result
        'catched'

        But fails to handle a SystemError:

        >>> deferred2 = Deferred()
        >>> deferred2.add_errback(dummy_errback)
        >>> deferred2.errback(SystemError())
        >>> deferred2.result                             #doctest: +ELLIPSIS
        <defer.DeferredException object at 0x...>
        >>> deferred2.result.value
        SystemError()
        """
        for err in errors:
            if issubclass(self.type, err):
                return err
        self.raise_exception()


class Deferred(object):
    """The Deferred allows to chain callbacks.

    There are two type of callbacks: normal callbacks and errbacks, which
    handle an exception in a normal callback.

    The callbacks are processed in pairs consisting of a normal callback
    and an errback. A normal callback will return its result to the
    callback of the next pair.  If an exception occurs, it will be handled
    by the errback of the next pair. If an errback doesn't raise an error
    again, the callback of the next pair will be called with the return
    value of the errback. Otherwise the exception of the errback will be
    returned to the errback of the next pair::

        CALLBACK1      ERRBACK1
         |     \       /     |
     result failure  result failure
         |       \   /       |
         |        \ /        |
         |         X         |
         |        / \        |
         |       /   \       |
         |      /     \      |
        CALLBACK2      ERRBACK2
         |     \       /     |
     result failure  result failure
         |       \   /       |
         |        \ /        |
         |         X         |
         |        / \        |
         |       /   \       |
         |      /     \      |
        CALLBACK3      ERRBACK3
      """

    def __init__(self):
        """Return a new Deferred instance."""
        self.callbacks = []
        self.errbacks = []
        self.called = False
        self.paused = False
        self._running = False

    def add_callbacks(self, callback, errback=None,
                      callback_args=None, callback_kwargs=None,
                      errback_args=None, errback_kwargs=None):
        """Add a pair of callables (function or method) to the callback and
        errback chain.

        Keyword arguments:
        callback -- the next chained challback
        errback -- the next chained errback
        callback_args -- list of additional arguments for the callback
        callback_kwargs -- dict of additional arguments for the callback
        errback_args -- list of additional arguments for the errback
        errback_kwargs -- dict of additional arguments for the errback

        In the following example the first callback pairs raises an
        exception that is catched by the errback of the second one and
        processed by the third one.

        >>> def callback(previous):
        ...     '''Return the previous result.'''
        ...     return "Got: %s" % previous
        >>> def callback_raise(previous):
        ...     '''Fail and raise an exception.'''
        ...     raise Exception("Test")
        >>> def errback(error):
        ...     '''Recover from an exception.'''
        ...     #error.catch(Exception)
        ...     return "catched"
        >>> deferred = Deferred()
        >>> deferred.callback("start")
        >>> deferred.result
        'start'
        >>> deferred.add_callbacks(callback_raise, errback)
        >>> deferred.result                             #doctest: +ELLIPSIS
        <defer.DeferredException object at 0x...>
        >>> deferred.add_callbacks(callback, errback)
        >>> deferred.result
        'catched'
        >>> deferred.add_callbacks(callback, errback)
        >>> deferred.result
        'Got: catched'
        """
        assert isinstance(callback, collections.Callable)
        assert errback is None or isinstance(errback, collections.Callable)
        if errback is None:
            errback = _passthrough
        self.callbacks.append(((callback,
                                callback_args or ([]),
                                callback_kwargs or ({})),
                               (errback or (_passthrough),
                                errback_args or ([]),
                                errback_kwargs or ({}))))
        if self.called:
            self._next()

    def add_errback(self, func, *args, **kwargs):
        """Add a callable (function or method) to the errback chain only.

        If there isn't any exception the result will be passed through to
        the callback of the next pair.

        The first argument is the callable instance followed by any
        additional argument that will be passed to the errback.

        The errback method will get the most recent DeferredException and
        and any additional arguments that was specified in add_errback.

        If the errback can catch the exception it can return a value that
        will be passed to the next callback in the chain. Otherwise the
        errback chain will not be processed anymore.

        See the documentation of defer.DeferredException.catch for
        further information.

        >>> def catch_error(deferred_error, ignore=False):
        ...     if ignore:
        ...         return "ignored"
        ...     deferred_error.catch(Exception)
        ...     return "catched"
        >>> deferred = Deferred()
        >>> deferred.errback(SystemError())
        >>> deferred.add_errback(catch_error, ignore=True)
        >>> deferred.result
        'ignored'
        """
        self.add_callbacks(_passthrough, func, errback_args=args,
                           errback_kwargs=kwargs)

    def add_callback(self, func, *args, **kwargs):
        """Add a callable (function or method) to the callback chain only.

        An error would be passed through to the next errback.

        The first argument is the callable instance followed by any
        additional argument that will be passed to the callback.

        The callback method will get the result of the previous callback
        and any additional arguments that was specified in add_callback.

        >>> def callback(previous, counter=False):
        ...     if counter:
        ...         return previous + 1
        ...     return previous
        >>> deferred = Deferred()
        >>> deferred.add_callback(callback, counter=True)
        >>> deferred.callback(1)
        >>> deferred.result
        2
        """
        self.add_callbacks(func, _passthrough, callback_args=args,
                           callback_kwargs=kwargs)

    def errback(self, error=None):
        """Start processing the errorback chain starting with the
        provided exception or DeferredException.

        If an exception is specified it will be wrapped into a
        DeferredException. It will be send to the first errback or stored 
        as finally result if not any further errback has been specified yet.

        >>> deferred = Deferred()
        >>> deferred.errback(Exception("Test Error"))
        >>> deferred.result                             #doctest: +ELLIPSIS
        <defer.DeferredException object at 0x...>
        >>> deferred.result.raise_exception()
        Traceback (most recent call last):
            ...
        Exception: Test Error
        """
        if self.called:
            raise AlreadyCalledDeferred()
        if not error:
            error = DeferredException()
        elif not isinstance(error, DeferredException):
            assert isinstance(error, Exception)
            error = DeferredException(error.__class__, error, None)
        self.called = True
        self.result = error
        self._next()

    def callback(self, result=None):
        """Start processing the callback chain starting with the
        provided result.

        It will be send to the first callback or stored as finally
        one if not any further callback has been specified yet.

        >>> deferred = Deferred()
        >>> deferred.callback("done")
        >>> deferred.result
        'done'
        """
        if self.called:
            raise AlreadyCalledDeferred()
        self.called = True
        self.result = result
        self._next()

    def _continue(self, result):
        """Continue processing the Deferred with the given result."""
        self.result = result
        self.paused = False
        if self.called:
            self._next()

    def _next(self):
        """Process the next callback."""
        if self._running or self.paused:
            return
        while self.callbacks:
            # Get the next callback pair
            next_pair = self.callbacks.pop(0)
            # Continue with the errback if the last result was an exception
            callback, args, kwargs = next_pair[isinstance(self.result,
                                                          DeferredException)]
            try:
                self.result = callback(self.result, *args, **kwargs)
            except:
                self.result = DeferredException()
            finally:
                self._running = False
            if isinstance(self.result, Deferred):
                # If a Deferred was returned add this deferred as callbacks to
                # the returned one. As a result the processing of this Deferred
                # will be paused until all callbacks of the returned Deferred
                # have been performed
                self.result.add_callbacks(self._continue, self._continue)
                self.paused == True
                break

        if isinstance(self.result, DeferredException):
            # Print the exception to stderr and stop if there aren't any
            # further errbacks to process
            sys.excepthook(self.result.type, self.result.value,
                           self.result.traceback)
            return False
 
def defer(func, *args, **kwargs):
    """Invoke the given function that may or not may be a Deferred.

    If the return object of the function call is a Deferred return, it.
    Otherwise wrap it into a Deferred.

    >>> defer(lambda x: x, 10)                 #doctest: +ELLIPSIS
    <defer.Deferred object at 0x...>

    >>> deferred = defer(lambda x: x, "done")
    >>> deferred.result
    'done'

    >>> deferred = Deferred()
    >>> defer(lambda: deferred) == deferred
    True
    """
    assert isinstance(func, collections.Callable)
    try:
        result = func(*args, **kwargs)
    except:
        result = DeferredException()
    if isinstance(result, Deferred):
        return result
    deferred = Deferred()
    deferred.callback(result)
    return deferred

def _passthrough(arg):
    return arg

def return_value(val):
    """
    Return val from a inline_callbacks generator.

    Note: this is currently implemented by raising an exception
    derived from BaseException.  You might want to change any
    'except:' clauses to an 'except Exception:' clause so as not to
    catch this exception.

    Also: while this function currently will work when called from
    within arbitrary functions called from within the generator, do
    not rely upon this behavior.
    """
    raise _DefGen_Return(val)

def _inline_callbacks(result, gen, deferred):
    """
    See inlineCallbacks.
    """
    # This function is complicated by the need to prevent unbounded recursion
    # arising from repeatedly yielding immediately ready deferreds.  This while
    # loop and the waiting variable solve that by manually unfolding the
    # recursion.

    waiting = [True, # waiting for result?
               None] # result

    while 1:
        try:
            # Send the last result back as the result of the yield expression.
            is_failure = isinstance(result, DeferredException)
            if is_failure:
                if sys.version_info[0] < 3:
                    result = gen.throw(result.type, result.value, result.traceback)
                else:
                    result = gen.throw(result.type(result.value).with_traceback(result.traceback))
            else:
                result = gen.send(result)
        except StopIteration:
            # fell off the end, or "return" statement
            deferred.callback(None)
            return deferred
        except _DefGen_Return as err:
            # returnValue() was called; time to give a result to the original
            # Deferred.  First though, let's try to identify the potentially
            # confusing situation which results when return_value() is
            # accidentally invoked from a different function, one that wasn't
            # decorated with @inline_callbacks.

            # The traceback starts in this frame (the one for
            # _inline_callbacks); the next one down should be the application
            # code.
            appCodeTrace = sys.exc_info()[2].tb_next
            if is_failure:
                # If we invoked this generator frame by throwing an exception
                # into it, then throwExceptionIntoGenerator will consume an
                # additional stack frame itself, so we need to skip that too.
                appCodeTrace = appCodeTrace.tb_next
            # Now that we've identified the frame being exited by the
            # exception, let's figure out if returnValue was called from it
            # directly.  returnValue itself consumes a stack frame, so the
            # application code will have a tb_next, but it will *not* have a
            # second tb_next.
            if appCodeTrace.tb_next and appCodeTrace.tb_next.tb_next:
                # If returnValue was invoked non-local to the frame which it is
                # exiting, identify the frame that ultimately invoked
                # returnValue so that we can warn the user, as this behavior is
                # confusing.
                ultimateTrace = appCodeTrace
                while ultimateTrace.tb_next.tb_next:
                    ultimateTrace = ultimateTrace.tb_next
                filename = ultimateTrace.tb_frame.f_code.co_filename
                lineno = ultimateTrace.tb_lineno
                warnings.warn_explicit(
                    "returnValue() in %r causing %r to exit: "
                    "returnValue should only be invoked by functions decorated "
                    "with inlineCallbacks" % (
                        ultimateTrace.tb_frame.f_code.co_name,
                        appCodeTrace.tb_frame.f_code.co_name),
                    DeprecationWarning, filename, lineno)
            deferred.callback(err.value)
            return deferred
        except:
            deferred.errback()
            return deferred

        if isinstance(result, Deferred):
            # a deferred was yielded, get the result.
            def gotResult(res):
                if waiting[0]:
                    waiting[0] = False
                    waiting[1] = res
                else:
                    _inline_callbacks(res, gen, deferred)

            result.add_callbacks(gotResult, gotResult)
            if waiting[0]:
                # Haven't called back yet, set flag so that we get reinvoked
                # and return from the loop
                waiting[0] = False
                return deferred

            result = waiting[1]
            # Reset waiting to initial values for next loop.  gotResult uses
            # waiting, but this isn't a problem because gotResult is only
            # executed once, and if it hasn't been executed yet, the return
            # branch above would have been taken.
            waiting[0] = True
            waiting[1] = None
    return deferred

def inline_callbacks(func):
    """inline_callbacks helps you write Deferred-using code that looks like a
    regular sequential function. For example::

        def thingummy():
            thing = yield makeSomeRequestResultingInDeferred()
            print thing #the result! hoorj!
        thingummy = inline_callbacks(thingummy)

    When you call anything that results in a Deferred, you can simply yield it;
    your generator will automatically be resumed when the Deferred's result is
    available. The generator will be sent the result of the Deferred with the
    'send' method on generators, or if the result was a failure, 'throw'.

    Your inline_callbacks-enabled generator will return a Deferred object, which
    will result in the return value of the generator (or will fail with a
    failure object if your generator raises an unhandled exception). Note that
    you can't use return result to return a value; use return_value(result)
    instead. Falling off the end of the generator, or simply using return
    will cause the Deferred to have a result of None.

    The Deferred returned from your deferred generator may errback if your
    generator raised an exception::

        def thingummy():
            thing = yield makeSomeRequestResultingInDeferred()
            if thing == 'I love Twisted':
                # will become the result of the Deferred
                return_value('TWISTED IS GREAT!')
            else:
                # will trigger an errback
                raise Exception('DESTROY ALL LIFE')
        thingummy = inline_callbacks(thingummy)
    """
    @wraps(func)
    def unwind_generator(*args, **kwargs):
        return _inline_callbacks(None, func(*args, **kwargs), Deferred())
    return unwind_generator


# vim:tw=4:sw=4:et
