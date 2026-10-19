# Python 3.12.7 logging 原始文档摘录 2

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/logging.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

      .. versionchanged:: 3.2
         The *stack_info* parameter was added.

      .. versionchanged:: 3.5
         The *exc_info* parameter can now accept exception instances.

      .. versionchanged:: 3.8
         The *stacklevel* parameter was added.


   .. method:: Logger.info(msg, *args, **kwargs)

      Logs a message with level :const:`INFO` on this logger. The arguments are
      interpreted as for :meth:`debug`.


   .. method:: Logger.warning(msg, *args, **kwargs)

      Logs a message with level :const:`WARNING` on this logger. The arguments are
      interpreted as for :meth:`debug`.

      .. note:: There is an obsolete method ``warn`` which is functionally
         identical to ``warning``. As ``warn`` is deprecated, please do not use
         it - use ``warning`` instead.

   .. method:: Logger.error(msg, *args, **kwargs)

      Logs a message with level :const:`ERROR` on this logger. The arguments are
      interpreted as for :meth:`debug`.


   .. method:: Logger.critical(msg, *args, **kwargs)

      Logs a message with level :const:`CRITICAL` on this logger. The arguments are
      interpreted as for :meth:`debug`.


   .. method:: Logger.log(level, msg, *args, **kwargs)

      Logs a message with integer level *level* on this logger. The other arguments are
      interpreted as for :meth:`debug`.


   .. method:: Logger.exception(msg, *args, **kwargs)

      Logs a message with level :const:`ERROR` on this logger. The arguments are
      interpreted as for :meth:`debug`. Exception info is added to the logging
      message. This method should only be called from an exception handler.


   .. method:: Logger.addFilter(filter)

      Adds the specified filter *filter* to this logger.


   .. method:: Logger.removeFilter(filter)

      Removes the specified filter *filter* from this logger.


   .. method:: Logger.filter(record)

      Apply this logger's filters to the record and return ``True`` if the
      record is to be processed. The filters are consulted in turn, until one of
      them returns a false value. If none of them return a false value, the record
      will be processed (passed to handlers). If one returns a false value, no
      further processing of the record occurs.


   .. method:: Logger.addHandler(hdlr)

      Adds the specified handler *hdlr* to this logger.


   .. method:: Logger.removeHandler(hdlr)

      Removes the specified handler *hdlr* from this logger.


   .. method:: Logger.findCaller(stack_info=False, stacklevel=1)

      Finds the caller's source filename and line number. Returns the filename, line
      number, function name and stack information as a 4-element tuple. The stack
      information is returned as ``None`` unless *stack_info* is ``True``.

      The *stacklevel* parameter is passed from code calling the :meth:`debug`
      and other APIs. If greater than 1, the excess is used to skip stack frames
      before determining the values to be returned. This will generally be useful
      when calling logging APIs from helper/wrapper code, so that the information
      in the event log refers not to the helper/wrapper code, but to the code that
      calls it.


   .. method:: Logger.handle(record)

      Handles a record by passing it to all handlers associated with this logger and
      its ancestors (until a false value of *propagate* is found). This method is used
      for unpickled records received from a socket, as well as those created locally.
      Logger-level filtering is applied using :meth:`~Logger.filter`.


   .. method:: Logger.makeRecord(name, level, fn, lno, msg, args, exc_info, func=None, extra=None, sinfo=None)

      This is a factory method which can be overridden in subclasses to create
      specialized :class:`LogRecord` instances.

   .. method:: Logger.hasHandlers()

      Checks to see if this logger has any handlers configured. This is done by
      looking for handlers in this logger and its parents in the logger hierarchy.
      Returns ``True`` if a handler was found, else ``False``. The method stops searching
      up the hierarchy whenever a logger with the 'propagate' attribute set to
      false is found - that will be the last logger which is checked for the
      existence of handlers.

      .. versionadded:: 3.2

   .. versionchanged:: 3.7
      Loggers can now be pickled and unpickled.

.. _levels:

Logging Levels
--------------

The numeric values of logging levels are given in the following table. These are
primarily of interest if you want to define your own levels, and need them to
have specific values relative to the predefined levels. If you define a level
with the same numeric value, it overwrites the predefined value; the predefined
name is lost.

