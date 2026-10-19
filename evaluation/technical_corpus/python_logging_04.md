# Python 3.12.7 logging 原始文档摘录 5

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/logging.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

   If *level* is one of the predefined levels :const:`CRITICAL`, :const:`ERROR`,
   :const:`WARNING`, :const:`INFO` or :const:`DEBUG` then you get the
   corresponding string. If you have associated levels with names using
   :func:`addLevelName` then the name you have associated with *level* is
   returned. If a numeric value corresponding to one of the defined levels is
   passed in, the corresponding string representation is returned.

   The *level* parameter also accepts a string representation of the level such
   as 'INFO'. In such cases, this functions returns the corresponding numeric
   value of the level.

   If no matching numeric or string value is passed in, the string
   'Level %s' % level is returned.

   .. note:: Levels are internally integers (as they need to be compared in the
      logging logic). This function is used to convert between an integer level
      and the level name displayed in the formatted log output by means of the
      ``%(levelname)s`` format specifier (see :ref:`logrecord-attributes`), and
      vice versa.

   .. versionchanged:: 3.4
      In Python versions earlier than 3.4, this function could also be passed a
      text level, and would return the corresponding numeric value of the level.
      This undocumented behaviour was considered a mistake, and was removed in
      Python 3.4, but reinstated in 3.4.2 due to retain backward compatibility.

.. function:: getHandlerByName(name)

   Returns a handler with the specified *name*, or ``None`` if there is no handler
   with that name.

   .. versionadded:: 3.12

.. function:: getHandlerNames()

   Returns an immutable set of all known handler names.

   .. versionadded:: 3.12

.. function:: makeLogRecord(attrdict)

   Creates and returns a new :class:`LogRecord` instance whose attributes are
   defined by *attrdict*. This function is useful for taking a pickled
   :class:`LogRecord` attribute dictionary, sent over a socket, and reconstituting
   it as a :class:`LogRecord` instance at the receiving end.


.. function:: basicConfig(**kwargs)

   Does basic configuration for the logging system by creating a
   :class:`StreamHandler` with a default :class:`Formatter` and adding it to the
   root logger. The functions :func:`debug`, :func:`info`, :func:`warning`,
   :func:`error` and :func:`critical` will call :func:`basicConfig` automatically
   if no handlers are defined for the root logger.

   This function does nothing if the root logger already has handlers
   configured, unless the keyword argument *force* is set to ``True``.

   .. note:: This function should be called from the main thread
      before other threads are started. In versions of Python prior to
      2.7.1 and 3.2, if this function is called from multiple threads,
      it is possible (in rare circumstances) that a handler will be added
      to the root logger more than once, leading to unexpected results
      such as messages being duplicated in the log.

   The following keyword arguments are supported.

   .. tabularcolumns:: |l|L|

   +--------------+---------------------------------------------+
   | Format       | Description                                 |
   +==============+=============================================+
   | *filename*   | Specifies that a :class:`FileHandler` be    |
   |              | created, using the specified filename,      |
   |              | rather than a :class:`StreamHandler`.       |
   +--------------+---------------------------------------------+
   | *filemode*   | If *filename* is specified, open the file   |
   |              | in this :ref:`mode <filemodes>`. Defaults   |
   |              | to ``'a'``.                                 |
   +--------------+---------------------------------------------+
   | *format*     | Use the specified format string for the     |
   |              | handler. Defaults to attributes             |
   |              | ``levelname``, ``name`` and ``message``     |
   |              | separated by colons.                        |
   +--------------+---------------------------------------------+
   | *datefmt*    | Use the specified date/time format, as      |
   |              | accepted by :func:`time.strftime`.          |
   +--------------+---------------------------------------------+
   | *style*      | If *format* is specified, use this style    |
   |              | for the format string. One of ``'%'``,      |
   |              | ``'{'`` or ``'$'`` for :ref:`printf-style   |
   |              | <old-string-formatting>`,                   |
   |              | :meth:`str.format` or                       |
   |              | :class:`string.Template` respectively.      |
   |              | Defaults to ``'%'``.                        |
   +--------------+---------------------------------------------+
   | *level*      | Set the root logger level to the specified  |
   |              | :ref:`level <levels>`.                      |
   +--------------+---------------------------------------------+
   | *stream*     | Use the specified stream to initialize the  |
   |              | :class:`StreamHandler`. Note that this      |
   |              | argument is incompatible with *filename* -  |
   |              | if both are present, a ``ValueError`` is    |
   |              | raised.                                     |
   +--------------+---------------------------------------------+
   | *handlers*   | If specified, this should be an iterable of |
   |              | already created handlers to add to the root |
   |              | logger. Any handlers which don't already    |
   |              | have a formatter set will be assigned the   |
   |              | default formatter created in this function. |
   |              | Note that this argument is incompatible     |
   |              | with *filename* or *stream* - if both       |
   |              | are present, a ``ValueError`` is raised.    |
   +--------------+---------------------------------------------+
   | *force*      | If this keyword argument is specified as    |
   |              | true, any existing handlers attached to the |
   |              | root logger are removed and closed, before  |
   |              | carrying out the configuration as specified |
   |              | by the other arguments.                     |
   +--------------+---------------------------------------------+
   | *encoding*   | If this keyword argument is specified along |
   |              | with *filename*, its value is used when the |
   |              | :class:`FileHandler` is created, and thus   |
   |              | used when opening the output file.          |
   +--------------+---------------------------------------------+
   | *errors*     | If this keyword argument is specified along |
   |              | with *filename*, its value is used when the |
   |              | :class:`FileHandler` is created, and thus   |
   |              | used when opening the output file. If not   |
   |              | specified, the value 'backslashreplace' is  |
   |              | used. Note that if ``None`` is specified,   |
   |              | it will be passed as such to :func:`open`,  |
   |              | which means that it will be treated the     |
   |              | same as passing 'errors'.                   |
   +--------------+---------------------------------------------+

   .. versionchanged:: 3.2
      The *style* argument was added.

   .. versionchanged:: 3.3
      The *handlers* argument was added. Additional checks were added to
      catch situations where incompatible arguments are specified (e.g.
      *handlers* together with *stream* or *filename*, or *stream*
      together with *filename*).

   .. versionchanged:: 3.8
      The *force* argument was added.

   .. versionchanged:: 3.9
      The *encoding* and *errors* arguments were added.

.. function:: shutdown()

   Informs the logging system to perform an orderly shutdown by flushing and
   closing all handlers. This should be called at application exit and no
   further use of the logging system should be made after this call.

   When the logging module is imported, it registers this function as an exit
   handler (see :mod:`atexit`), so normally there's no need to do that
   manually.


.. function:: setLoggerClass(klass)

   Tells the logging system to use the class *klass* when instantiating a logger.
   The class should define :meth:`!__init__` such that only a name argument is
   required, and the :meth:`!__init__` should call :meth:`!Logger.__init__`. This
   function is typically called before any loggers are instantiated by applications
   which need to use custom logger behavior. After this call, as at any other
   time, do not instantiate loggers directly using the subclass: continue to use
   the :func:`logging.getLogger` API to get your loggers.


.. function:: setLogRecordFactory(factory)

   Set a callable which is used to create a :class:`LogRecord`.

   :param factory: The factory callable to be used to instantiate a log record.

   .. versionadded:: 3.2
      This function has been provided, along with :func:`getLogRecordFactory`, to
      allow developers more control over how the :class:`LogRecord` representing
      a logging event is constructed.

   The factory has the following signature:

   ``factory(name, level, fn, lno, msg, args, exc_info, func=None, sinfo=None, **kwargs)``

      :name: The logger name.
      :level: The logging level (numeric).
      :fn: The full pathname of the file where the logging call was made.
      :lno: The line number in the file where the logging call was made.
      :msg: The logging message.
      :args: The arguments for the logging message.
      :exc_info: An exception tuple, or ``None``.
      :func: The name of the function or method which invoked the logging
             call.
      :sinfo: A stack traceback such as is provided by
              :func:`traceback.print_stack`, showing the call hierarchy.
      :kwargs: Additional keyword arguments.


Module-Level Attributes
-----------------------

.. attribute:: lastResort

   A "handler of last resort" is available through this attribute. This
   is a :class:`StreamHandler` writing to ``sys.stderr`` with a level of
   ``WARNING``, and is used to handle logging events in the absence of any
   logging configuration. The end result is to just print the message to
   ``sys.stderr``. This replaces the earlier error message saying that
   "no handlers could be found for logger XYZ". If you need the earlier
   behaviour for some reason, ``lastResort`` can be set to ``None``.

   .. versionadded:: 3.2

.. attribute:: raiseExceptions

   Used to see if exceptions during handling should be propagated.

   Default: ``True``.

   If :data:`raiseExceptions` is ``False``,
   exceptions get silently ignored. This is what is mostly wanted
   for a logging system - most users will not care about errors in
   the logging system, they are more interested in application errors.


Integration with the warnings module
------------------------------------

The :func:`captureWarnings` function can be used to integrate :mod:`logging`
with the :mod:`warnings` module.

.. function:: captureWarnings(capture)

   This function is used to turn the capture of warnings by logging on and
   off.

   If *capture* is ``True``, warnings issued by the :mod:`warnings` module will
   be redirected to the logging system. Specifically, a warning will be
   formatted using :func:`warnings.formatwarning` and the resulting string
   logged to a logger named ``'py.warnings'`` with a severity of :const:`WARNING`.

   If *capture* is ``False``, the redirection of warnings to the logging system
   will stop, and warnings will be redirected to their original destinations
   (i.e. those in effect before ``captureWarnings(True)`` was called).


.. seealso::

   Module :mod:`logging.config`
      Configuration API for the logging module.

   Module :mod:`logging.handlers`
      Useful handlers included with the logging module.

   :pep:`282` - A Logging System
      The proposal which described this feature for inclusion in the Python standard
      library.

   `Original Python logging package <https://old.red-dove.com/python_logging.html>`_
      This is the original source for the :mod:`logging` package.  The version of the
      package available from this site is suitable for use with Python 1.5.2, 2.1.x
      and 2.2.x, which do not include the :mod:`logging` package in the standard
      library.


