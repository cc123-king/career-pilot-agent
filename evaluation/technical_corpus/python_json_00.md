# Python 3.12.7 json 原始文档摘录 1

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/json.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

:mod:`!json` --- JSON encoder and decoder
=========================================

.. module:: json
   :synopsis: Encode and decode the JSON format.

.. moduleauthor:: Bob Ippolito <bob@redivi.com>
.. sectionauthor:: Bob Ippolito <bob@redivi.com>

**Source code:** :source:`Lib/json/__init__.py`

--------------

`JSON (JavaScript Object Notation) <https://json.org>`_, specified by
:rfc:`7159` (which obsoletes :rfc:`4627`) and by
`ECMA-404 <https://ecma-international.org/publications-and-standards/standards/ecma-404/>`_,
is a lightweight data interchange format inspired by
`JavaScript <https://en.wikipedia.org/wiki/JavaScript>`_ object literal syntax
(although it is not a strict subset of JavaScript [#rfc-errata]_ ).

.. warning::
   Be cautious when parsing JSON data from untrusted sources. A malicious
   JSON string may cause the decoder to consume considerable CPU and memory
   resources. Limiting the size of data to be parsed is recommended.

:mod:`json` exposes an API familiar to users of the standard library
:mod:`marshal` and :mod:`pickle` modules.

Encoding basic Python object hierarchies::

    >>> import json
    >>> json.dumps(['foo', {'bar': ('baz', None, 1.0, 2)}])
    '["foo", {"bar": ["baz", null, 1.0, 2]}]'
    >>> print(json.dumps("\"foo\bar"))
    "\"foo\bar"
    >>> print(json.dumps('\u1234'))
    "\u1234"
    >>> print(json.dumps('\\'))
    "\\"
    >>> print(json.dumps({"c": 0, "b": 0, "a": 0}, sort_keys=True))
    {"a": 0, "b": 0, "c": 0}
    >>> from io import StringIO
    >>> io = StringIO()
    >>> json.dump(['streaming API'], io)
    >>> io.getvalue()
    '["streaming API"]'

Compact encoding::

    >>> import json
    >>> json.dumps([1, 2, 3, {'4': 5, '6': 7}], separators=(',', ':'))
    '[1,2,3,{"4":5,"6":7}]'

Pretty printing::

    >>> import json
    >>> print(json.dumps({'4': 5, '6': 7}, sort_keys=True, indent=4))
    {
        "4": 5,
        "6": 7
    }

Decoding JSON::

    >>> import json
    >>> json.loads('["foo", {"bar":["baz", null, 1.0, 2]}]')
    ['foo', {'bar': ['baz', None, 1.0, 2]}]
    >>> json.loads('"\\"foo\\bar"')
    '"foo\x08ar'
    >>> from io import StringIO
    >>> io = StringIO('["streaming API"]')
    >>> json.load(io)
    ['streaming API']

Specializing JSON object decoding::

    >>> import json
    >>> def as_complex(dct):
    ...     if '__complex__' in dct:
    ...         return complex(dct['real'], dct['imag'])
    ...     return dct
    ...
    >>> json.loads('{"__complex__": true, "real": 1, "imag": 2}',
    ...     object_hook=as_complex)
    (1+2j)
    >>> import decimal
    >>> json.loads('1.1', parse_float=decimal.Decimal)
    Decimal('1.1')

Extending :class:`JSONEncoder`::

    >>> import json
    >>> class ComplexEncoder(json.JSONEncoder):
    ...     def default(self, obj):
    ...         if isinstance(obj, complex):
    ...             return [obj.real, obj.imag]
    ...         # Let the base class default method raise the TypeError
    ...         return super().default(obj)
    ...
    >>> json.dumps(2 + 1j, cls=ComplexEncoder)
    '[2.0, 1.0]'
    >>> ComplexEncoder().encode(2 + 1j)
    '[2.0, 1.0]'
    >>> list(ComplexEncoder().iterencode(2 + 1j))
    ['[2.0', ', 1.0', ']']


Using :mod:`json.tool` from the shell to validate and pretty-print:

.. code-block:: shell-session

    $ echo '{"json":"obj"}' | python -m json.tool
    {
        "json": "obj"
    }
    $ echo '{1.2:3.4}' | python -m json.tool
    Expecting property name enclosed in double quotes: line 1 column 2 (char 1)

See :ref:`json-commandline` for detailed documentation.

.. note::

   JSON is a subset of `YAML <https://yaml.org/>`_ 1.2.  The JSON produced by
   this module's default settings (in particular, the default *separators*
   value) is also a subset of YAML 1.0 and 1.1.  This module can thus also be
   used as a YAML serializer.

.. note::

   This module's encoders and decoders preserve input and output order by
   default.  Order is only lost if the underlying containers are unordered.


Basic Usage
-----------

.. function:: dump(obj, fp, *, skipkeys=False, ensure_ascii=True, \
                   check_circular=True, allow_nan=True, cls=None, \
                   indent=None, separators=None, default=None, \
                   sort_keys=False, **kw)

   Serialize *obj* as a JSON formatted stream to *fp* (a ``.write()``-supporting
   :term:`file-like object`) using this :ref:`conversion table
   <py-to-json-table>`.

   If *skipkeys* is true (default: ``False``), then dict keys that are not
   of a basic type (:class:`str`, :class:`int`, :class:`float`, :class:`bool`,
   ``None``) will be skipped instead of raising a :exc:`TypeError`.

   The :mod:`json` module always produces :class:`str` objects, not
   :class:`bytes` objects. Therefore, ``fp.write()`` must support :class:`str`
   input.

   If *ensure_ascii* is true (the default), the output is guaranteed to
   have all incoming non-ASCII characters escaped.  If *ensure_ascii* is
   false, these characters will be output as-is.

   If *check_circular* is false (default: ``True``), then the circular
   reference check for container types will be skipped and a circular reference
   will result in a :exc:`RecursionError` (or worse).

   If *allow_nan* is false (default: ``True``), then it will be a
   :exc:`ValueError` to serialize out of range :class:`float` values (``nan``,
   ``inf``, ``-inf``) in strict compliance of the JSON specification.
   If *allow_nan* is true, their JavaScript equivalents (``NaN``,
   ``Infinity``, ``-Infinity``) will be used.

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

   If *sort_keys* is true (default: ``False``), then the output of
   dictionaries will be sorted by key.

   To use a custom :class:`JSONEncoder` subclass (e.g. one that overrides the
   :meth:`~JSONEncoder.default` method to serialize additional types), specify it with the
   *cls* kwarg; otherwise :class:`JSONEncoder` is used.

   .. versionchanged:: 3.6
      All optional parameters are now :ref:`keyword-only <keyword-only_parameter>`.

   .. note::

      Unlike :mod:`pickle` and :mod:`marshal`, JSON is not a framed protocol,
      so trying to serialize multiple objects with repeated calls to
      :func:`dump` using the same *fp* will result in an invalid JSON file.

.. function:: dumps(obj, *, skipkeys=False, ensure_ascii=True, \
                    check_circular=True, allow_nan=True, cls=None, \
                    indent=None, separators=None, default=None, \
                    sort_keys=False, **kw)

   Serialize *obj* to a JSON formatted :class:`str` using this :ref:`conversion
   table <py-to-json-table>`.  The arguments have the same meaning as in
   :func:`dump`.

   .. note::

      Keys in key/value pairs of JSON are always of the type :class:`str`. When
      a dictionary is converted into JSON, all the keys of the dictionary are
      coerced to strings. As a result of this, if a dictionary is converted
      into JSON and then back into a dictionary, the dictionary may not equal
      the original one. That is, ``loads(dumps(x)) != x`` if x has non-string
      keys.

.. function:: load(fp, *, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None, **kw)

   Deserialize *fp* (a ``.read()``-supporting :term:`text file` or
   :term:`binary file` containing a JSON document) to a Python object using
   this :ref:`conversion table <json-to-py-table>`.

   *object_hook* is an optional function that will be called with the result of
   any object literal decoded (a :class:`dict`).  The return value of
   *object_hook* will be used instead of the :class:`dict`.  This feature can
   be used to implement custom decoders (e.g. `JSON-RPC
   <https://www.jsonrpc.org>`_ class hinting).

   *object_pairs_hook* is an optional function that will be called with the
   result of any object literal decoded with an ordered list of pairs.  The
   return value of *object_pairs_hook* will be used instead of the
   :class:`dict`.  This feature can be used to implement custom decoders.  If
   *object_hook* is also defined, the *object_pairs_hook* takes priority.

   .. versionchanged:: 3.1
      Added support for *object_pairs_hook*.

   *parse_float* is an optional function that will be called with the string of
   every JSON float to be decoded.  By default, this is equivalent to
   ``float(num_str)``.  This can be used to use another datatype or parser for
   JSON floats (e.g. :class:`decimal.Decimal`).

   *parse_int* is an optional function that will be called with the string of
   every JSON int to be decoded.  By default, this is equivalent to
   ``int(num_str)``.  This can be used to use another datatype or parser for
   JSON integers (e.g. :class:`float`).

   .. versionchanged:: 3.11
      The default *parse_int* of :func:`int` now limits the maximum length of
      the integer string via the interpreter's :ref:`integer string
      conversion length limitation <int_max_str_digits>` to help avoid denial
      of service attacks.

   *parse_constant* is an optional function that will be called with one of the
   following strings: ``'-Infinity'``, ``'Infinity'``, ``'NaN'``.  This can be
   used to raise an exception if invalid JSON numbers are encountered.

   .. versionchanged:: 3.1
      *parse_constant* doesn't get called on 'null', 'true', 'false' anymore.

   To use a custom :class:`JSONDecoder` subclass, specify it with the ``cls``
   kwarg; otherwise :class:`JSONDecoder` is used.  Additional keyword arguments
   will be passed to the constructor of the class.

   If the data being deserialized is not a valid JSON document, a
   :exc:`JSONDecodeError` will be raised.

   .. versionchanged:: 3.6
      All optional parameters are now :ref:`keyword-only <keyword-only_parameter>`.

   .. versionchanged:: 3.6
      *fp* can now be a :term:`binary file`. The input encoding should be
      UTF-8, UTF-16 or UTF-32.

.. function:: loads(s, *, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None, **kw)

   Deserialize *s* (a :class:`str`, :class:`bytes` or :class:`bytearray`
   instance containing a JSON document) to a Python object using this
   :ref:`conversion table <json-to-py-table>`.

   The other arguments have the same meaning as in :func:`load`.

   If the data being deserialized is not a valid JSON document, a
   :exc:`JSONDecodeError` will be raised.

   .. versionchanged:: 3.6
      *s* can now be of type :class:`bytes` or :class:`bytearray`. The
      input encoding should be UTF-8, UTF-16 or UTF-32.

   .. versionchanged:: 3.9
      The keyword argument *encoding* has been removed.


Encoders and Decoders
---------------------

.. class:: JSONDecoder(*, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, strict=True, object_pairs_hook=None)

   Simple JSON decoder.

   Performs the following translations in decoding by default:

   .. _json-to-py-table:

   +---------------+-------------------+
   | JSON          | Python            |
   +===============+===================+
   | object        | dict              |
   +---------------+-------------------+
   | array         | list              |
   +---------------+-------------------+
   | string        | str               |
   +---------------+-------------------+
   | number (int)  | int               |
   +---------------+-------------------+
   | number (real) | float             |
   +---------------+-------------------+
   | true          | True              |
   +---------------+-------------------+
   | false         | False             |
   +---------------+-------------------+
   | null          | None              |
   +---------------+-------------------+

   It also understands ``NaN``, ``Infinity``, and ``-Infinity`` as their
   corresponding ``float`` values, which is outside the JSON spec.

   *object_hook* is an optional function that will be called with the result of
   every JSON object decoded and its return value will be used in place of the
   given :class:`dict`.  This can be used to provide custom deserializations
   (e.g. to support `JSON-RPC <https://www.jsonrpc.org>`_ class hinting).

   *object_pairs_hook* is an optional function that will be called with the
   result of every JSON object decoded with an ordered list of pairs.  The
   return value of *object_pairs_hook* will be used instead of the
   :class:`dict`.  This feature can be used to implement custom decoders.  If
   *object_hook* is also defined, the *object_pairs_hook* takes priority.

   .. versionchanged:: 3.1
      Added support for *object_pairs_hook*.

   *parse_float* is an optional function that will be called with the string of
   every JSON float to be decoded.  By default, this is equivalent to
   ``float(num_str)``.  This can be used to use another datatype or parser for
   JSON floats (e.g. :class:`decimal.Decimal`).

   *parse_int* is an optional function that will be called with the string of
   every JSON int to be decoded.  By default, this is equivalent to
   ``int(num_str)``.  This can be used to use another datatype or parser for
   JSON integers (e.g. :class:`float`).

   *parse_constant* is an optional function that will be called with one of the
   following strings: ``'-Infinity'``, ``'Infinity'``, ``'NaN'``.  This can be
   used to raise an exception if invalid JSON numbers are encountered.

   If *strict* is false (``True`` is the default), then control characters
   will be allowed inside strings.  Control characters in this context are
   those with character codes in the 0--31 range, including ``'\t'`` (tab),
   ``'\n'``, ``'\r'`` and ``'\0'``.

   If the data being deserialized is not a valid JSON document, a
   :exc:`JSONDecodeError` will be raised.

   .. versionchanged:: 3.6
      All parameters are now :ref:`keyword-only <keyword-only_parameter>`.

   .. method:: decode(s)

      Return the Python representation of *s* (a :class:`str` instance
      containing a JSON document).

      :exc:`JSONDecodeError` will be raised if the given JSON document is not
      valid.

   .. method:: raw_decode(s)

      Decode a JSON document from *s* (a :class:`str` beginning with a
      JSON document) and return a 2-tuple of the Python representation
      and the index in *s* where the document ended.

      This can be used to decode a JSON document from a string that may have
      extraneous data at the end.


.. class:: JSONEncoder(*, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, sort_keys=False, indent=None, separators=None, default=None)

   Extensible JSON encoder for Python data structures.

   Supports the following objects and types by default:

   .. _py-to-json-table:

