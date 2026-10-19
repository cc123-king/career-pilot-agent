# Python 3.12.7 json 原始文档摘录 2

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/json.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

   +----------------------------------------+---------------+
   | Python                                 | JSON          |
   +========================================+===============+
   | dict                                   | object        |
   +----------------------------------------+---------------+
   | list, tuple                            | array         |
   +----------------------------------------+---------------+
   | str                                    | string        |
   +----------------------------------------+---------------+
   | int, float, int- & float-derived Enums | number        |
   +----------------------------------------+---------------+
   | True                                   | true          |
   +----------------------------------------+---------------+
   | False                                  | false         |
   +----------------------------------------+---------------+
   | None                                   | null          |
   +----------------------------------------+---------------+

   .. versionchanged:: 3.4
      Added support for int- and float-derived Enum classes.

   To extend this to recognize other objects, subclass and implement a
   :meth:`~JSONEncoder.default` method with another method that returns a serializable object
   for ``o`` if possible, otherwise it should call the superclass implementation
   (to raise :exc:`TypeError`).

   If *skipkeys* is false (the default), a :exc:`TypeError` will be raised when
   trying to encode keys that are not :class:`str`, :class:`int`, :class:`float`
   or ``None``.  If *skipkeys* is true, such items are simply skipped.

   If *ensure_ascii* is true (the default), the output is guaranteed to
   have all incoming non-ASCII characters escaped.  If *ensure_ascii* is
   false, these characters will be output as-is.

   If *check_circular* is true (the default), then lists, dicts, and custom
   encoded objects will be checked for circular references during encoding to
   prevent an infinite recursion (which would cause a :exc:`RecursionError`).
   Otherwise, no such check takes place.

   If *allow_nan* is true (the default), then ``NaN``, ``Infinity``, and
   ``-Infinity`` will be encoded as such.  This behavior is not JSON
   specification compliant, but is consistent with most JavaScript based
   encoders and decoders.  Otherwise, it will be a :exc:`ValueError` to encode
   such floats.

   If *sort_keys* is true (default: ``False``), then the output of dictionaries
   will be sorted by key; this is useful for regression tests to ensure that
   JSON serializations can be compared on a day-to-day basis.

   If *indent* is a non-negative integer or string, then JSON array elements and
   object members will be pretty-printed with that indent level.  An indent level
   of 0, negative, or ``""`` will only insert newlines.  ``None`` (the default)
   selects the most compact representation. Using a positive integer indent
   indents that many spaces per level.  If *indent* is a string (such as ``"\t"``),
   that string is used to indent each level.

   .. versionchanged:: 3.2
      Allow strings for *indent* in addition to integers.

   If specified, *separators* should be an ``(item_separator, key_separator)``
   tuple.  The default is ``(', ', ': ')`` if *indent* is ``None`` and
   ``(',', ': ')`` otherwise.  To get the most compact JSON representation,
   you should specify ``(',', ':')`` to eliminate whitespace.

   .. versionchanged:: 3.4
      Use ``(',', ': ')`` as default if *indent* is not ``None``.

   If specified, *default* should be a function that gets called for objects that
   can't otherwise be serialized.  It should return a JSON encodable version of
   the object or raise a :exc:`TypeError`.  If not specified, :exc:`TypeError`
   is raised.

   .. versionchanged:: 3.6
      All parameters are now :ref:`keyword-only <keyword-only_parameter>`.


   .. method:: default(o)

      Implement this method in a subclass such that it returns a serializable
      object for *o*, or calls the base implementation (to raise a
      :exc:`TypeError`).

      For example, to support arbitrary iterators, you could implement
      :meth:`~JSONEncoder.default` like this::

         def default(self, o):
            try:
                iterable = iter(o)
            except TypeError:
                pass
            else:
                return list(iterable)
            # Let the base class default method raise the TypeError
            return super().default(o)


   .. method:: encode(o)

      Return a JSON string representation of a Python data structure, *o*.  For
      example::

        >>> json.JSONEncoder().encode({"foo": ["bar", "baz"]})
        '{"foo": ["bar", "baz"]}'


   .. method:: iterencode(o)

      Encode the given object, *o*, and yield each string representation as
      available.  For example::

            for chunk in json.JSONEncoder().iterencode(bigobject):
                mysocket.write(chunk)


