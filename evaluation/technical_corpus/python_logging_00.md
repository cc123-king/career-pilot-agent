# Python 3.12.7 logging 原始文档摘录 1

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/logging.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

:mod:`!logging` --- Logging facility for Python
===============================================

.. module:: logging
   :synopsis: Flexible event logging system for applications.

.. moduleauthor:: Vinay Sajip <vinay_sajip@red-dove.com>
.. sectionauthor:: Vinay Sajip <vinay_sajip@red-dove.com>

**Source code:** :source:`Lib/logging/__init__.py`

.. index:: pair: Errors; logging

.. sidebar:: Important

   This page contains the API reference information. For tutorial
   information and discussion of more advanced topics, see

   * :ref:`Basic Tutorial <logging-basic-tutorial>`
   * :ref:`Advanced Tutorial <logging-advanced-tutorial>`
   * :ref:`Logging Cookbook <logging-cookbook>`

--------------

This module defines functions and classes which implement a flexible event
logging system for applications and libraries.

The key benefit of having the logging API provided by a standard library module
is that all Python modules can participate in logging, so your application log
can include your own messages integrated with messages from third-party
modules.

Here's a simple example of idiomatic usage: ::

   # myapp.py
   import logging
   import mylib
   logger = logging.getLogger(__name__)

   def main():
       logging.basicConfig(filename='myapp.log', level=logging.INFO)
       logger.info('Started')
       mylib.do_something()
       logger.info('Finished')

   if __name__ == '__main__':
       main()

::

   # mylib.py
   import logging
   logger = logging.getLogger(__name__)

   def do_something():
       logger.info('Doing something')

If you run *myapp.py*, you should see this in *myapp.log*:

.. code-block:: none

   INFO:__main__:Started
   INFO:mylib:Doing something
   INFO:__main__:Finished

The key feature of this idiomatic usage is that the majority of code is simply
creating a module level logger with ``getLogger(__name__)``, and using that
logger to do any needed logging. This is concise, while allowing downstream
code fine-grained control if needed. Logged messages to the module-level logger
get forwarded to handlers of loggers in higher-level modules, all the way up to
the highest-level logger known as the root logger; this approach is known as
hierarchical logging.

For logging to be useful, it needs to be configured: setting the levels and
destinations for each logger, potentially changing how specific modules log,
often based on command-line arguments or application configuration. In most
cases, like the one above, only the root logger needs to be so configured, since
all the lower level loggers at module level eventually forward their messages to
its handlers.  :func:`~logging.basicConfig` provides a quick way to configure
the root logger that handles many use cases.

The module provides a lot of functionality and flexibility.  If you are
unfamiliar with logging, the best way to get to grips with it is to view the
tutorials (**see the links above and on the right**).

The basic classes defined by the module, together with their attributes and
methods, are listed in the sections below.

* Loggers expose the interface that application code directly uses.
* Handlers send the log records (created by loggers) to the appropriate
  destination.
* Filters provide a finer grained facility for determining which log records
  to output.
* Formatters specify the layout of log records in the final output.


.. _logger:

Logger Objects
--------------

Loggers have the following attributes and methods.  Note that Loggers should
*NEVER* be instantiated directly, but always through the module-level function
``logging.getLogger(name)``.  Multiple calls to :func:`getLogger` with the same
name will always return a reference to the same Logger object.

The ``name`` is potentially a period-separated hierarchical value, like
``foo.bar.baz`` (though it could also be just plain ``foo``, for example).
Loggers that are further down in the hierarchical list are children of loggers
higher up in the list.  For example, given a logger with a name of ``foo``,
loggers with names of ``foo.bar``, ``foo.bar.baz``, and ``foo.bam`` are all
descendants of ``foo``.  In addition, all loggers are descendants of the root
logger. The logger name hierarchy is analogous to the Python package hierarchy,
and identical to it if you organise your loggers on a per-module basis using
the recommended construction ``logging.getLogger(__name__)``.  That's because
in a module, ``__name__`` is the module's name in the Python package namespace.


