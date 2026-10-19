# Python 3.12.7 logging 原始文档摘录 4

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/logging.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

+----------------+-------------------------+-----------------------------------------------+
| Attribute name | Format                  | Description                                   |
+================+=========================+===============================================+
| args           | You shouldn't need to   | The tuple of arguments merged into ``msg`` to |
|                | format this yourself.   | produce ``message``, or a dict whose values   |
|                |                         | are used for the merge (when there is only one|
|                |                         | argument, and it is a dictionary).            |
+----------------+-------------------------+-----------------------------------------------+
| asctime        | ``%(asctime)s``         | Human-readable time when the                  |
|                |                         | :class:`LogRecord` was created.  By default   |
|                |                         | this is of the form '2003-07-08 16:49:45,896' |
|                |                         | (the numbers after the comma are millisecond  |
|                |                         | portion of the time).                         |
+----------------+-------------------------+-----------------------------------------------+
| created        | ``%(created)f``         | Time when the :class:`LogRecord` was created  |
|                |                         | (as returned by :func:`time.time`).           |
+----------------+-------------------------+-----------------------------------------------+
| exc_info       | You shouldn't need to   | Exception tuple (à la ``sys.exc_info``) or,   |
|                | format this yourself.   | if no exception has occurred, ``None``.       |
+----------------+-------------------------+-----------------------------------------------+
| filename       | ``%(filename)s``        | Filename portion of ``pathname``.             |
+----------------+-------------------------+-----------------------------------------------+
| funcName       | ``%(funcName)s``        | Name of function containing the logging call. |
+----------------+-------------------------+-----------------------------------------------+
| levelname      | ``%(levelname)s``       | Text logging level for the message            |
|                |                         | (``'DEBUG'``, ``'INFO'``, ``'WARNING'``,      |
|                |                         | ``'ERROR'``, ``'CRITICAL'``).                 |
+----------------+-------------------------+-----------------------------------------------+
| levelno        | ``%(levelno)s``         | Numeric logging level for the message         |
|                |                         | (:const:`DEBUG`, :const:`INFO`,               |
|                |                         | :const:`WARNING`, :const:`ERROR`,             |
|                |                         | :const:`CRITICAL`).                           |
+----------------+-------------------------+-----------------------------------------------+
| lineno         | ``%(lineno)d``          | Source line number where the logging call was |
|                |                         | issued (if available).                        |
+----------------+-------------------------+-----------------------------------------------+
| message        | ``%(message)s``         | The logged message, computed as ``msg %       |
|                |                         | args``. This is set when                      |
|                |                         | :meth:`Formatter.format` is invoked.          |
+----------------+-------------------------+-----------------------------------------------+
| module         | ``%(module)s``          | Module (name portion of ``filename``).        |
+----------------+-------------------------+-----------------------------------------------+
| msecs          | ``%(msecs)d``           | Millisecond portion of the time when the      |
|                |                         | :class:`LogRecord` was created.               |
+----------------+-------------------------+-----------------------------------------------+
| msg            | You shouldn't need to   | The format string passed in the original      |
|                | format this yourself.   | logging call. Merged with ``args`` to         |
|                |                         | produce ``message``, or an arbitrary object   |
|                |                         | (see :ref:`arbitrary-object-messages`).       |
+----------------+-------------------------+-----------------------------------------------+
| name           | ``%(name)s``            | Name of the logger used to log the call.      |
+----------------+-------------------------+-----------------------------------------------+
| pathname       | ``%(pathname)s``        | Full pathname of the source file where the    |
|                |                         | logging call was issued (if available).       |
+----------------+-------------------------+-----------------------------------------------+
| process        | ``%(process)d``         | Process ID (if available).                    |
+----------------+-------------------------+-----------------------------------------------+
| processName    | ``%(processName)s``     | Process name (if available).                  |
+----------------+-------------------------+-----------------------------------------------+
| relativeCreated| ``%(relativeCreated)d`` | Time in milliseconds when the LogRecord was   |
|                |                         | created, relative to the time the logging     |
|                |                         | module was loaded.                            |
+----------------+-------------------------+-----------------------------------------------+
| stack_info     | You shouldn't need to   | Stack frame information (where available)     |
|                | format this yourself.   | from the bottom of the stack in the current   |
|                |                         | thread, up to and including the stack frame   |
|                |                         | of the logging call which resulted in the     |
|                |                         | creation of this record.                      |
+----------------+-------------------------+-----------------------------------------------+
| thread         | ``%(thread)d``          | Thread ID (if available).                     |
+----------------+-------------------------+-----------------------------------------------+
| threadName     | ``%(threadName)s``      | Thread name (if available).                   |
+----------------+-------------------------+-----------------------------------------------+
| taskName       | ``%(taskName)s``        | :class:`asyncio.Task` name (if available).    |
+----------------+-------------------------+-----------------------------------------------+

