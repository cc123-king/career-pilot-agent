# Python 3.12.7 pathlib 原始文档摘录 1

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/pathlib.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

:mod:`!pathlib` --- Object-oriented filesystem paths
====================================================

.. module:: pathlib
   :synopsis: Object-oriented filesystem paths

.. versionadded:: 3.4

**Source code:** :source:`Lib/pathlib.py`

.. index:: single: path; operations

--------------

This module offers classes representing filesystem paths with semantics
appropriate for different operating systems.  Path classes are divided
between :ref:`pure paths <pure-paths>`, which provide purely computational
operations without I/O, and :ref:`concrete paths <concrete-paths>`, which
inherit from pure paths but also provide I/O operations.

.. image:: pathlib-inheritance.png
   :align: center
   :class: invert-in-dark-mode
   :alt: Inheritance diagram showing the classes available in pathlib. The
         most basic class is PurePath, which has three direct subclasses:
         PurePosixPath, PureWindowsPath, and Path. Further to these four
         classes, there are two classes that use multiple inheritance:
         PosixPath subclasses PurePosixPath and Path, and WindowsPath
         subclasses PureWindowsPath and Path.

If you've never used this module before or just aren't sure which class is
right for your task, :class:`Path` is most likely what you need. It instantiates
a :ref:`concrete path <concrete-paths>` for the platform the code is running on.

Pure paths are useful in some special cases; for example:

#. If you want to manipulate Windows paths on a Unix machine (or vice versa).
   You cannot instantiate a :class:`WindowsPath` when running on Unix, but you
   can instantiate :class:`PureWindowsPath`.
#. You want to make sure that your code only manipulates paths without actually
   accessing the OS. In this case, instantiating one of the pure classes may be
   useful since those simply don't have any OS-accessing operations.

.. seealso::
   :pep:`428`: The pathlib module -- object-oriented filesystem paths.

.. seealso::
   For low-level path manipulation on strings, you can also use the
   :mod:`os.path` module.


Basic use
---------

Importing the main class::

   >>> from pathlib import Path

Listing subdirectories::

   >>> p = Path('.')
   >>> [x for x in p.iterdir() if x.is_dir()]
   [PosixPath('.hg'), PosixPath('docs'), PosixPath('dist'),
    PosixPath('__pycache__'), PosixPath('build')]

Listing Python source files in this directory tree::

   >>> list(p.glob('**/*.py'))
   [PosixPath('test_pathlib.py'), PosixPath('setup.py'),
    PosixPath('pathlib.py'), PosixPath('docs/conf.py'),
    PosixPath('build/lib/pathlib.py')]

Navigating inside a directory tree::

   >>> p = Path('/etc')
   >>> q = p / 'init.d' / 'reboot'
   >>> q
   PosixPath('/etc/init.d/reboot')
   >>> q.resolve()
   PosixPath('/etc/rc.d/init.d/halt')

Querying path properties::

   >>> q.exists()
   True
   >>> q.is_dir()
   False

Opening a file::

   >>> with q.open() as f: f.readline()
   ...
   '#!/bin/bash\n'


.. _pure-paths:

Pure paths
----------

Pure path objects provide path-handling operations which don't actually
access a filesystem.  There are three ways to access these classes, which
we also call *flavours*:

.. class:: PurePath(*pathsegments)

   A generic class that represents the system's path flavour (instantiating
   it creates either a :class:`PurePosixPath` or a :class:`PureWindowsPath`)::

      >>> PurePath('setup.py')      # Running on a Unix machine
      PurePosixPath('setup.py')

   Each element of *pathsegments* can be either a string representing a
   path segment, or an object implementing the :class:`os.PathLike` interface
   where the :meth:`~os.PathLike.__fspath__` method returns a string,
   such as another path object::

      >>> PurePath('foo', 'some/path', 'bar')
      PurePosixPath('foo/some/path/bar')
      >>> PurePath(Path('foo'), Path('bar'))
      PurePosixPath('foo/bar')

   When *pathsegments* is empty, the current directory is assumed::

      >>> PurePath()
      PurePosixPath('.')

   If a segment is an absolute path, all previous segments are ignored
   (like :func:`os.path.join`)::

      >>> PurePath('/etc', '/usr', 'lib64')
      PurePosixPath('/usr/lib64')
      >>> PureWindowsPath('c:/Windows', 'd:bar')
      PureWindowsPath('d:bar')

   On Windows, the drive is not reset when a rooted relative path
   segment (e.g., ``r'\foo'``) is encountered::

      >>> PureWindowsPath('c:/Windows', '/Program Files')
      PureWindowsPath('c:/Program Files')

   Spurious slashes and single dots are collapsed, but double dots (``'..'``)
   and leading double slashes (``'//'``) are not, since this would change the
   meaning of a path for various reasons (e.g. symbolic links, UNC paths)::

      >>> PurePath('foo//bar')
      PurePosixPath('foo/bar')
      >>> PurePath('//foo/bar')
      PurePosixPath('//foo/bar')
      >>> PurePath('foo/./bar')
      PurePosixPath('foo/bar')
      >>> PurePath('foo/../bar')
      PurePosixPath('foo/../bar')

   (a naïve approach would make ``PurePosixPath('foo/../bar')`` equivalent
   to ``PurePosixPath('bar')``, which is wrong if ``foo`` is a symbolic link
   to another directory)

   Pure path objects implement the :class:`os.PathLike` interface, allowing them
   to be used anywhere the interface is accepted.

   .. versionchanged:: 3.6
      Added support for the :class:`os.PathLike` interface.

.. class:: PurePosixPath(*pathsegments)

   A subclass of :class:`PurePath`, this path flavour represents non-Windows
   filesystem paths::

      >>> PurePosixPath('/etc/hosts')
      PurePosixPath('/etc/hosts')

   *pathsegments* is specified similarly to :class:`PurePath`.

.. class:: PureWindowsPath(*pathsegments)

   A subclass of :class:`PurePath`, this path flavour represents Windows
   filesystem paths, including `UNC paths`_::

      >>> PureWindowsPath('c:/', 'Users', 'Ximénez')
      PureWindowsPath('c:/Users/Ximénez')
      >>> PureWindowsPath('//server/share/file')
      PureWindowsPath('//server/share/file')

   *pathsegments* is specified similarly to :class:`PurePath`.

   .. _unc paths: https://en.wikipedia.org/wiki/Path_(computing)#UNC

Regardless of the system you're running on, you can instantiate all of
these classes, since they don't provide any operation that does system calls.


General properties
^^^^^^^^^^^^^^^^^^

Paths are immutable and :term:`hashable`.  Paths of a same flavour are comparable
and orderable.  These properties respect the flavour's case-folding
semantics::

   >>> PurePosixPath('foo') == PurePosixPath('FOO')
   False
   >>> PureWindowsPath('foo') == PureWindowsPath('FOO')
   True
   >>> PureWindowsPath('FOO') in { PureWindowsPath('foo') }
   True
   >>> PureWindowsPath('C:') < PureWindowsPath('d:')
   True

Paths of a different flavour compare unequal and cannot be ordered::

   >>> PureWindowsPath('foo') == PurePosixPath('foo')
   False
   >>> PureWindowsPath('foo') < PurePosixPath('foo')
   Traceback (most recent call last):
     File "<stdin>", line 1, in <module>
   TypeError: '<' not supported between instances of 'PureWindowsPath' and 'PurePosixPath'


Operators
^^^^^^^^^

The slash operator helps create child paths, like :func:`os.path.join`.
If the argument is an absolute path, the previous path is ignored.
On Windows, the drive is not reset when the argument is a rooted
relative path (e.g., ``r'\foo'``)::

   >>> p = PurePath('/etc')
   >>> p
   PurePosixPath('/etc')
   >>> p / 'init.d' / 'apache2'
   PurePosixPath('/etc/init.d/apache2')
   >>> q = PurePath('bin')
   >>> '/usr' / q
   PurePosixPath('/usr/bin')
   >>> p / '/an_absolute_path'
   PurePosixPath('/an_absolute_path')
   >>> PureWindowsPath('c:/Windows', '/Program Files')
   PureWindowsPath('c:/Program Files')

A path object can be used anywhere an object implementing :class:`os.PathLike`
is accepted::

   >>> import os
   >>> p = PurePath('/etc')
   >>> os.fspath(p)
   '/etc'

