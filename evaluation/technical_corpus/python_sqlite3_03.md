# Python 3.12.7 sqlite3 原始文档摘录 4

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/sqlite3.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

      ``True`` if a transaction is active (there are uncommitted changes),
      ``False`` otherwise.

      .. versionadded:: 3.2

   .. attribute:: isolation_level

      Controls the :ref:`legacy transaction handling mode
      <sqlite3-transaction-control-isolation-level>` of :mod:`!sqlite3`.
      If set to ``None``, transactions are never implicitly opened.
      If set to one of ``"DEFERRED"``, ``"IMMEDIATE"``, or ``"EXCLUSIVE"``,
      corresponding to the underlying `SQLite transaction behaviour`_,
      :ref:`implicit transaction management
      <sqlite3-transaction-control-isolation-level>` is performed.

      If not overridden by the *isolation_level* parameter of :func:`connect`,
      the default is ``""``, which is an alias for ``"DEFERRED"``.

      .. note::

         Using :attr:`autocommit` to control transaction handling is
         recommended over using :attr:`!isolation_level`.
         :attr:`!isolation_level` has no effect unless :attr:`autocommit` is
         set to :data:`LEGACY_TRANSACTION_CONTROL` (the default).

   .. attribute:: row_factory

      The initial :attr:`~Cursor.row_factory`
      for :class:`Cursor` objects created from this connection.
      Assigning to this attribute does not affect the :attr:`!row_factory`
      of existing cursors belonging to this connection, only new ones.
      Is ``None`` by default,
      meaning each row is returned as a :class:`tuple`.

      See :ref:`sqlite3-howto-row-factory` for more details.

   .. attribute:: text_factory

      A :term:`callable` that accepts a :class:`bytes` parameter
      and returns a text representation of it.
      The callable is invoked for SQLite values with the ``TEXT`` data type.
      By default, this attribute is set to :class:`str`.

      See :ref:`sqlite3-howto-encoding` for more details.

   .. attribute:: total_changes

      Return the total number of database rows that have been modified, inserted, or
      deleted since the database connection was opened.


.. _sqlite3-cursor-objects:

Cursor objects
^^^^^^^^^^^^^^

   A ``Cursor`` object represents a `database cursor`_
   which is used to execute SQL statements,
   and manage the context of a fetch operation.
   Cursors are created using :meth:`Connection.cursor`,
   or by using any of the :ref:`connection shortcut methods
   <sqlite3-connection-shortcuts>`.

   Cursor objects are :term:`iterators <iterator>`,
   meaning that if you :meth:`~Cursor.execute` a ``SELECT`` query,
   you can simply iterate over the cursor to fetch the resulting rows:

   .. testsetup:: sqlite3.cursor

      import sqlite3
      con = sqlite3.connect(":memory:", isolation_level=None)
      cur = con.execute("CREATE TABLE data(t)")
      cur.execute("INSERT INTO data VALUES(1)")

   .. testcode:: sqlite3.cursor

      for row in cur.execute("SELECT t FROM data"):
          print(row)

   .. testoutput:: sqlite3.cursor
      :hide:

      (1,)

   .. _database cursor: https://en.wikipedia.org/wiki/Cursor_(databases)