.. versionchanged:: 3.1
   *processName* was added.

.. versionchanged:: 3.12
   *taskName* was added.

.. _logger-adapter:

LoggerAdapter Objects
---------------------

:class:`LoggerAdapter` instances are used to conveniently pass contextual
information into logging calls. For a usage example, see the section on
:ref:`adding contextual information to your logging output <context-info>`.

.. class:: LoggerAdapter(logger, extra)

   Returns an instance of :class:`LoggerAdapter` initialized with an
   underlying :class:`Logger` instance and a dict-like object.

   .. method:: process(msg, kwargs)

      Modifies the message and/or keyword arguments passed to a logging call in
      order to insert contextual information. This implementation takes the object
      passed as *extra* to the constructor and adds it to *kwargs* using key
      'extra'. The return value is a (*msg*, *kwargs*) tuple which has the
      (possibly modified) versions of the arguments passed in.

   .. attribute:: manager

      Delegates to the underlying :attr:`!manager` on *logger*.

   .. attribute:: _log

      Delegates to the underlying :meth:`!_log` method on *logger*.

   In addition to the above, :class:`LoggerAdapter` supports the following
   methods of :class:`Logger`: :meth:`~Logger.debug`, :meth:`~Logger.info`,
   :meth:`~Logger.warning`, :meth:`~Logger.error`, :meth:`~Logger.exception`,
   :meth:`~Logger.critical`, :meth:`~Logger.log`, :meth:`~Logger.isEnabledFor`,
   :meth:`~Logger.getEffectiveLevel`, :meth:`~Logger.setLevel` and
   :meth:`~Logger.hasHandlers`. These methods have the same signatures as their
   counterparts in :class:`Logger`, so you can use the two types of instances
   interchangeably.

   .. versionchanged:: 3.2

      The :meth:`~Logger.isEnabledFor`, :meth:`~Logger.getEffectiveLevel`,
      :meth:`~Logger.setLevel` and :meth:`~Logger.hasHandlers` methods were added
      to :class:`LoggerAdapter`.  These methods delegate to the underlying logger.

   .. versionchanged:: 3.6

      Attribute :attr:`!manager` and method :meth:`!_log` were added, which
      delegate to the underlying logger and allow adapters to be nested.


Thread Safety
-------------

The logging module is intended to be thread-safe without any special work
needing to be done by its clients. It achieves this though using threading
locks; there is one lock to serialize access to the module's shared data, and
each handler also creates a lock to serialize access to its underlying I/O.

If you are implementing asynchronous signal handlers using the :mod:`signal`
module, you may not be able to use logging from within such handlers. This is
because lock implementations in the :mod:`threading` module are not always
re-entrant, and so cannot be invoked from such signal handlers.


Module-Level Functions
----------------------

In addition to the classes described above, there are a number of module-level
functions.


.. function:: getLogger(name=None)

   Return a logger with the specified name or, if name is ``None``, return the
   root logger of the hierarchy. If specified, the name is typically a
   dot-separated hierarchical name like *'a'*, *'a.b'* or *'a.b.c.d'*. Choice
   of these names is entirely up to the developer who is using logging, though
   it is recommended that ``__name__`` be used unless you have a specific
   reason for not doing that, as mentioned in :ref:`logger`.

   All calls to this function with a given name return the same logger instance.
   This means that logger instances never need to be passed between different parts
   of an application.


.. function:: getLoggerClass()

   Return either the standard :class:`Logger` class, or the last class passed to
   :func:`setLoggerClass`. This function may be called from within a new class
   definition, to ensure that installing a customized :class:`Logger` class will
   not undo customizations already applied by other code. For example::

      class MyLogger(logging.getLoggerClass()):
          # ... override behaviour here