+-----------------------+---------------+-------------------------------------+
| Level                 | Numeric value | What it means / When to use it      |
+=======================+===============+=====================================+
| .. py:data:: NOTSET   | 0             | When set on a logger, indicates that|
|                       |               | ancestor loggers are to be consulted|
|                       |               | to determine the effective level.   |
|                       |               | If that still resolves to           |
|                       |               | :const:`!NOTSET`, then all events   |
|                       |               | are logged. When set on a handler,  |
|                       |               | all events are handled.             |
+-----------------------+---------------+-------------------------------------+
| .. py:data:: DEBUG    | 10            | Detailed information, typically only|
|                       |               | of interest to a developer trying to|
|                       |               | diagnose a problem.                 |
+-----------------------+---------------+-------------------------------------+
| .. py:data:: INFO     | 20            | Confirmation that things are working|
|                       |               | as expected.                        |
+-----------------------+---------------+-------------------------------------+
| .. py:data:: WARNING  | 30            | An indication that something        |
|                       |               | unexpected happened, or that a      |
|                       |               | problem might occur in the near     |
|                       |               | future (e.g. 'disk space low'). The |
|                       |               | software is still working as        |
|                       |               | expected.                           |
+-----------------------+---------------+-------------------------------------+
| .. py:data:: ERROR    | 40            | Due to a more serious problem, the  |
|                       |               | software has not been able to       |
|                       |               | perform some function.              |
+-----------------------+---------------+-------------------------------------+
| .. py:data:: CRITICAL | 50            | A serious error, indicating that the|
|                       |               | program itself may be unable to     |
|                       |               | continue running.                   |
+-----------------------+---------------+-------------------------------------+


.. _handler:

Handler Objects
---------------

Handlers have the following attributes and methods. Note that :class:`Handler`
is never instantiated directly; this class acts as a base for more useful
subclasses. However, the :meth:`!__init__` method in subclasses needs to call
:meth:`Handler.__init__`.

.. class:: Handler

   .. method:: Handler.__init__(level=NOTSET)

      Initializes the :class:`Handler` instance by setting its level, setting the list
      of filters to the empty list and creating a lock (using :meth:`createLock`) for
      serializing access to an I/O mechanism.


   .. method:: Handler.createLock()

      Initializes a thread lock which can be used to serialize access to underlying
      I/O functionality which may not be threadsafe.


   .. method:: Handler.acquire()

      Acquires the thread lock created with :meth:`createLock`.


   .. method:: Handler.release()

      Releases the thread lock acquired with :meth:`acquire`.


   .. method:: Handler.setLevel(level)

      Sets the threshold for this handler to *level*. Logging messages which are
      less severe than *level* will be ignored. When a handler is created, the
      level is set to :const:`NOTSET` (which causes all messages to be
      processed).

      See :ref:`levels` for a list of levels.

      .. versionchanged:: 3.2
         The *level* parameter now accepts a string representation of the
         level such as 'INFO' as an alternative to the integer constants
         such as :const:`INFO`.


   .. method:: Handler.setFormatter(fmt)

      Sets the :class:`Formatter` for this handler to *fmt*.


   .. method:: Handler.addFilter(filter)

      Adds the specified filter *filter* to this handler.


   .. method:: Handler.removeFilter(filter)

      Removes the specified filter *filter* from this handler.


   .. method:: Handler.filter(record)

      Apply this handler's filters to the record and return ``True`` if the
      record is to be processed. The filters are consulted in turn, until one of
      them returns a false value. If none of them return a false value, the record
      will be emitted. If one returns a false value, the handler will not emit the
      record.


   .. method:: Handler.flush()

      Ensure all logging output has been flushed. This version does nothing and is
      intended to be implemented by subclasses.


   .. method:: Handler.close()

      Tidy up any resources used by the handler. This version does no output but
      removes the handler from an internal list of handlers which is closed when
      :func:`shutdown` is called. Subclasses should ensure that this gets called
      from overridden :meth:`close` methods.


   .. method:: Handler.handle(record)

      Conditionally emits the specified logging record, depending on filters which may
      have been added to the handler. Wraps the actual emission of the record with
      acquisition/release of the I/O thread lock.


   .. method:: Handler.handleError(record)

      This method should be called from handlers when an exception is encountered
      during an :meth:`emit` call. If the module-level attribute
      :data:`raiseExceptions` is ``False``, exceptions get silently ignored. This is
      what is mostly wanted for a logging system - most users will not care about
      errors in the logging system, they are more interested in application
      errors. You could, however, replace this with a custom handler if you wish.
      The specified record is the one which was being processed when the exception
      occurred. (The default value of :data:`raiseExceptions` is ``True``, as that is
      more useful during development).


   .. method:: Handler.format(record)

      Do formatting for a record - if a formatter is set, use it. Otherwise, use the
      default formatter for the module.


   .. method:: Handler.emit(record)

      Do whatever it takes to actually log the specified logging record. This version
      is intended to be implemented by subclasses and so raises a
      :exc:`NotImplementedError`.

      .. warning:: This method is called after a handler-level lock is acquired, which
         is released after this method returns. When you override this method, note
         that you should be careful when calling anything that invokes other parts of
         the logging API which might do locking, because that might result in a
         deadlock. Specifically:

         * Logging configuration APIs acquire the module-level lock, and then
           individual handler-level locks as those handlers are configured.

         * Many logging APIs lock the module-level lock. If such an API is called
           from this method, it could cause a deadlock if a configuration call is
           made on another thread, because that thread will try to acquire the
           module-level lock *before* the handler-level lock, whereas this thread
           tries to acquire the module-level lock *after* the handler-level lock
           (because in this method, the handler-level lock has already been acquired).

