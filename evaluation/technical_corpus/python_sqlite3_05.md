# Python 3.12.7 sqlite3 原始文档摘录 6

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/sqlite3.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

Using the :meth:`~Connection.execute`,
:meth:`~Connection.executemany`, and :meth:`~Connection.executescript`
methods of the :class:`Connection` class, your code can
be written more concisely because you don't have to create the (often
superfluous) :class:`Cursor` objects explicitly. Instead, the :class:`Cursor`
objects are created implicitly and these shortcut methods return the cursor
objects. This way, you can execute a ``SELECT`` statement and iterate over it
directly using only a single call on the :class:`Connection` object.

.. testcode::

   # Create and fill the table.
   con = sqlite3.connect(":memory:")
   con.execute("CREATE TABLE lang(name, first_appeared)")
   data = [
       ("C++", 1985),
       ("Objective-C", 1984),
   ]
   con.executemany("INSERT INTO lang(name, first_appeared) VALUES(?, ?)", data)

   # Print the table contents
   for row in con.execute("SELECT name, first_appeared FROM lang"):
       print(row)

   print("I just deleted", con.execute("DELETE FROM lang").rowcount, "rows")

   # close() is not a shortcut method and it's not called automatically;
   # the connection object should be closed manually
   con.close()

.. testoutput::
   :hide:

   ('C++', 1985)
   ('Objective-C', 1984)
   I just deleted 2 rows


.. _sqlite3-connection-context-manager:

How to use the connection context manager
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A :class:`Connection` object can be used as a context manager that
automatically commits or rolls back open transactions when leaving the body of
the context manager.
If the body of the :keyword:`with` statement finishes without exceptions,
the transaction is committed.
If this commit fails,
or if the body of the ``with`` statement raises an uncaught exception,
the transaction is rolled back.
If :attr:`~Connection.autocommit` is ``False``,
a new transaction is implicitly opened after committing or rolling back.

If there is no open transaction upon leaving the body of the ``with`` statement,
or if :attr:`~Connection.autocommit` is ``True``,
the context manager does nothing.

.. note::
   The context manager neither implicitly opens a new transaction
   nor closes the connection. If you need a closing context manager, consider
   using :meth:`contextlib.closing`.

.. testcode::

   con = sqlite3.connect(":memory:")
   con.execute("CREATE TABLE lang(id INTEGER PRIMARY KEY, name VARCHAR UNIQUE)")

   # Successful, con.commit() is called automatically afterwards
   with con:
       con.execute("INSERT INTO lang(name) VALUES(?)", ("Python",))

   # con.rollback() is called after the with block finishes with an exception,
   # the exception is still raised and must be caught
   try:
       with con:
           con.execute("INSERT INTO lang(name) VALUES(?)", ("Python",))
   except sqlite3.IntegrityError:
       print("couldn't add Python twice")

   # Connection object used as context manager only commits or rollbacks transactions,
   # so the connection object should be closed manually
   con.close()

.. testoutput::
   :hide:

   couldn't add Python twice


.. _sqlite3-uri-tricks:

How to work with SQLite URIs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some useful URI tricks include:

* Open a database in read-only mode:

.. doctest::

   >>> con = sqlite3.connect("file:tutorial.db?mode=ro", uri=True)
   >>> con.execute("CREATE TABLE readonly(data)")
   Traceback (most recent call last):
   OperationalError: attempt to write a readonly database

* Do not implicitly create a new database file if it does not already exist;
  will raise :exc:`~sqlite3.OperationalError` if unable to create a new file:

.. doctest::

   >>> con = sqlite3.connect("file:nosuchdb.db?mode=rw", uri=True)
   Traceback (most recent call last):
   OperationalError: unable to open database file


* Create a shared named in-memory database:

.. testcode::

   db = "file:mem1?mode=memory&cache=shared"
   con1 = sqlite3.connect(db, uri=True)
   con2 = sqlite3.connect(db, uri=True)
   with con1:
       con1.execute("CREATE TABLE shared(data)")
       con1.execute("INSERT INTO shared VALUES(28)")
   res = con2.execute("SELECT data FROM shared")
   assert res.fetchone() == (28,)

   con1.close()
   con2.close()

More information about this feature, including a list of parameters,
can be found in the `SQLite URI documentation`_.

.. _SQLite URI documentation: https://www.sqlite.org/uri.html


.. _sqlite3-howto-row-factory:

How to create and use row factories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, :mod:`!sqlite3` represents each row as a :class:`tuple`.
If a :class:`!tuple` does not suit your needs,
you can use the :class:`sqlite3.Row` class
or a custom :attr:`~Cursor.row_factory`.

While :attr:`!row_factory` exists as an attribute both on the
:class:`Cursor` and the :class:`Connection`,
it is recommended to set :class:`Connection.row_factory`,
so all cursors created from the connection will use the same row factory.

:class:`!Row` provides indexed and case-insensitive named access to columns,
with minimal memory overhead and performance impact over a :class:`!tuple`.
To use :class:`!Row` as a row factory,
assign it to the :attr:`!row_factory` attribute:

.. doctest::

   >>> con = sqlite3.connect(":memory:")
   >>> con.row_factory = sqlite3.Row

Queries now return :class:`!Row` objects:

.. doctest::

   >>> res = con.execute("SELECT 'Earth' AS name, 6378 AS radius")
   >>> row = res.fetchone()
   >>> row.keys()
   ['name', 'radius']
   >>> row[0]         # Access by index.
   'Earth'
   >>> row["name"]    # Access by name.
   'Earth'
   >>> row["RADIUS"]  # Column names are case-insensitive.
   6378
   >>> con.close()

.. note::

    The ``FROM`` clause can be omitted in the ``SELECT`` statement, as in the
    above example. In such cases, SQLite returns a single row with columns
    defined by expressions, e.g. literals, with the given aliases
    ``expr AS alias``.

You can create a custom :attr:`~Cursor.row_factory`
that returns each row as a :class:`dict`, with column names mapped to values:

.. testcode::

   def dict_factory(cursor, row):
       fields = [column[0] for column in cursor.description]
       return {key: value for key, value in zip(fields, row)}

Using it, queries now return a :class:`!dict` instead of a :class:`!tuple`:

.. doctest::

   >>> con = sqlite3.connect(":memory:")
   >>> con.row_factory = dict_factory
   >>> for row in con.execute("SELECT 1 AS a, 2 AS b"):
   ...     print(row)
   {'a': 1, 'b': 2}
   >>> con.close()

The following row factory returns a :term:`named tuple`:

.. testcode::

   from collections import namedtuple

   def namedtuple_factory(cursor, row):
       fields = [column[0] for column in cursor.description]
       cls = namedtuple("Row", fields)
       return cls._make(row)

:func:`!namedtuple_factory` can be used as follows:

.. doctest::

   >>> con = sqlite3.connect(":memory:")
   >>> con.row_factory = namedtuple_factory
   >>> cur = con.execute("SELECT 1 AS a, 2 AS b")
   >>> row = cur.fetchone()
   >>> row
   Row(a=1, b=2)
   >>> row[0]  # Indexed access.
   1
   >>> row.b   # Attribute access.
   2
   >>> con.close()

With some adjustments, the above recipe can be adapted to use a
:class:`~dataclasses.dataclass`, or any other custom class,
instead of a :class:`~collections.namedtuple`.


.. _sqlite3-howto-encoding:

How to handle non-UTF-8 text encodings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, :mod:`!sqlite3` uses :class:`str` to adapt SQLite values
with the ``TEXT`` data type.
This works well for UTF-8 encoded text, but it might fail for other encodings
and invalid UTF-8.
You can use a custom :attr:`~Connection.text_factory` to handle such cases.

Because of SQLite's `flexible typing`_, it is not uncommon to encounter table
columns with the ``TEXT`` data type containing non-UTF-8 encodings,
or even arbitrary data.
To demonstrate, let's assume we have a database with ISO-8859-2 (Latin-2)
encoded text, for example a table of Czech-English dictionary entries.
Assuming we now have a :class:`Connection` instance :py:data:`!con`
connected to this database,
we can decode the Latin-2 encoded text using this :attr:`~Connection.text_factory`:

.. testcode::

   con.text_factory = lambda data: str(data, encoding="latin2")

For invalid UTF-8 or arbitrary data in stored in ``TEXT`` table columns,
you can use the following technique, borrowed from the :ref:`unicode-howto`:

.. testcode::

   con.text_factory = lambda data: str(data, errors="surrogateescape")

.. note::

   The :mod:`!sqlite3` module API does not support strings
   containing surrogates.

.. seealso::

   :ref:`unicode-howto`


.. _sqlite3-explanation:

Explanation
-----------

.. _sqlite3-transaction-control:
.. _sqlite3-controlling-transactions:

Transaction control
^^^^^^^^^^^^^^^^^^^

:mod:`!sqlite3` offers multiple methods of controlling whether,
when and how database transactions are opened and closed.
:ref:`sqlite3-transaction-control-autocommit` is recommended,
while :ref:`sqlite3-transaction-control-isolation-level`
retains the pre-Python 3.12 behaviour.

.. _sqlite3-transaction-control-autocommit:

Transaction control via the ``autocommit`` attribute
""""""""""""""""""""""""""""""""""""""""""""""""""""

The recommended way of controlling transaction behaviour is through
the :attr:`Connection.autocommit` attribute,
which should preferably be set using the *autocommit* parameter
of :func:`connect`.

It is suggested to set *autocommit* to ``False``,
which implies :pep:`249`-compliant transaction control.
This means:

* :mod:`!sqlite3` ensures that a transaction is always open,
  so :func:`connect`, :meth:`Connection.commit`, and :meth:`Connection.rollback`
  will implicitly open a new transaction
  (immediately after closing the pending one, for the latter two).
  :mod:`!sqlite3` uses ``BEGIN DEFERRED`` statements when opening transactions.
* Transactions should be committed explicitly using :meth:`!commit`.
* Transactions should be rolled back explicitly using :meth:`!rollback`.
* An implicit rollback is performed if the database is
  :meth:`~Connection.close`-ed with pending changes.

Set *autocommit* to ``True`` to enable SQLite's `autocommit mode`_.
In this mode, :meth:`Connection.commit` and :meth:`Connection.rollback`
have no effect.
Note that SQLite's autocommit mode is distinct from
the :pep:`249`-compliant :attr:`Connection.autocommit` attribute;
use :attr:`Connection.in_transaction` to query
the low-level SQLite autocommit mode.

Set *autocommit* to :data:`LEGACY_TRANSACTION_CONTROL`
to leave transaction control behaviour to the
:attr:`Connection.isolation_level` attribute.
See :ref:`sqlite3-transaction-control-isolation-level` for more information.


.. _sqlite3-transaction-control-isolation-level:

Transaction control via the ``isolation_level`` attribute
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""

.. note::

   The recommended way of controlling transactions is via the
   :attr:`~Connection.autocommit` attribute.
   See :ref:`sqlite3-transaction-control-autocommit`.

If :attr:`Connection.autocommit` is set to
:data:`LEGACY_TRANSACTION_CONTROL` (the default),
transaction behaviour is controlled using
the :attr:`Connection.isolation_level` attribute.
Otherwise, :attr:`!isolation_level` has no effect.

If the connection attribute :attr:`~Connection.isolation_level`
is not ``None``,
new transactions are implicitly opened before
:meth:`~Cursor.execute` and :meth:`~Cursor.executemany` executes
``INSERT``, ``UPDATE``, ``DELETE``, or ``REPLACE`` statements;
for other statements, no implicit transaction handling is performed.
Use the :meth:`~Connection.commit` and :meth:`~Connection.rollback` methods
to respectively commit and roll back pending transactions.
You can choose the underlying `SQLite transaction behaviour`_ —
that is, whether and what type of ``BEGIN`` statements :mod:`!sqlite3`
implicitly executes –
via the :attr:`~Connection.isolation_level` attribute.

If :attr:`~Connection.isolation_level` is set to ``None``,
no transactions are implicitly opened at all.
This leaves the underlying SQLite library in `autocommit mode`_,
but also allows the user to perform their own transaction handling
using explicit SQL statements.
The underlying SQLite library autocommit mode can be queried using the
:attr:`~Connection.in_transaction` attribute.

The :meth:`~Cursor.executescript` method implicitly commits
any pending transaction before execution of the given SQL script,
regardless of the value of :attr:`~Connection.isolation_level`.

.. versionchanged:: 3.6
   :mod:`!sqlite3` used to implicitly commit an open transaction before DDL
   statements.  This is no longer the case.

.. versionchanged:: 3.12
   The recommended way of controlling transactions is now via the
   :attr:`~Connection.autocommit` attribute.

.. _autocommit mode:
   https://www.sqlite.org/lang_transaction.html#implicit_versus_explicit_transactions

.. _SQLite transaction behaviour:
   https://www.sqlite.org/lang_transaction.html#deferred_immediate_and_exclusive_transactions

.. testcleanup::

   import os
   os.remove("backup.db")
   os.remove("dump.sql")
   os.remove("example.db")
   os.remove("tutorial.db")


