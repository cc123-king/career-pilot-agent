# Python 3.12.7 logging 原始文档摘录 3

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/logging.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

      This method should be called from :meth:`format` by a formatter which
      wants to make use of a formatted time. This method can be overridden in
      formatters to provide for any specific requirement, but the basic behavior
      is as follows: if *datefmt* (a string) is specified, it is used with
      :func:`time.strftime` to format the creation time of the
      record. Otherwise, the format '%Y-%m-%d %H:%M:%S,uuu' is used, where the
      uuu part is a millisecond value and the other letters are as per the
      :func:`time.strftime` documentation.  An example time in this format is
      ``2003-01-23 00:29:50,411``.  The resulting string is returned.

      This function uses a user-configurable function to convert the creation
      time to a tuple. By default, :func:`time.localtime` is used; to change
      this for a particular formatter instance, set the ``converter`` attribute
      to a function with the same signature as :func:`time.localtime` or
      :func:`time.gmtime`. To change it for all formatters, for example if you
      want all logging times to be shown in GMT, set the ``converter``
      attribute in the ``Formatter`` class.

      .. versionchanged:: 3.3
         Previously, the default format was hard-coded as in this example:
         ``2010-09-06 22:38:15,292`` where the part before the comma is
         handled by a strptime format string (``'%Y-%m-%d %H:%M:%S'``), and the
         part after the comma is a millisecond value. Because strptime does not
         have a format placeholder for milliseconds, the millisecond value is
         appended using another format string, ``'%s,%03d'`` --- and both of these
         format strings have been hardcoded into this method. With the change,
         these strings are defined as class-level attributes which can be
         overridden at the instance level when desired. The names of the
         attributes are ``default_time_format`` (for the strptime format string)
         and ``default_msec_format`` (for appending the millisecond value).

      .. versionchanged:: 3.9
         The ``default_msec_format`` can be ``None``.

   .. method:: formatException(exc_info)

      Formats the specified exception information (a standard exception tuple as
      returned by :func:`sys.exc_info`) as a string. This default implementation
      just uses :func:`traceback.print_exception`. The resulting string is
      returned.

   .. method:: formatStack(stack_info)

      Formats the specified stack information (a string as returned by
      :func:`traceback.print_stack`, but with the last newline removed) as a
      string. This default implementation just returns the input value.

.. class:: BufferingFormatter(linefmt=None)

   A base formatter class suitable for subclassing when you want to format a
   number of records. You can pass a :class:`Formatter` instance which you want
   to use to format each line (that corresponds to a single record). If not
   specified, the default formatter (which just outputs the event message) is
   used as the line formatter.

   .. method:: formatHeader(records)

      Return a header for a list of *records*. The base implementation just
      returns the empty string. You will need to override this method if you
      want specific behaviour, e.g. to show the count of records, a title or a
      separator line.

   .. method:: formatFooter(records)

      Return a footer for a list of *records*. The base implementation just
      returns the empty string. You will need to override this method if you
      want specific behaviour, e.g. to show the count of records or a separator
      line.

   .. method:: format(records)

      Return formatted text for a list of *records*. The base implementation
      just returns the empty string if there are no records; otherwise, it
      returns the concatenation of the header, each record formatted with the
      line formatter, and the footer.

.. _filter:

Filter Objects
--------------

``Filters`` can be used by ``Handlers`` and ``Loggers`` for more sophisticated
filtering than is provided by levels. The base filter class only allows events
which are below a certain point in the logger hierarchy. For example, a filter
initialized with 'A.B' will allow events logged by loggers 'A.B', 'A.B.C',
'A.B.C.D', 'A.B.D' etc. but not 'A.BB', 'B.A.B' etc. If initialized with the
empty string, all events are passed.


.. class:: Filter(name='')

   Returns an instance of the :class:`Filter` class. If *name* is specified, it
   names a logger which, together with its children, will have its events allowed
   through the filter. If *name* is the empty string, allows every event.


   .. method:: filter(record)

      Is the specified record to be logged? Returns false for no, true for
      yes. Filters can either modify log records in-place or return a completely
      different record instance which will replace the original
      log record in any future processing of the event.

Note that filters attached to handlers are consulted before an event is
emitted by the handler, whereas filters attached to loggers are consulted
whenever an event is logged (using :meth:`debug`, :meth:`info`,
etc.), before sending an event to handlers. This means that events which have
been generated by descendant loggers will not be filtered by a logger's filter
setting, unless the filter has also been applied to those descendant loggers.

You don't actually need to subclass ``Filter``: you can pass any instance
which has a ``filter`` method with the same semantics.

.. versionchanged:: 3.2
   You don't need to create specialized ``Filter`` classes, or use other
   classes with a ``filter`` method: you can use a function (or other
   callable) as a filter. The filtering logic will check to see if the filter
   object has a ``filter`` attribute: if it does, it's assumed to be a
   ``Filter`` and its :meth:`~Filter.filter` method is called. Otherwise, it's
   assumed to be a callable and called with the record as the single
   parameter. The returned value should conform to that returned by
   :meth:`~Filter.filter`.