The string representation of a path is the raw filesystem path itself
(in native form, e.g. with backslashes under Windows), which you can
pass to any function taking a file path as a string::

   >>> p = PurePath('/etc')
   >>> str(p)
   '/etc'
   >>> p = PureWindowsPath('c:/Program Files')
   >>> str(p)
   'c:\\Program Files'

Similarly, calling :class:`bytes` on a path gives the raw filesystem path as a
bytes object, as encoded by :func:`os.fsencode`::

   >>> bytes(p)
   b'/etc'

.. note::
   Calling :class:`bytes` is only recommended under Unix.  Under Windows,
   the unicode form is the canonical representation of filesystem paths.


Accessing individual parts
^^^^^^^^^^^^^^^^^^^^^^^^^^

To access the individual "parts" (components) of a path, use the following
property:

.. attribute:: PurePath.parts

   A tuple giving access to the path's various components::

      >>> p = PurePath('/usr/bin/python3')
      >>> p.parts
      ('/', 'usr', 'bin', 'python3')

      >>> p = PureWindowsPath('c:/Program Files/PSF')
      >>> p.parts
      ('c:\\', 'Program Files', 'PSF')

   (note how the drive and local root are regrouped in a single part)


Methods and properties
^^^^^^^^^^^^^^^^^^^^^^

.. testsetup::

   from pathlib import PurePath, PurePosixPath, PureWindowsPath

Pure paths provide the following methods and properties:

.. attribute:: PurePath.drive

   A string representing the drive letter or name, if any::

      >>> PureWindowsPath('c:/Program Files/').drive
      'c:'
      >>> PureWindowsPath('/Program Files/').drive
      ''
      >>> PurePosixPath('/etc').drive
      ''

   UNC shares are also considered drives::

      >>> PureWindowsPath('//host/share/foo.txt').drive
      '\\\\host\\share'

.. attribute:: PurePath.root

   A string representing the (local or global) root, if any::

      >>> PureWindowsPath('c:/Program Files/').root
      '\\'
      >>> PureWindowsPath('c:Program Files/').root
      ''
      >>> PurePosixPath('/etc').root
      '/'

   UNC shares always have a root::

      >>> PureWindowsPath('//host/share').root
      '\\'

   If the path starts with more than two successive slashes,
   :class:`~pathlib.PurePosixPath` collapses them::

      >>> PurePosixPath('//etc').root
      '//'
      >>> PurePosixPath('///etc').root
      '/'
      >>> PurePosixPath('////etc').root
      '/'

   .. note::

      This behavior conforms to *The Open Group Base Specifications Issue 6*,
      paragraph `4.11 Pathname Resolution
      <https://pubs.opengroup.org/onlinepubs/009695399/basedefs/xbd_chap04.html#tag_04_11>`_:

      *"A pathname that begins with two successive slashes may be interpreted in
      an implementation-defined manner, although more than two leading slashes
      shall be treated as a single slash."*

.. attribute:: PurePath.anchor

   The concatenation of the drive and root::

      >>> PureWindowsPath('c:/Program Files/').anchor
      'c:\\'
      >>> PureWindowsPath('c:Program Files/').anchor
      'c:'
      >>> PurePosixPath('/etc').anchor
      '/'
      >>> PureWindowsPath('//host/share').anchor
      '\\\\host\\share\\'


.. attribute:: PurePath.parents

   An immutable sequence providing access to the logical ancestors of
   the path::

      >>> p = PureWindowsPath('c:/foo/bar/setup.py')
      >>> p.parents[0]
      PureWindowsPath('c:/foo/bar')
      >>> p.parents[1]
      PureWindowsPath('c:/foo')
      >>> p.parents[2]
      PureWindowsPath('c:/')

   .. versionchanged:: 3.10
      The parents sequence now supports :term:`slices <slice>` and negative index values.