For a list of handlers included as standard, see :mod:`logging.handlers`.

.. _formatter-objects:

Formatter Objects
-----------------

.. currentmodule:: logging

.. class:: Formatter(fmt=None, datefmt=None, style='%', validate=True, *, defaults=None)

   Responsible for converting a :class:`LogRecord` to an output string
   to be interpreted by a human or external system.

   :param fmt: A format string in the given *style* for
       the logged output as a whole.
       The possible mapping keys are drawn from the :class:`LogRecord` object's
       :ref:`logrecord-attributes`.
       If not specified, ``'%(message)s'`` is used,
       which is just the logged message.
   :type fmt: str

   :param datefmt: A format string in the given *style* for
       the date/time portion of the logged output.
       If not specified, the default described in :meth:`formatTime` is used.
   :type datefmt: str

   :param style: Can be one of ``'%'``, ``'{'`` or ``'$'`` and determines
       how the format string will be merged with its data: using one of
       :ref:`old-string-formatting` (``%``), :meth:`str.format` (``{``)
       or :class:`string.Template` (``$``). This only applies to
       *fmt* and *datefmt* (e.g. ``'%(message)s'`` versus ``'{message}'``),
       not to the actual log messages passed to the logging methods.
       However, there are :ref:`other ways <formatting-styles>`
       to use ``{``- and ``$``-formatting for log messages.
   :type style: str

   :param validate: If ``True`` (the default), incorrect or mismatched
       *fmt* and *style* will raise a :exc:`ValueError`; for example,
       ``logging.Formatter('%(asctime)s - %(message)s', style='{')``.
   :type validate: bool

   :param defaults: A dictionary with default values to use in custom fields.
       For example,
       ``logging.Formatter('%(ip)s %(message)s', defaults={"ip": None})``
   :type defaults: dict[str, Any]

   .. versionchanged:: 3.2
      Added the *style* parameter.

   .. versionchanged:: 3.8
      Added the *validate* parameter.

   .. versionchanged:: 3.10
      Added the *defaults* parameter.


   .. method:: format(record)

      The record's attribute dictionary is used as the operand to a string
      formatting operation. Returns the resulting string. Before formatting the
      dictionary, a couple of preparatory steps are carried out. The *message*
      attribute of the record is computed using *msg* % *args*. If the
      formatting string contains ``'(asctime)'``, :meth:`formatTime` is called
      to format the event time. If there is exception information, it is
      formatted using :meth:`formatException` and appended to the message. Note
      that the formatted exception information is cached in attribute
      *exc_text*. This is useful because the exception information can be
      pickled and sent across the wire, but you should be careful if you have
      more than one :class:`Formatter` subclass which customizes the formatting
      of exception information. In this case, you will have to clear the cached
      value (by setting the *exc_text* attribute to ``None``) after a formatter
      has done its formatting, so that the next formatter to handle the event
      doesn't use the cached value, but recalculates it afresh.

      If stack information is available, it's appended after the exception
      information, using :meth:`formatStack` to transform it if necessary.


   .. method:: formatTime(record, datefmt=None)