.. versionchanged:: 3.12
   You can now return a :class:`LogRecord` instance from filters to replace
   the log record rather than modifying it in place. This allows filters attached to
   a :class:`Handler` to modify the log record before it is emitted, without
   having side effects on other handlers.

Although filters are used primarily to filter records based on more
sophisticated criteria than levels, they get to see every record which is
processed by the handler or logger they're attached to: this can be useful if
you want to do things like counting how many records were processed by a
particular logger or handler, or adding, changing or removing attributes in
the :class:`LogRecord` being processed. Obviously changing the LogRecord needs
to be done with some care, but it does allow the injection of contextual
information into logs (see :ref:`filters-contextual`).


.. _log-record:

LogRecord Objects
-----------------

:class:`LogRecord` instances are created automatically by the :class:`Logger`
every time something is logged, and can be created manually via
:func:`makeLogRecord` (for example, from a pickled event received over the
wire).


.. class:: LogRecord(name, level, pathname, lineno, msg, args, exc_info, func=None, sinfo=None)

   Contains all the information pertinent to the event being logged.

   The primary information is passed in *msg* and *args*,
   which are combined using ``msg % args`` to create
   the :attr:`!message` attribute of the record.

   :param name: The name of the logger used to log the event
      represented by this :class:`!LogRecord`.
      Note that the logger name in the :class:`!LogRecord`
      will always have this value,
      even though it may be emitted by a handler
      attached to a different (ancestor) logger.
   :type name: str

   :param level: The :ref:`numeric level <levels>` of the logging event
      (such as ``10`` for ``DEBUG``, ``20`` for ``INFO``, etc).
      Note that this is converted to *two* attributes of the LogRecord:
      :attr:`!levelno` for the numeric value
      and :attr:`!levelname` for the corresponding level name.
   :type level: int

   :param pathname: The full string path of the source file
      where the logging call was made.
   :type pathname: str

   :param lineno: The line number in the source file
      where the logging call was made.
   :type lineno: int

   :param msg: The event description message,
      which can be a %-format string with placeholders for variable data,
      or an arbitrary object (see :ref:`arbitrary-object-messages`).
   :type msg: typing.Any

   :param args: Variable data to merge into the *msg* argument
      to obtain the event description.
   :type args: tuple | dict[str, typing.Any]

   :param exc_info: An exception tuple with the current exception information,
      as returned by :func:`sys.exc_info`,
      or ``None`` if no exception information is available.
   :type exc_info: tuple[type[BaseException], BaseException, types.TracebackType] | None

   :param func: The name of the function or method
      from which the logging call was invoked.
   :type func: str | None

   :param sinfo: A text string representing stack information
      from the base of the stack in the current thread,
      up to the logging call.
   :type sinfo: str | None

   .. method:: getMessage()

      Returns the message for this :class:`LogRecord` instance after merging any
      user-supplied arguments with the message. If the user-supplied message
      argument to the logging call is not a string, :func:`str` is called on it to
      convert it to a string. This allows use of user-defined classes as
      messages, whose ``__str__`` method can return the actual format string to
      be used.

   .. versionchanged:: 3.2
      The creation of a :class:`LogRecord` has been made more configurable by
      providing a factory which is used to create the record. The factory can be
      set using :func:`getLogRecordFactory` and :func:`setLogRecordFactory`
      (see this for the factory's signature).

   This functionality can be used to inject your own values into a
   :class:`LogRecord` at creation time. You can use the following pattern::

      old_factory = logging.getLogRecordFactory()

      def record_factory(*args, **kwargs):
          record = old_factory(*args, **kwargs)
          record.custom_attribute = 0xdecafbad
          return record

      logging.setLogRecordFactory(record_factory)

   With this pattern, multiple factories could be chained, and as long
   as they don't overwrite each other's attributes or unintentionally
   overwrite the standard attributes listed above, there should be no
   surprises.


.. _logrecord-attributes:

LogRecord attributes
--------------------

The LogRecord has a number of attributes, most of which are derived from the
parameters to the constructor. (Note that the names do not always correspond
exactly between the LogRecord constructor parameters and the LogRecord
attributes.) These attributes can be used to merge data from the record into
the format string. The following table lists (in alphabetical order) the
attribute names, their meanings and the corresponding placeholder in a %-style
format string.

If you are using {}-formatting (:func:`str.format`), you can use
``{attrname}`` as the placeholder in the format string. If you are using
$-formatting (:class:`string.Template`), use the form ``${attrname}``. In
both cases, of course, replace ``attrname`` with the actual attribute name
you want to use.

In the case of {}-formatting, you can specify formatting flags by placing them
after the attribute name, separated from it with a colon. For example: a
placeholder of ``{msecs:03.0f}`` would format a millisecond value of ``4`` as
``004``. Refer to the :meth:`str.format` documentation for full details on
the options available to you.

