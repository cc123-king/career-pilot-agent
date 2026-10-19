# Python 3.12.7 sqlite3 原始文档摘录 1

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/sqlite3.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

:mod:`!sqlite3` --- DB-API 2.0 interface for SQLite databases
=============================================================

.. module:: sqlite3
   :synopsis: A DB-API 2.0 implementation using SQLite 3.x.

.. sectionauthor:: Gerhard Häring <gh@ghaering.de>

**Source code:** :source:`Lib/sqlite3/`

.. Make sure we always doctest the tutorial with an empty database.

.. testsetup::

   import sqlite3
   src = sqlite3.connect(":memory:", isolation_level=None)
   dst = sqlite3.connect("tutorial.db", isolation_level=None)
   src.backup(dst)
   src.close()
   dst.close()
   del src, dst

.. _sqlite3-intro:

SQLite is a C library that provides a lightweight disk-based database that
doesn't require a separate server process and allows accessing the database
using a nonstandard variant of the SQL query language. Some applications can use
SQLite for internal data storage.  It's also possible to prototype an
application using SQLite and then port the code to a larger database such as
PostgreSQL or Oracle.

The :mod:`!sqlite3` module was written by Gerhard Häring.  It provides an SQL interface
compliant with the DB-API 2.0 specification described by :pep:`249`, and
requires SQLite 3.7.15 or newer.

This document includes four main sections:

* :ref:`sqlite3-tutorial` teaches how to use the :mod:`!sqlite3` module.
* :ref:`sqlite3-reference` describes the classes and functions this module
  defines.
* :ref:`sqlite3-howtos` details how to handle specific tasks.
* :ref:`sqlite3-explanation` provides in-depth background on
  transaction control.

.. seealso::

   https://www.sqlite.org
      The SQLite web page; the documentation describes the syntax and the
      available data types for the supported SQL dialect.

   https://www.w3schools.com/sql/
      Tutorial, reference and examples for learning SQL syntax.

   :pep:`249` - Database API Specification 2.0
      PEP written by Marc-André Lemburg.


.. We use the following practises for SQL code:
   - UPPERCASE for keywords
   - snake_case for schema
   - single quotes for string literals
   - singular for table names
   - if needed, use double quotes for table and column names

.. _sqlite3-tutorial:

Tutorial
--------

In this tutorial, you will create a database of Monty Python movies
using basic :mod:`!sqlite3` functionality.
It assumes a fundamental understanding of database concepts,
including `cursors`_ and `transactions`_.

First, we need to create a new database and open
a database connection to allow :mod:`!sqlite3` to work with it.
Call :func:`sqlite3.connect` to create a connection to
the database :file:`tutorial.db` in the current working directory,
implicitly creating it if it does not exist:

.. testcode::

   import sqlite3
   con = sqlite3.connect("tutorial.db")

The returned :class:`Connection` object ``con``
represents the connection to the on-disk database.

In order to execute SQL statements and fetch results from SQL queries,
we will need to use a database cursor.
Call :meth:`con.cursor() <Connection.cursor>` to create the :class:`Cursor`:

.. testcode::

   cur = con.cursor()

Now that we've got a database connection and a cursor,
we can create a database table ``movie`` with columns for title,
release year, and review score.
For simplicity, we can just use column names in the table declaration --
thanks to the `flexible typing`_ feature of SQLite,
specifying the data types is optional.
Execute the ``CREATE TABLE`` statement
by calling :meth:`cur.execute(...) <Cursor.execute>`:

.. testcode::

   cur.execute("CREATE TABLE movie(title, year, score)")

.. Ideally, we'd use sqlite_schema instead of sqlite_master below,
   but SQLite versions older than 3.33.0 do not recognise that variant.

We can verify that the new table has been created by querying
the ``sqlite_master`` table built-in to SQLite,
which should now contain an entry for the ``movie`` table definition
(see `The Schema Table`_ for details).
Execute that query by calling :meth:`cur.execute(...) <Cursor.execute>`,
assign the result to ``res``,
and call :meth:`res.fetchone() <Cursor.fetchone>` to fetch the resulting row:

.. doctest::

   >>> res = cur.execute("SELECT name FROM sqlite_master")
   >>> res.fetchone()
   ('movie',)

We can see that the table has been created,
as the query returns a :class:`tuple` containing the table's name.
If we query ``sqlite_master`` for a non-existent table ``spam``,
:meth:`!res.fetchone` will return ``None``:

.. doctest::

   >>> res = cur.execute("SELECT name FROM sqlite_master WHERE name='spam'")
   >>> res.fetchone() is None
   True

Now, add two rows of data supplied as SQL literals
by executing an ``INSERT`` statement,
once again by calling :meth:`cur.execute(...) <Cursor.execute>`:

.. testcode::

   cur.execute("""
       INSERT INTO movie VALUES
           ('Monty Python and the Holy Grail', 1975, 8.2),
           ('And Now for Something Completely Different', 1971, 7.5)
   """)

The ``INSERT`` statement implicitly opens a transaction,
which needs to be committed before changes are saved in the database
(see :ref:`sqlite3-controlling-transactions` for details).
Call :meth:`con.commit() <Connection.commit>` on the connection object
to commit the transaction:

.. testcode::

   con.commit()

We can verify that the data was inserted correctly
by executing a ``SELECT`` query.
Use the now-familiar :meth:`cur.execute(...) <Cursor.execute>` to
assign the result to ``res``,
and call :meth:`res.fetchall() <Cursor.fetchall>` to return all resulting rows:

.. doctest::

   >>> res = cur.execute("SELECT score FROM movie")
   >>> res.fetchall()
   [(8.2,), (7.5,)]

The result is a :class:`list` of two :class:`!tuple`\s, one per row,
each containing that row's ``score`` value.

Now, insert three more rows by calling
:meth:`cur.executemany(...) <Cursor.executemany>`:

.. testcode::

   data = [
       ("Monty Python Live at the Hollywood Bowl", 1982, 7.9),
       ("Monty Python's The Meaning of Life", 1983, 7.5),
       ("Monty Python's Life of Brian", 1979, 8.0),
   ]
   cur.executemany("INSERT INTO movie VALUES(?, ?, ?)", data)
   con.commit()  # Remember to commit the transaction after executing INSERT.

Notice that ``?`` placeholders are used to bind ``data`` to the query.
Always use placeholders instead of :ref:`string formatting <tut-formatting>`
to bind Python values to SQL statements,
to avoid `SQL injection attacks`_
(see :ref:`sqlite3-placeholders` for more details).

We can verify that the new rows were inserted
by executing a ``SELECT`` query,
this time iterating over the results of the query:

.. doctest::

   >>> for row in cur.execute("SELECT year, title FROM movie ORDER BY year"):
   ...     print(row)
   (1971, 'And Now for Something Completely Different')
   (1975, 'Monty Python and the Holy Grail')
   (1979, "Monty Python's Life of Brian")
   (1982, 'Monty Python Live at the Hollywood Bowl')
   (1983, "Monty Python's The Meaning of Life")

Each row is a two-item :class:`tuple` of ``(year, title)``,
matching the columns selected in the query.

Finally, verify that the database has been written to disk
by calling :meth:`con.close() <Connection.close>`
to close the existing connection, opening a new one,
creating a new cursor, then querying the database:

.. doctest::

   >>> con.close()
   >>> new_con = sqlite3.connect("tutorial.db")
   >>> new_cur = new_con.cursor()
   >>> res = new_cur.execute("SELECT title, year FROM movie ORDER BY score DESC")
   >>> title, year = res.fetchone()
   >>> print(f'The highest scoring Monty Python movie is {title!r}, released in {year}')
   The highest scoring Monty Python movie is 'Monty Python and the Holy Grail', released in 1975
   >>> new_con.close()

You've now created an SQLite database using the :mod:`!sqlite3` module,
inserted data and retrieved values from it in multiple ways.

.. _SQL injection attacks: https://en.wikipedia.org/wiki/SQL_injection
.. _The Schema Table: https://www.sqlite.org/schematab.html
.. _cursors: https://en.wikipedia.org/wiki/Cursor_(databases)
.. _flexible typing: https://www.sqlite.org/flextypegood.html
.. _sqlite_master: https://www.sqlite.org/schematab.html
.. _transactions: https://en.wikipedia.org/wiki/Database_transaction

.. seealso::

   * :ref:`sqlite3-howtos` for further reading:

     * :ref:`sqlite3-placeholders`
     * :ref:`sqlite3-adapters`
     * :ref:`sqlite3-converters`
     * :ref:`sqlite3-connection-context-manager`
     * :ref:`sqlite3-howto-row-factory`

   * :ref:`sqlite3-explanation` for in-depth background on transaction control.

.. _sqlite3-reference:

Reference
---------

.. We keep the old sqlite3-module-contents ref to prevent breaking links.
.. _sqlite3-module-contents:

.. _sqlite3-module-functions:

Module functions
^^^^^^^^^^^^^^^^