.. attribute:: PurePath.parent

   The logical parent of the path::

      >>> p = PurePosixPath('/a/b/c/d')
      >>> p.parent
      PurePosixPath('/a/b/c')

   You cannot go past an anchor, or empty path::

      >>> p = PurePosixPath('/')
      >>> p.parent
      PurePosixPath('/')
      >>> p = PurePosixPath('.')
      >>> p.parent
      PurePosixPath('.')

   .. note::
      This is a purely lexical operation, hence the following behaviour::

         >>> p = PurePosixPath('foo/..')
         >>> p.parent
         PurePosixPath('foo')

      If you want to walk an arbitrary filesystem path upwards, it is
      recommended to first call :meth:`Path.resolve` so as to resolve
      symlinks and eliminate ``".."`` components.


.. attribute:: PurePath.name

   A string representing the final path component, excluding the drive and
   root, if any::

      >>> PurePosixPath('my/library/setup.py').name
      'setup.py'

   UNC drive names are not considered::

      >>> PureWindowsPath('//some/share/setup.py').name
      'setup.py'
      >>> PureWindowsPath('//some/share').name
      ''


.. attribute:: PurePath.suffix

   The file extension of the final component, if any::

      >>> PurePosixPath('my/library/setup.py').suffix
      '.py'
      >>> PurePosixPath('my/library.tar.gz').suffix
      '.gz'
      >>> PurePosixPath('my/library').suffix
      ''


.. attribute:: PurePath.suffixes

   A list of the path's file extensions::

      >>> PurePosixPath('my/library.tar.gar').suffixes
      ['.tar', '.gar']
      >>> PurePosixPath('my/library.tar.gz').suffixes
      ['.tar', '.gz']
      >>> PurePosixPath('my/library').suffixes
      []


.. attribute:: PurePath.stem

   The final path component, without its suffix::

      >>> PurePosixPath('my/library.tar.gz').stem
      'library.tar'
      >>> PurePosixPath('my/library.tar').stem
      'library'
      >>> PurePosixPath('my/library').stem
      'library'


.. method:: PurePath.as_posix()

   Return a string representation of the path with forward slashes (``/``)::

      >>> p = PureWindowsPath('c:\\windows')
      >>> str(p)
      'c:\\windows'
      >>> p.as_posix()
      'c:/windows'


.. method:: PurePath.as_uri()

   Represent the path as a ``file`` URI.  :exc:`ValueError` is raised if
   the path isn't absolute.

      >>> p = PurePosixPath('/etc/passwd')
      >>> p.as_uri()
      'file:///etc/passwd'
      >>> p = PureWindowsPath('c:/Windows')
      >>> p.as_uri()
      'file:///c:/Windows'


.. method:: PurePath.is_absolute()

   Return whether the path is absolute or not.  A path is considered absolute
   if it has both a root and (if the flavour allows) a drive::

      >>> PurePosixPath('/a/b').is_absolute()
      True
      >>> PurePosixPath('a/b').is_absolute()
      False

      >>> PureWindowsPath('c:/a/b').is_absolute()
      True
      >>> PureWindowsPath('/a/b').is_absolute()
      False
      >>> PureWindowsPath('c:').is_absolute()
      False
      >>> PureWindowsPath('//some/share').is_absolute()
      True


.. method:: PurePath.is_relative_to(other)

   Return whether or not this path is relative to the *other* path.

      >>> p = PurePath('/etc/passwd')
      >>> p.is_relative_to('/etc')
      True
      >>> p.is_relative_to('/usr')
      False

   This method is string-based; it neither accesses the filesystem nor treats
   "``..``" segments specially. The following code is equivalent:

      >>> u = PurePath('/usr')
      >>> u == p or u in p.parents
      False

   .. versionadded:: 3.9

   .. deprecated-removed:: 3.12 3.14

      Passing additional arguments is deprecated; if supplied, they are joined
      with *other*.

.. method:: PurePath.is_reserved()

   With :class:`PureWindowsPath`, return ``True`` if the path is considered
   reserved under Windows, ``False`` otherwise.  With :class:`PurePosixPath`,
   ``False`` is always returned.

      >>> PureWindowsPath('nul').is_reserved()
      True
      >>> PurePosixPath('nul').is_reserved()
      False

   File system calls on reserved paths can fail mysteriously or have
   unintended effects.


.. method:: PurePath.joinpath(*pathsegments)

   Calling this method is equivalent to combining the path with each of
   the given *pathsegments* in turn::