Exceptions
----------

.. exception:: JSONDecodeError(msg, doc, pos)

   Subclass of :exc:`ValueError` with the following additional attributes:

   .. attribute:: msg

      The unformatted error message.

   .. attribute:: doc

      The JSON document being parsed.

   .. attribute:: pos

      The start index of *doc* where parsing failed.

   .. attribute:: lineno

      The line corresponding to *pos*.

   .. attribute:: colno

      The column corresponding to *pos*.

   .. versionadded:: 3.5


Standard Compliance and Interoperability
----------------------------------------

The JSON format is specified by :rfc:`7159` and by
`ECMA-404 <https://ecma-international.org/publications-and-standards/standards/ecma-404/>`_.
This section details this module's level of compliance with the RFC.
For simplicity, :class:`JSONEncoder` and :class:`JSONDecoder` subclasses, and
parameters other than those explicitly mentioned, are not considered.

This module does not comply with the RFC in a strict fashion, implementing some
extensions that are valid JavaScript but not valid JSON.  In particular:

- Infinite and NaN number values are accepted and output;
- Repeated names within an object are accepted, and only the value of the last
  name-value pair is used.

Since the RFC permits RFC-compliant parsers to accept input texts that are not
RFC-compliant, this module's deserializer is technically RFC-compliant under
default settings.

Character Encodings
^^^^^^^^^^^^^^^^^^^

The RFC requires that JSON be represented using either UTF-8, UTF-16, or
UTF-32, with UTF-8 being the recommended default for maximum interoperability.

As permitted, though not required, by the RFC, this module's serializer sets
*ensure_ascii=True* by default, thus escaping the output so that the resulting
strings only contain ASCII characters.

Other than the *ensure_ascii* parameter, this module is defined strictly in
terms of conversion between Python objects and
:class:`Unicode strings <str>`, and thus does not otherwise directly address
the issue of character encodings.

The RFC prohibits adding a byte order mark (BOM) to the start of a JSON text,
and this module's serializer does not add a BOM to its output.
The RFC permits, but does not require, JSON deserializers to ignore an initial
BOM in their input.  This module's deserializer raises a :exc:`ValueError`
when an initial BOM is present.

The RFC does not explicitly forbid JSON strings which contain byte sequences
that don't correspond to valid Unicode characters (e.g. unpaired UTF-16
surrogates), but it does note that they may cause interoperability problems.
By default, this module accepts and outputs (when present in the original
:class:`str`) code points for such sequences.


Infinite and NaN Number Values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The RFC does not permit the representation of infinite or NaN number values.
Despite that, by default, this module accepts and outputs ``Infinity``,
``-Infinity``, and ``NaN`` as if they were valid JSON number literal values::

   >>> # Neither of these calls raises an exception, but the results are not valid JSON
   >>> json.dumps(float('-inf'))
   '-Infinity'
   >>> json.dumps(float('nan'))
   'NaN'
   >>> # Same when deserializing
   >>> json.loads('-Infinity')
   -inf
   >>> json.loads('NaN')
   nan

In the serializer, the *allow_nan* parameter can be used to alter this
behavior.  In the deserializer, the *parse_constant* parameter can be used to
alter this behavior.


Repeated Names Within an Object
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The RFC specifies that the names within a JSON object should be unique, but
does not mandate how repeated names in JSON objects should be handled.  By
default, this module does not raise an exception; instead, it ignores all but
the last name-value pair for a given name::

   >>> weird_json = '{"x": 1, "x": 2, "x": 3}'
   >>> json.loads(weird_json)
   {'x': 3}

