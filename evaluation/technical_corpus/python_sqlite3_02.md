# Python 3.12.7 sqlite3 原始文档摘录 3

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/sqlite3.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

      Create a collation named *name* using the collating function *callable*.
      *callable* is passed two :class:`string <str>` arguments,
      and it should return an :class:`integer <int>`:

      * ``1`` if the first is ordered higher than the second
      * ``-1`` if the first is ordered lower than the second
      * ``0`` if they are ordered equal

      The following example shows a reverse sorting collation:

      .. testcode::

         def collate_reverse(string1, string2):
             if string1 == string2:
                 return 0
             elif string1 < string2:
                 return 1
             else:
                 return -1

         con = sqlite3.connect(":memory:")
         con.create_collation("reverse", collate_reverse)

         cur = con.execute("CREATE TABLE test(x)")
         cur.executemany("INSERT INTO test(x) VALUES(?)", [("a",), ("b",)])
         cur.execute("SELECT x FROM test ORDER BY x COLLATE reverse")
         for row in cur:
             print(row)
         con.close()

      .. testoutput::
         :hide:

         ('b',)
         ('a',)

      Remove a collation function by setting *callable* to ``None``.

      .. versionchanged:: 3.11
         The collation name can contain any Unicode character.  Earlier, only
         ASCII characters were allowed.


   .. method:: interrupt()

      Call this method from a different thread to abort any queries that might
      be executing on the connection.
      Aborted queries will raise an :exc:`OperationalError`.


   .. method:: set_authorizer(authorizer_callback)

      Register :term:`callable` *authorizer_callback* to be invoked
      for each attempt to access a column of a table in the database.
      The callback should return one of :const:`SQLITE_OK`,
      :const:`SQLITE_DENY`, or :const:`SQLITE_IGNORE`
      to signal how access to the column should be handled
      by the underlying SQLite library.

      The first argument to the callback signifies what kind of operation is to be
      authorized. The second and third argument will be arguments or ``None``
      depending on the first argument. The 4th argument is the name of the database
      ("main", "temp", etc.) if applicable. The 5th argument is the name of the
      inner-most trigger or view that is responsible for the access attempt or
      ``None`` if this access attempt is directly from input SQL code.

      Please consult the SQLite documentation about the possible values for the first
      argument and the meaning of the second and third argument depending on the first
      one. All necessary constants are available in the :mod:`!sqlite3` module.

      Passing ``None`` as *authorizer_callback* will disable the authorizer.

      .. versionchanged:: 3.11
         Added support for disabling the authorizer using ``None``.


   .. method:: set_progress_handler(progress_handler, n)

      Register :term:`callable` *progress_handler* to be invoked for every *n*
      instructions of the SQLite virtual machine. This is useful if you want to
      get called from SQLite during long-running operations, for example to update
      a GUI.

      If you want to clear any previously installed progress handler, call the
      method with ``None`` for *progress_handler*.

      Returning a non-zero value from the handler function will terminate the
      currently executing query and cause it to raise a :exc:`DatabaseError`
      exception.


   .. method:: set_trace_callback(trace_callback)

      Register :term:`callable` *trace_callback* to be invoked
      for each SQL statement that is actually executed by the SQLite backend.

      The only argument passed to the callback is the statement (as
      :class:`str`) that is being executed. The return value of the callback is
      ignored. Note that the backend does not only run statements passed to the
      :meth:`Cursor.execute` methods.  Other sources include the
      :ref:`transaction management <sqlite3-controlling-transactions>` of the
      :mod:`!sqlite3` module and the execution of triggers defined in the current
      database.

      Passing ``None`` as *trace_callback* will disable the trace callback.

      .. note::
         Exceptions raised in the trace callback are not propagated. As a
         development and debugging aid, use
         :meth:`~sqlite3.enable_callback_tracebacks` to enable printing
         tracebacks from exceptions raised in the trace callback.

      .. versionadded:: 3.3


   .. method:: enable_load_extension(enabled, /)

      Enable the SQLite engine to load SQLite extensions from shared libraries
      if *enabled* is ``True``;
      else, disallow loading SQLite extensions.
      SQLite extensions can define new functions,
      aggregates or whole new virtual table implementations.  One well-known
      extension is the fulltext-search extension distributed with SQLite.

      .. note::

         The :mod:`!sqlite3` module is not built with loadable extension support by
         default, because some platforms (notably macOS) have SQLite
         libraries which are compiled without this feature.
         To get loadable extension support,
         you must pass the :option:`--enable-loadable-sqlite-extensions` option
         to :program:`configure`.

      .. audit-event:: sqlite3.enable_load_extension connection,enabled sqlite3.Connection.enable_load_extension

      .. versionadded:: 3.2

      .. versionchanged:: 3.10
         Added the ``sqlite3.enable_load_extension`` auditing event.

      .. We cannot doctest the load extension API, since there is no convenient
         way to skip it.

      .. code-block::

         con.enable_load_extension(True)

         # Load the fulltext search extension
         con.execute("select load_extension('./fts3.so')")

         # alternatively you can load the extension using an API call:
         # con.load_extension("./fts3.so")

         # disable extension loading again
         con.enable_load_extension(False)

         # example from SQLite wiki
         con.execute("CREATE VIRTUAL TABLE recipe USING fts3(name, ingredients)")
         con.executescript("""
             INSERT INTO recipe (name, ingredients) VALUES('broccoli stew', 'broccoli peppers cheese tomatoes');
             INSERT INTO recipe (name, ingredients) VALUES('pumpkin stew', 'pumpkin onions garlic celery');
             INSERT INTO recipe (name, ingredients) VALUES('broccoli pie', 'broccoli cheese onions flour');
             INSERT INTO recipe (name, ingredients) VALUES('pumpkin pie', 'pumpkin sugar flour butter');
             """)
         for row in con.execute("SELECT rowid, name, ingredients FROM recipe WHERE name MATCH 'pie'"):
             print(row)

   .. method:: load_extension(path, /, *, entrypoint=None)

      Load an SQLite extension from a shared library.
      Enable extension loading with :meth:`enable_load_extension` before
      calling this method.

      :param str path:

         The path to the SQLite extension.

      :param entrypoint:

         Entry point name.
         If ``None`` (the default),
         SQLite will come up with an entry point name of its own;
         see the SQLite docs `Loading an Extension`_ for details.

      :type entrypoint: str | None

      .. audit-event:: sqlite3.load_extension connection,path sqlite3.Connection.load_extension

      .. versionadded:: 3.2

      .. versionchanged:: 3.10
         Added the ``sqlite3.load_extension`` auditing event.

      .. versionchanged:: 3.12
         Added the *entrypoint* parameter.

   .. _Loading an Extension: https://www.sqlite.org/loadext.html#loading_an_extension

   .. method:: iterdump

      Return an :term:`iterator` to dump the database as SQL source code.
      Useful when saving an in-memory database for later restoration.
      Similar to the ``.dump`` command in the :program:`sqlite3` shell.

      Example:

      .. testcode::

         # Convert file example.db to SQL dump file dump.sql
         con = sqlite3.connect('example.db')
         with open('dump.sql', 'w') as f:
             for line in con.iterdump():
                 f.write('%s\n' % line)
         con.close()

      .. seealso::

         :ref:`sqlite3-howto-encoding`


   .. method:: backup(target, *, pages=-1, progress=None, name="main", sleep=0.250)

      Create a backup of an SQLite database.

      Works even if the database is being accessed by other clients
      or concurrently by the same connection.

      :param ~sqlite3.Connection target:
          The database connection to save the backup to.

      :param int pages:
          The number of pages to copy at a time.
          If equal to or less than ``0``,
          the entire database is copied in a single step.
          Defaults to ``-1``.

      :param progress:
          If set to a :term:`callable`,
          it is invoked with three integer arguments for every backup iteration:
          the *status* of the last iteration,
          the *remaining* number of pages still to be copied,
          and the *total* number of pages.
          Defaults to ``None``.
      :type progress: :term:`callback` | None

      :param str name:
          The name of the database to back up.
          Either ``"main"`` (the default) for the main database,
          ``"temp"`` for the temporary database,
          or the name of a custom database as attached using the
          ``ATTACH DATABASE`` SQL statement.

      :param float sleep:
          The number of seconds to sleep between successive attempts
          to back up remaining pages.

      Example 1, copy an existing database into another:

      .. testcode::

         def progress(status, remaining, total):
             print(f'Copied {total-remaining} of {total} pages...')

         src = sqlite3.connect('example.db')
         dst = sqlite3.connect('backup.db')
         with dst:
             src.backup(dst, pages=1, progress=progress)
         dst.close()
         src.close()

      .. testoutput::
         :hide:

         Copied 0 of 0 pages...

      Example 2, copy an existing database into a transient copy:

      .. testcode::

         src = sqlite3.connect('example.db')
         dst = sqlite3.connect(':memory:')
         src.backup(dst)
         dst.close()
         src.close()

      .. versionadded:: 3.7

      .. seealso::

         :ref:`sqlite3-howto-encoding`

   .. method:: getlimit(category, /)

      Get a connection runtime limit.

      :param int category:
         The `SQLite limit category`_ to be queried.

      :rtype: int

      :raises ProgrammingError:
         If *category* is not recognised by the underlying SQLite library.

      Example, query the maximum length of an SQL statement
      for :class:`Connection` ``con`` (the default is 1000000000):

      .. testsetup:: sqlite3.limits

         import sqlite3
         con = sqlite3.connect(":memory:")
         con.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 1_000_000_000)
         con.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 10)

      .. doctest:: sqlite3.limits

         >>> con.getlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH)
         1000000000

      .. versionadded:: 3.11


   .. method:: setlimit(category, limit, /)

      Set a connection runtime limit.
      Attempts to increase a limit above its hard upper bound are silently
      truncated to the hard upper bound. Regardless of whether or not the limit
      was changed, the prior value of the limit is returned.

      :param int category:
         The `SQLite limit category`_ to be set.

      :param int limit:
         The value of the new limit.
         If negative, the current limit is unchanged.

      :rtype: int

      :raises ProgrammingError:
         If *category* is not recognised by the underlying SQLite library.

      Example, limit the number of attached databases to 1
      for :class:`Connection` ``con`` (the default limit is 10):

      .. doctest:: sqlite3.limits

         >>> con.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 1)
         10
         >>> con.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED)
         1

      .. testcleanup:: sqlite3.limits

         con.close()

      .. versionadded:: 3.11

   .. _SQLite limit category: https://www.sqlite.org/c3ref/c_limit_attached.html


   .. method:: getconfig(op, /)

      Query a boolean connection configuration option.

      :param int op:
         A :ref:`SQLITE_DBCONFIG code <sqlite3-dbconfig-constants>`.

      :rtype: bool

      .. versionadded:: 3.12

   .. method:: setconfig(op, enable=True, /)

      Set a boolean connection configuration option.

      :param int op:
         A :ref:`SQLITE_DBCONFIG code <sqlite3-dbconfig-constants>`.

      :param bool enable:
         ``True`` if the configuration option should be enabled (default);
         ``False`` if it should be disabled.

      .. versionadded:: 3.12

   .. method:: serialize(*, name="main")

      Serialize a database into a :class:`bytes` object.  For an
      ordinary on-disk database file, the serialization is just a copy of the
      disk file.  For an in-memory database or a "temp" database, the
      serialization is the same sequence of bytes which would be written to
      disk if that database were backed up to disk.

      :param str name:
         The database name to be serialized.
         Defaults to ``"main"``.

      :rtype: bytes

      .. note::

         This method is only available if the underlying SQLite library has the
         serialize API.

      .. versionadded:: 3.11


   .. method:: deserialize(data, /, *, name="main")

      Deserialize a :meth:`serialized <serialize>` database into a
      :class:`Connection`.
      This method causes the database connection to disconnect from database
      *name*, and reopen *name* as an in-memory database based on the
      serialization contained in *data*.

      :param bytes data:
         A serialized database.

      :param str name:
         The database name to deserialize into.
         Defaults to ``"main"``.

      :raises OperationalError:
         If the database connection is currently involved in a read
         transaction or a backup operation.

      :raises DatabaseError:
         If *data* does not contain a valid SQLite database.

      :raises OverflowError:
         If :func:`len(data) <len>` is larger than ``2**63 - 1``.

      .. note::

         This method is only available if the underlying SQLite library has the
         deserialize API.

      .. versionadded:: 3.11

   .. attribute:: autocommit

      This attribute controls :pep:`249`-compliant transaction behaviour.
      :attr:`!autocommit` has three allowed values:

      * ``False``: Select :pep:`249`-compliant transaction behaviour,
        implying that :mod:`!sqlite3` ensures a transaction is always open.
        Use :meth:`commit` and :meth:`rollback` to close transactions.

        This is the recommended value of :attr:`!autocommit`.

      * ``True``: Use SQLite's `autocommit mode`_.
        :meth:`commit` and :meth:`rollback` have no effect in this mode.

      * :data:`LEGACY_TRANSACTION_CONTROL`:
        Pre-Python 3.12 (non-:pep:`249`-compliant) transaction control.
        See :attr:`isolation_level` for more details.

        This is currently the default value of :attr:`!autocommit`.

      Changing :attr:`!autocommit` to ``False`` will open a new transaction,
      and changing it to ``True`` will commit any pending transaction.

      See :ref:`sqlite3-transaction-control-autocommit` for more details.

      .. note::

         The :attr:`isolation_level` attribute has no effect unless
         :attr:`autocommit` is :data:`LEGACY_TRANSACTION_CONTROL`.

      .. versionadded:: 3.12

   .. attribute:: in_transaction

      This read-only attribute corresponds to the low-level SQLite
      `autocommit mode`_.