.. class:: Cursor

   A :class:`Cursor` instance has the following attributes and methods.

   .. index:: single: ? (question mark); in SQL statements
   .. index:: single: : (colon); in SQL statements

   .. method:: execute(sql, parameters=(), /)

      Execute a single SQL statement,
      optionally binding Python values using
      :ref:`placeholders <sqlite3-placeholders>`.

      :param str sql:
         A single SQL statement.

      :param parameters:
         Python values to bind to placeholders in *sql*.
         A :class:`!dict` if named placeholders are used.
         A :term:`!sequence` if unnamed placeholders are used.
         See :ref:`sqlite3-placeholders`.
      :type parameters: :class:`dict` | :term:`sequence`

      :raises ProgrammingError:
         If *sql* contains more than one SQL statement.

      If :attr:`~Connection.autocommit` is
      :data:`LEGACY_TRANSACTION_CONTROL`,
      :attr:`~Connection.isolation_level` is not ``None``,
      *sql* is an ``INSERT``, ``UPDATE``, ``DELETE``, or ``REPLACE`` statement,
      and there is no open transaction,
      a transaction is implicitly opened before executing *sql*.

      .. deprecated-removed:: 3.12 3.14

         :exc:`DeprecationWarning` is emitted if
         :ref:`named placeholders <sqlite3-placeholders>` are used
         and *parameters* is a sequence instead of a :class:`dict`.
         Starting with Python 3.14, :exc:`ProgrammingError` will
         be raised instead.

      Use :meth:`executescript` to execute multiple SQL statements.

   .. method:: executemany(sql, parameters, /)

      For every item in *parameters*,
      repeatedly execute the :ref:`parameterized <sqlite3-placeholders>`
      :abbr:`DML (Data Manipulation Language)` SQL statement *sql*.

      Uses the same implicit transaction handling as :meth:`~Cursor.execute`.

      :param str sql:
         A single SQL DML statement.

      :param parameters:
         An :term:`!iterable` of parameters to bind with
         the placeholders in *sql*.
         See :ref:`sqlite3-placeholders`.
      :type parameters: :term:`iterable`

      :raises ProgrammingError:
         If *sql* contains more than one SQL statement,
         or is not a DML statement.

      Example:

      .. testcode:: sqlite3.cursor

         rows = [
             ("row1",),
             ("row2",),
         ]
         # cur is an sqlite3.Cursor object
         cur.executemany("INSERT INTO data VALUES(?)", rows)

      .. testcleanup:: sqlite3.cursor

         con.close()

      .. note::

         Any resulting rows are discarded,
         including DML statements with `RETURNING clauses`_.

      .. _RETURNING clauses: https://www.sqlite.org/lang_returning.html

      .. deprecated-removed:: 3.12 3.14

         :exc:`DeprecationWarning` is emitted if
         :ref:`named placeholders <sqlite3-placeholders>` are used
         and the items in *parameters* are sequences
         instead of :class:`dict`\s.
         Starting with Python 3.14, :exc:`ProgrammingError` will
         be raised instead.

   .. method:: executescript(sql_script, /)

      Execute the SQL statements in *sql_script*.
      If the :attr:`~Connection.autocommit` is
      :data:`LEGACY_TRANSACTION_CONTROL`
      and there is a pending transaction,
      an implicit ``COMMIT`` statement is executed first.
      No other implicit transaction control is performed;
      any transaction control must be added to *sql_script*.

      *sql_script* must be a :class:`string <str>`.

      Example:

      .. testcode:: sqlite3.cursor

         # cur is an sqlite3.Cursor object
         cur.executescript("""
             BEGIN;
             CREATE TABLE person(firstname, lastname, age);
             CREATE TABLE book(title, author, published);
             CREATE TABLE publisher(name, address);
             COMMIT;
         """)

   .. method:: fetchone()

      If :attr:`~Cursor.row_factory` is ``None``,
      return the next row query result set as a :class:`tuple`.
      Else, pass it to the row factory and return its result.
      Return ``None`` if no more data is available.


   .. method:: fetchmany(size=cursor.arraysize)

      Return the next set of rows of a query result as a :class:`list`.
      Return an empty list if no more rows are available.

      The number of rows to fetch per call is specified by the *size* parameter.
      If *size* is not given, :attr:`arraysize` determines the number of rows
      to be fetched.
      If fewer than *size* rows are available,
      as many rows as are available are returned.

      Note there are performance considerations involved with the *size* parameter.
      For optimal performance, it is usually best to use the arraysize attribute.
      If the *size* parameter is used, then it is best for it to retain the same
      value from one :meth:`fetchmany` call to the next.

   .. method:: fetchall()

      Return all (remaining) rows of a query result as a :class:`list`.
      Return an empty list if no rows are available.
      Note that the :attr:`arraysize` attribute can affect the performance of
      this operation.

   .. method:: close()

      Close the cursor now (rather than whenever ``__del__`` is called).

      The cursor will be unusable from this point forward; a :exc:`ProgrammingError`
      exception will be raised if any operation is attempted with the cursor.

   .. method:: setinputsizes(sizes, /)

      Required by the DB-API. Does nothing in :mod:`!sqlite3`.

   .. method:: setoutputsize(size, column=None, /)

      Required by the DB-API. Does nothing in :mod:`!sqlite3`.

   .. attribute:: arraysize

      Read/write attribute that controls the number of rows returned by :meth:`fetchmany`.
      The default value is 1 which means a single row would be fetched per call.

   .. attribute:: connection

      Read-only attribute that provides the SQLite database :class:`Connection`
      belonging to the cursor.  A :class:`Cursor` object created by
      calling :meth:`con.cursor() <Connection.cursor>` will have a
      :attr:`connection` attribute that refers to *con*:

      .. doctest::

         >>> con = sqlite3.connect(":memory:")
         >>> cur = con.cursor()
         >>> cur.connection == con
         True
         >>> con.close()

   .. attribute:: description

      Read-only attribute that provides the column names of the last query. To
      remain compatible with the Python DB API, it returns a 7-tuple for each
      column where the last six items of each tuple are ``None``.

      It is set for ``SELECT`` statements without any matching rows as well.

   .. attribute:: lastrowid

      Read-only attribute that provides the row id of the last inserted row. It
      is only updated after successful ``INSERT`` or ``REPLACE`` statements
      using the :meth:`execute` method.  For other statements, after
      :meth:`executemany` or :meth:`executescript`, or if the insertion failed,
      the value of ``lastrowid`` is left unchanged.  The initial value of
      ``lastrowid`` is ``None``.

      .. note::
         Inserts into ``WITHOUT ROWID`` tables are not recorded.

      .. versionchanged:: 3.6
         Added support for the ``REPLACE`` statement.

   .. attribute:: rowcount

      Read-only attribute that provides the number of modified rows for
      ``INSERT``, ``UPDATE``, ``DELETE``, and ``REPLACE`` statements;
      is ``-1`` for other statements,
      including :abbr:`CTE (Common Table Expression)` queries.
      It is only updated by the :meth:`execute` and :meth:`executemany` methods,
      after the statement has run to completion.
      This means that any resulting rows must be fetched in order for
      :attr:`!rowcount` to be updated.

   .. attribute:: row_factory

      Control how a row fetched from this :class:`!Cursor` is represented.
      If ``None``, a row is represented as a :class:`tuple`.
      Can be set to the included :class:`sqlite3.Row`;
      or a :term:`callable` that accepts two arguments,
      a :class:`Cursor` object and the :class:`!tuple` of row values,
      and returns a custom object representing an SQLite row.

      Defaults to what :attr:`Connection.row_factory` was set to
      when the :class:`!Cursor` was created.
      Assigning to this attribute does not affect
      :attr:`Connection.row_factory` of the parent connection.

      See :ref:`sqlite3-howto-row-factory` for more details.