.. function:: connect(database, timeout=5.0, detect_types=0, \
                      isolation_level="DEFERRED", check_same_thread=True, \
                      factory=sqlite3.Connection, cached_statements=128, \
                      uri=False, *, \
                      autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL)

   Open a connection to an SQLite database.

   :param database:
       The path to the database file to be opened.
       You can pass ``":memory:"`` to create an `SQLite database existing only
       in memory <https://sqlite.org/inmemorydb.html>`_, and open a connection
       to it.
   :type database: :term:`path-like object`

   :param float timeout:
       How many seconds the connection should wait before raising
       an :exc:`OperationalError` when a table is locked.
       If another connection opens a transaction to modify a table,
       that table will be locked until the transaction is committed.
       Default five seconds.

   :param int detect_types:
       Control whether and how data types not
       :ref:`natively supported by SQLite <sqlite3-types>`
       are looked up to be converted to Python types,
       using the converters registered with :func:`register_converter`.
       Set it to any combination (using ``|``, bitwise or) of
       :const:`PARSE_DECLTYPES` and :const:`PARSE_COLNAMES`
       to enable this.
       Column names takes precedence over declared types if both flags are set.
       Types cannot be detected for generated fields (for example ``max(data)``),
       even when the *detect_types* parameter is set; :class:`str` will be
       returned instead.
       By default (``0``), type detection is disabled.

   :param isolation_level:
       Control legacy transaction handling behaviour.
       See :attr:`Connection.isolation_level` and
       :ref:`sqlite3-transaction-control-isolation-level` for more information.
       Can be ``"DEFERRED"`` (default), ``"EXCLUSIVE"`` or ``"IMMEDIATE"``;
       or ``None`` to disable opening transactions implicitly.
       Has no effect unless :attr:`Connection.autocommit` is set to
       :const:`~sqlite3.LEGACY_TRANSACTION_CONTROL` (the default).
   :type isolation_level: str | None

   :param bool check_same_thread:
       If ``True`` (default), :exc:`ProgrammingError` will be raised
       if the database connection is used by a thread
       other than the one that created it.
       If ``False``, the connection may be accessed in multiple threads;
       write operations may need to be serialized by the user
       to avoid data corruption.
       See :attr:`threadsafety` for more information.

   :param ~sqlite3.Connection factory:
       A custom subclass of :class:`Connection` to create the connection with,
       if not the default :class:`Connection` class.

   :param int cached_statements:
       The number of statements that :mod:`!sqlite3`
       should internally cache for this connection, to avoid parsing overhead.
       By default, 128 statements.

   :param bool uri:
       If set to ``True``, *database* is interpreted as a
       :abbr:`URI (Uniform Resource Identifier)` with a file path
       and an optional query string.
       The scheme part *must* be ``"file:"``,
       and the path can be relative or absolute.
       The query string allows passing parameters to SQLite,
       enabling various :ref:`sqlite3-uri-tricks`.

   :param autocommit:
       Control :pep:`249` transaction handling behaviour.
       See :attr:`Connection.autocommit` and
       :ref:`sqlite3-transaction-control-autocommit` for more information.
       *autocommit* currently defaults to
       :const:`~sqlite3.LEGACY_TRANSACTION_CONTROL`.
       The default will change to ``False`` in a future Python release.
   :type autocommit: bool

   :rtype: ~sqlite3.Connection

   .. audit-event:: sqlite3.connect database sqlite3.connect
   .. audit-event:: sqlite3.connect/handle connection_handle sqlite3.connect

   .. versionchanged:: 3.4
      Added the *uri* parameter.

   .. versionchanged:: 3.7
      *database* can now also be a :term:`path-like object`, not only a string.

   .. versionchanged:: 3.10
      Added the ``sqlite3.connect/handle`` auditing event.

   .. versionchanged:: 3.12
      Added the *autocommit* parameter.

.. function:: complete_statement(statement)

   Return ``True`` if the string *statement* appears to contain
   one or more complete SQL statements.
   No syntactic verification or parsing of any kind is performed,
   other than checking that there are no unclosed string literals
   and the statement is terminated by a semicolon.

   For example:

   .. doctest::

      >>> sqlite3.complete_statement("SELECT foo FROM bar;")
      True
      >>> sqlite3.complete_statement("SELECT foo")
      False

   This function may be useful during command-line input
   to determine if the entered text seems to form a complete SQL statement,
   or if additional input is needed before calling :meth:`~Cursor.execute`.

   See :func:`!runsource` in :source:`Lib/sqlite3/__main__.py`
   for real-world use.

.. function:: enable_callback_tracebacks(flag, /)

   Enable or disable callback tracebacks.
   By default you will not get any tracebacks in user-defined functions,
   aggregates, converters, authorizer callbacks etc. If you want to debug them,
   you can call this function with *flag* set to ``True``. Afterwards, you
   will get tracebacks from callbacks on :data:`sys.stderr`. Use ``False``
   to disable the feature again.

   .. note::

      Errors in user-defined function callbacks are logged as unraisable exceptions.
      Use an :func:`unraisable hook handler <sys.unraisablehook>` for
      introspection of the failed callback.

.. function:: register_adapter(type, adapter, /)

   Register an *adapter* :term:`callable` to adapt the Python type *type*
   into an SQLite type.
   The adapter is called with a Python object of type *type* as its sole
   argument, and must return a value of a
   :ref:`type that SQLite natively understands <sqlite3-types>`.

.. function:: register_converter(typename, converter, /)

   Register the *converter* :term:`callable` to convert SQLite objects of type
   *typename* into a Python object of a specific type.
   The converter is invoked for all SQLite values of type *typename*;
   it is passed a :class:`bytes` object and should return an object of the
   desired Python type.
   Consult the parameter *detect_types* of
   :func:`connect` for information regarding how type detection works.

   Note: *typename* and the name of the type in your query are matched
   case-insensitively.


.. _sqlite3-module-constants:

Module constants
^^^^^^^^^^^^^^^^

.. data:: LEGACY_TRANSACTION_CONTROL

   Set :attr:`~Connection.autocommit` to this constant to select
   old style (pre-Python 3.12) transaction control behaviour.
   See :ref:`sqlite3-transaction-control-isolation-level` for more information.

.. data:: PARSE_COLNAMES