The *object_pairs_hook* parameter can be used to alter this behavior.


Top-level Non-Object, Non-Array Values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The old version of JSON specified by the obsolete :rfc:`4627` required that
the top-level value of a JSON text must be either a JSON object or array
(Python :class:`dict` or :class:`list`), and could not be a JSON null,
boolean, number, or string value.  :rfc:`7159` removed that restriction, and
this module does not and has never implemented that restriction in either its
serializer or its deserializer.

Regardless, for maximum interoperability, you may wish to voluntarily adhere
to the restriction yourself.


Implementation Limitations
^^^^^^^^^^^^^^^^^^^^^^^^^^

Some JSON deserializer implementations may set limits on:

* the size of accepted JSON texts
* the maximum level of nesting of JSON objects and arrays
* the range and precision of JSON numbers
* the content and maximum length of JSON strings

This module does not impose any such limits beyond those of the relevant
Python datatypes themselves or the Python interpreter itself.

When serializing to JSON, beware any such limitations in applications that may
consume your JSON.  In particular, it is common for JSON numbers to be
deserialized into IEEE 754 double precision numbers and thus subject to that
representation's range and precision limitations.  This is especially relevant
when serializing Python :class:`int` values of extremely large magnitude, or
when serializing instances of "exotic" numerical types such as
:class:`decimal.Decimal`.


.. _json-commandline:
.. program:: json.tool

Command Line Interface
----------------------

.. module:: json.tool
    :synopsis: A command line to validate and pretty-print JSON.

**Source code:** :source:`Lib/json/tool.py`

--------------

The :mod:`json.tool` module provides a simple command line interface to validate
and pretty-print JSON objects.

If the optional ``infile`` and ``outfile`` arguments are not
specified, :data:`sys.stdin` and :data:`sys.stdout` will be used respectively:

.. code-block:: shell-session

    $ echo '{"json": "obj"}' | python -m json.tool
    {
        "json": "obj"
    }
    $ echo '{1.2:3.4}' | python -m json.tool
    Expecting property name enclosed in double quotes: line 1 column 2 (char 1)

.. versionchanged:: 3.5
   The output is now in the same order as the input. Use the
   :option:`--sort-keys` option to sort the output of dictionaries
   alphabetically by key.


Command line options
^^^^^^^^^^^^^^^^^^^^

.. option:: infile

   The JSON file to be validated or pretty-printed:

   .. code-block:: shell-session

      $ python -m json.tool mp_films.json
      [
          {
              "title": "And Now for Something Completely Different",
              "year": 1971
          },
          {
              "title": "Monty Python and the Holy Grail",
              "year": 1975
          }
      ]

   If *infile* is not specified, read from :data:`sys.stdin`.

.. option:: outfile

   Write the output of the *infile* to the given *outfile*. Otherwise, write it
   to :data:`sys.stdout`.

.. option:: --sort-keys

   Sort the output of dictionaries alphabetically by key.

   .. versionadded:: 3.5

.. option:: --no-ensure-ascii

   Disable escaping of non-ascii characters, see :func:`json.dumps` for more information.

   .. versionadded:: 3.9

.. option:: --json-lines

   Parse every input line as separate JSON object.

   .. versionadded:: 3.8

.. option:: --indent, --tab, --no-indent, --compact

   Mutually exclusive options for whitespace control.

   .. versionadded:: 3.9

.. option:: -h, --help

   Show the help message.


.. rubric:: Footnotes

.. [#rfc-errata] As noted in `the errata for RFC 7159
   <https://www.rfc-editor.org/errata_search.php?rfc=7159>`_,
   JSON permits literal U+2028 (LINE SEPARATOR) and
   U+2029 (PARAGRAPH SEPARATOR) characters in strings, whereas JavaScript
   (as of ECMAScript Edition 5.1) does not.