.. function:: getLogRecordFactory()

   Return a callable which is used to create a :class:`LogRecord`.

   .. versionadded:: 3.2
      This function has been provided, along with :func:`setLogRecordFactory`,
      to allow developers more control over how the :class:`LogRecord`
      representing a logging event is constructed.

   See :func:`setLogRecordFactory` for more information about the how the
   factory is called.

.. function:: debug(msg, *args, **kwargs)

   This is a convenience function that calls :meth:`Logger.debug`, on the root
   logger. The handling of the arguments is in every way identical
   to what is described in that method.

   The only difference is that if the root logger has no handlers, then
   :func:`basicConfig` is called, prior to calling ``debug`` on the root logger.

   For very short scripts or quick demonstrations of ``logging`` facilities,
   ``debug`` and the other module-level functions may be convenient. However,
   most programs will want to carefully and explicitly control the logging
   configuration, and should therefore prefer creating a module-level logger and
   calling :meth:`Logger.debug` (or other level-specific methods) on it, as
   described at the beginnning of this documentation.


.. function:: info(msg, *args, **kwargs)

   Logs a message with level :const:`INFO` on the root logger. The arguments and behavior
   are otherwise the same as for :func:`debug`.


.. function:: warning(msg, *args, **kwargs)

   Logs a message with level :const:`WARNING` on the root logger. The arguments and behavior
   are otherwise the same as for :func:`debug`.

   .. note:: There is an obsolete function ``warn`` which is functionally
      identical to ``warning``. As ``warn`` is deprecated, please do not use
      it - use ``warning`` instead.


.. function:: error(msg, *args, **kwargs)

   Logs a message with level :const:`ERROR` on the root logger. The arguments and behavior
   are otherwise the same as for :func:`debug`.


.. function:: critical(msg, *args, **kwargs)

   Logs a message with level :const:`CRITICAL` on the root logger. The arguments and behavior
   are otherwise the same as for :func:`debug`.


.. function:: exception(msg, *args, **kwargs)

   Logs a message with level :const:`ERROR` on the root logger. The arguments and behavior
   are otherwise the same as for :func:`debug`. Exception info is added to the logging
   message. This function should only be called from an exception handler.

.. function:: log(level, msg, *args, **kwargs)

   Logs a message with level *level* on the root logger. The arguments and behavior
   are otherwise the same as for :func:`debug`.

.. function:: disable(level=CRITICAL)

   Provides an overriding level *level* for all loggers which takes precedence over
   the logger's own level. When the need arises to temporarily throttle logging
   output down across the whole application, this function can be useful. Its
   effect is to disable all logging calls of severity *level* and below, so that
   if you call it with a value of INFO, then all INFO and DEBUG events would be
   discarded, whereas those of severity WARNING and above would be processed
   according to the logger's effective level. If
   ``logging.disable(logging.NOTSET)`` is called, it effectively removes this
   overriding level, so that logging output again depends on the effective
   levels of individual loggers.

   Note that if you have defined any custom logging level higher than
   ``CRITICAL`` (this is not recommended), you won't be able to rely on the
   default value for the *level* parameter, but will have to explicitly supply a
   suitable value.

   .. versionchanged:: 3.7
      The *level* parameter was defaulted to level ``CRITICAL``. See
      :issue:`28524` for more information about this change.

.. function:: addLevelName(level, levelName)

   Associates level *level* with text *levelName* in an internal dictionary, which is
   used to map numeric levels to a textual representation, for example when a
   :class:`Formatter` formats a message. This function can also be used to define
   your own levels. The only constraints are that all levels used must be
   registered using this function, levels should be positive integers and they
   should increase in increasing order of severity.

   .. note:: If you are thinking of defining your own levels, please see the
      section on :ref:`custom-levels`.

.. function:: getLevelNamesMapping()

   Returns a mapping from level names to their corresponding logging levels. For example, the
   string "CRITICAL" maps to :const:`CRITICAL`. The returned mapping is copied from an internal
   mapping on each call to this function.

   .. versionadded:: 3.11

.. function:: getLevelName(level)

   Returns the textual or numeric representation of logging level *level*.