.. class:: Logger

   .. attribute:: Logger.name

      This is the logger's name, and is the value that was passed to :func:`getLogger`
      to obtain the logger.

      .. note:: This attribute should be treated as read-only.

   .. attribute:: Logger.level

      The threshold of this logger, as set by the :meth:`setLevel` method.

      .. note:: Do not set this attribute directly - always use :meth:`setLevel`,
         which has checks for the level passed to it.

   .. attribute:: Logger.parent

      The parent logger of this logger. It may change based on later instantiation
      of loggers which are higher up in the namespace hierarchy.

      .. note:: This value should be treated as read-only.

   .. attribute:: Logger.propagate

      If this attribute evaluates to true, events logged to this logger will be
      passed to the handlers of higher level (ancestor) loggers, in addition to
      any handlers attached to this logger. Messages are passed directly to the
      ancestor loggers' handlers - neither the level nor filters of the ancestor
      loggers in question are considered.

      If this evaluates to false, logging messages are not passed to the handlers
      of ancestor loggers.

      Spelling it out with an example: If the propagate attribute of the logger named
      ``A.B.C`` evaluates to true, any event logged to ``A.B.C`` via a method call such as
      ``logging.getLogger('A.B.C').error(...)`` will [subject to passing that logger's
      level and filter settings] be passed in turn to any handlers attached to loggers
      named ``A.B``, ``A`` and the root logger, after first being passed to any handlers
      attached to ``A.B.C``. If any logger in the chain ``A.B.C``, ``A.B``, ``A`` has its
      ``propagate`` attribute set to false, then that is the last logger whose handlers
      are offered the event to handle, and propagation stops at that point.

      The constructor sets this attribute to ``True``.

      .. note:: If you attach a handler to a logger *and* one or more of its
         ancestors, it may emit the same record multiple times. In general, you
         should not need to attach a handler to more than one logger - if you just
         attach it to the appropriate logger which is highest in the logger
         hierarchy, then it will see all events logged by all descendant loggers,
         provided that their propagate setting is left set to ``True``. A common
         scenario is to attach handlers only to the root logger, and to let
         propagation take care of the rest.

   .. attribute:: Logger.handlers

      The list of handlers directly attached to this logger instance.

      .. note:: This attribute should be treated as read-only; it is normally changed via
         the :meth:`addHandler` and :meth:`removeHandler` methods, which use locks to ensure
         thread-safe operation.

   .. attribute:: Logger.disabled

      This attribute disables handling of any events. It is set to ``False`` in the
      initializer, and only changed by logging configuration code.

      .. note:: This attribute should be treated as read-only.

   .. method:: Logger.setLevel(level)

      Sets the threshold for this logger to *level*. Logging messages which are less
      severe than *level* will be ignored; logging messages which have severity *level*
      or higher will be emitted by whichever handler or handlers service this logger,
      unless a handler's level has been set to a higher severity level than *level*.

      When a logger is created, the level is set to :const:`NOTSET` (which causes
      all messages to be processed when the logger is the root logger, or delegation
      to the parent when the logger is a non-root logger). Note that the root logger
      is created with level :const:`WARNING`.

      The term 'delegation to the parent' means that if a logger has a level of
      NOTSET, its chain of ancestor loggers is traversed until either an ancestor with
      a level other than NOTSET is found, or the root is reached.

      If an ancestor is found with a level other than NOTSET, then that ancestor's
      level is treated as the effective level of the logger where the ancestor search
      began, and is used to determine how a logging event is handled.

      If the root is reached, and it has a level of NOTSET, then all messages will be
      processed. Otherwise, the root's level will be used as the effective level.

      See :ref:`levels` for a list of levels.

      .. versionchanged:: 3.2
         The *level* parameter now accepts a string representation of the
         level such as 'INFO' as an alternative to the integer constants
         such as :const:`INFO`. Note, however, that levels are internally stored
         as integers, and methods such as e.g. :meth:`getEffectiveLevel` and
         :meth:`isEnabledFor` will return/expect to be passed integers.


   .. method:: Logger.isEnabledFor(level)

      Indicates if a message of severity *level* would be processed by this logger.
      This method checks first the module-level level set by
      ``logging.disable(level)`` and then the logger's effective level as determined
      by :meth:`getEffectiveLevel`.


   .. method:: Logger.getEffectiveLevel()

      Indicates the effective level for this logger. If a value other than
      :const:`NOTSET` has been set using :meth:`setLevel`, it is returned. Otherwise,
      the hierarchy is traversed towards the root until a value other than
      :const:`NOTSET` is found, and that value is returned. The value returned is
      an integer, typically one of :const:`logging.DEBUG`, :const:`logging.INFO`
      etc.


   .. method:: Logger.getChild(suffix)

      Returns a logger which is a descendant to this logger, as determined by the suffix.
      Thus, ``logging.getLogger('abc').getChild('def.ghi')`` would return the same
      logger as would be returned by ``logging.getLogger('abc.def.ghi')``. This is a
      convenience method, useful when the parent logger is named using e.g. ``__name__``
      rather than a literal string.

      .. versionadded:: 3.2


   .. method:: Logger.getChildren()

      Returns a set of loggers which are immediate children of this logger. So for
      example ``logging.getLogger().getChildren()`` might return a set containing
      loggers named ``foo`` and ``bar``, but a logger named ``foo.bar`` wouldn't be
      included in the set. Likewise, ``logging.getLogger('foo').getChildren()`` might
      return a set including a logger named ``foo.bar``, but it wouldn't include one
      named ``foo.bar.baz``.

      .. versionadded:: 3.12


   .. method:: Logger.debug(msg, *args, **kwargs)

      Logs a message with level :const:`DEBUG` on this logger. The *msg* is the
      message format string, and the *args* are the arguments which are merged into
      *msg* using the string formatting operator. (Note that this means that you can
      use keywords in the format string, together with a single dictionary argument.)
      No % formatting operation is performed on *msg* when no *args* are supplied.

      There are four keyword arguments in *kwargs* which are inspected:
      *exc_info*, *stack_info*, *stacklevel* and *extra*.

      If *exc_info* does not evaluate as false, it causes exception information to be
      added to the logging message. If an exception tuple (in the format returned by
      :func:`sys.exc_info`) or an exception instance is provided, it is used;
      otherwise, :func:`sys.exc_info` is called to get the exception information.

      The second optional keyword argument is *stack_info*, which defaults to
      ``False``. If true, stack information is added to the logging
      message, including the actual logging call. Note that this is not the same
      stack information as that displayed through specifying *exc_info*: The
      former is stack frames from the bottom of the stack up to the logging call
      in the current thread, whereas the latter is information about stack frames
      which have been unwound, following an exception, while searching for
      exception handlers.

      You can specify *stack_info* independently of *exc_info*, e.g. to just show
      how you got to a certain point in your code, even when no exceptions were
      raised. The stack frames are printed following a header line which says:

      .. code-block:: none

          Stack (most recent call last):

      This mimics the ``Traceback (most recent call last):`` which is used when
      displaying exception frames.

      The third optional keyword argument is *stacklevel*, which defaults to ``1``.
      If greater than 1, the corresponding number of stack frames are skipped
      when computing the line number and function name set in the :class:`LogRecord`
      created for the logging event. This can be used in logging helpers so that
      the function name, filename and line number recorded are not the information
      for the helper function/method, but rather its caller. The name of this
      parameter mirrors the equivalent one in the :mod:`warnings` module.

      The fourth keyword argument is *extra* which can be used to pass a
      dictionary which is used to populate the :attr:`~object.__dict__` of the
      :class:`LogRecord`
      created for the logging event with user-defined attributes. These custom
      attributes can then be used as you like. For example, they could be
      incorporated into logged messages. For example::

         FORMAT = '%(asctime)s %(clientip)-15s %(user)-8s %(message)s'
         logging.basicConfig(format=FORMAT)
         d = {'clientip': '192.168.0.1', 'user': 'fbloggs'}
         logger = logging.getLogger('tcpserver')
         logger.warning('Protocol problem: %s', 'connection reset', extra=d)

      would print something like

      .. code-block:: none

         2006-02-08 22:20:02,165 192.168.0.1 fbloggs  Protocol problem: connection reset

      The keys in the dictionary passed in *extra* should not clash with the keys used
      by the logging system. (See the section on :ref:`logrecord-attributes` for more
      information on which keys are used by the logging system.)

      If you choose to use these attributes in logged messages, you need to exercise
      some care. In the above example, for instance, the :class:`Formatter` has been
      set up with a format string which expects 'clientip' and 'user' in the attribute
      dictionary of the :class:`LogRecord`. If these are missing, the message will
      not be logged because a string formatting exception will occur. So in this case,
      you always need to pass the *extra* dictionary with these keys.

      While this might be annoying, this feature is intended for use in specialized
      circumstances, such as multi-threaded servers where the same code executes in
      many contexts, and interesting conditions which arise are dependent on this
      context (such as remote client IP address and authenticated user name, in the
      above example). In such circumstances, it is likely that specialized
      :class:`Formatter`\ s would be used with particular :class:`Handler`\ s.

      If no handler is attached to this logger (or any of its ancestors,
      taking into account the relevant :attr:`Logger.propagate` attributes),
      the message will be sent to the handler set on :attr:`lastResort`.