.. The sqlite3.Row example used to be a how-to. It has now been incorporated
   into the Row reference. We keep the anchor here in order not to break
   existing links.

.. _sqlite3-columns-by-name:
.. _sqlite3-row-objects:

Row objects
^^^^^^^^^^^

.. class:: Row

   A :class:`!Row` instance serves as a highly optimized
   :attr:`~Connection.row_factory` for :class:`Connection` objects.
   It supports iteration, equality testing, :func:`len`,
   and :term:`mapping` access by column name and index.

   Two :class:`!Row` objects compare equal
   if they have identical column names and values.

   See :ref:`sqlite3-howto-row-factory` for more details.

   .. method:: keys

      Return a :class:`list` of column names as :class:`strings <str>`.
      Immediately after a query,
      it is the first member of each tuple in :attr:`Cursor.description`.

   .. versionchanged:: 3.5
      Added support of slicing.


.. _sqlite3-blob-objects:

Blob objects
^^^^^^^^^^^^

.. class:: Blob

   .. versionadded:: 3.11

   A :class:`Blob` instance is a :term:`file-like object`
   that can read and write data in an SQLite :abbr:`BLOB (Binary Large OBject)`.
   Call :func:`len(blob) <len>` to get the size (number of bytes) of the blob.
   Use indices and :term:`slices <slice>` for direct access to the blob data.

   Use the :class:`Blob` as a :term:`context manager` to ensure that the blob
   handle is closed after use.

   .. testcode::

      con = sqlite3.connect(":memory:")
      con.execute("CREATE TABLE test(blob_col blob)")
      con.execute("INSERT INTO test(blob_col) VALUES(zeroblob(13))")

      # Write to our blob, using two write operations:
      with con.blobopen("test", "blob_col", 1) as blob:
          blob.write(b"hello, ")
          blob.write(b"world.")
          # Modify the first and last bytes of our blob
          blob[0] = ord("H")
          blob[-1] = ord("!")

      # Read the contents of our blob
      with con.blobopen("test", "blob_col", 1) as blob:
          greeting = blob.read()

      print(greeting)  # outputs "b'Hello, world!'"
      con.close()

   .. testoutput::
      :hide:

      b'Hello, world!'

   .. method:: close()

      Close the blob.

      The blob will be unusable from this point onward.  An
      :class:`~sqlite3.Error` (or subclass) exception will be raised if any
      further operation is attempted with the blob.

   .. method:: read(length=-1, /)

      Read *length* bytes of data from the blob at the current offset position.
      If the end of the blob is reached, the data up to
      :abbr:`EOF (End of File)` will be returned.  When *length* is not
      specified, or is negative, :meth:`~Blob.read` will read until the end of
      the blob.

   .. method:: write(data, /)

      Write *data* to the blob at the current offset.  This function cannot
      change the blob length.  Writing beyond the end of the blob will raise
      :exc:`ValueError`.

   .. method:: tell()

      Return the current access position of the blob.

   .. method:: seek(offset, origin=os.SEEK_SET, /)

      Set the current access position of the blob to *offset*.  The *origin*
      argument defaults to :const:`os.SEEK_SET` (absolute blob positioning).
      Other values for *origin* are :const:`os.SEEK_CUR` (seek relative to the
      current position) and :const:`os.SEEK_END` (seek relative to the blob’s
      end).


PrepareProtocol objects
^^^^^^^^^^^^^^^^^^^^^^^

.. class:: PrepareProtocol

   The PrepareProtocol type's single purpose is to act as a :pep:`246` style
   adaption protocol for objects that can :ref:`adapt themselves
   <sqlite3-conform>` to :ref:`native SQLite types <sqlite3-types>`.


.. _sqlite3-exceptions:

Exceptions
^^^^^^^^^^

The exception hierarchy is defined by the DB-API 2.0 (:pep:`249`).

.. exception:: Warning

   This exception is not currently raised by the :mod:`!sqlite3` module,
   but may be raised by applications using :mod:`!sqlite3`,
   for example if a user-defined function truncates data while inserting.
   ``Warning`` is a subclass of :exc:`Exception`.

.. exception:: Error

   The base class of the other exceptions in this module.
   Use this to catch all errors with one single :keyword:`except` statement.
   ``Error`` is a subclass of :exc:`Exception`.

   If the exception originated from within the SQLite library,
   the following two attributes are added to the exception:

   .. attribute:: sqlite_errorcode

