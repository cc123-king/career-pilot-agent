# Python 3.12.7 pathlib 原始文档摘录 3

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/pathlib.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

   ``False`` is also returned if the path doesn't exist or is a broken symlink;
   other errors (such as permission errors) are propagated.


.. method:: Path.samefile(other_path)

   Return whether this path points to the same file as *other_path*, which
   can be either a Path object, or a string.  The semantics are similar
   to :func:`os.path.samefile` and :func:`os.path.samestat`.

   An :exc:`OSError` can be raised if either file cannot be accessed for some
   reason.

   ::

      >>> p = Path('spam')
      >>> q = Path('eggs')
      >>> p.samefile(q)
      False
      >>> p.samefile('spam')
      True

   .. versionadded:: 3.5


Reading and writing files
^^^^^^^^^^^^^^^^^^^^^^^^^


.. method:: Path.open(mode='r', buffering=-1, encoding=None, errors=None, newline=None)

   Open the file pointed to by the path, like the built-in :func:`open`
   function does::

      >>> p = Path('setup.py')
      >>> with p.open() as f:
      ...     f.readline()
      ...
      '#!/usr/bin/env python3\n'


.. method:: Path.read_text(encoding=None, errors=None)

   Return the decoded contents of the pointed-to file as a string::

      >>> p = Path('my_text_file')
      >>> p.write_text('Text file contents')
      18
      >>> p.read_text()
      'Text file contents'

   The file is opened and then closed. The optional parameters have the same
   meaning as in :func:`open`.

   .. versionadded:: 3.5


.. method:: Path.read_bytes()

   Return the binary contents of the pointed-to file as a bytes object::

      >>> p = Path('my_binary_file')
      >>> p.write_bytes(b'Binary file contents')
      20
      >>> p.read_bytes()
      b'Binary file contents'

   .. versionadded:: 3.5


.. method:: Path.write_text(data, encoding=None, errors=None, newline=None)

   Open the file pointed to in text mode, write *data* to it, and close the
   file::

      >>> p = Path('my_text_file')
      >>> p.write_text('Text file contents')
      18
      >>> p.read_text()
      'Text file contents'

   An existing file of the same name is overwritten. The optional parameters
   have the same meaning as in :func:`open`.

   .. versionadded:: 3.5

   .. versionchanged:: 3.10
      The *newline* parameter was added.


.. method:: Path.write_bytes(data)

   Open the file pointed to in bytes mode, write *data* to it, and close the
   file::

      >>> p = Path('my_binary_file')
      >>> p.write_bytes(b'Binary file contents')
      20
      >>> p.read_bytes()
      b'Binary file contents'

   An existing file of the same name is overwritten.

   .. versionadded:: 3.5


Reading directories
^^^^^^^^^^^^^^^^^^^

.. method:: Path.iterdir()

   When the path points to a directory, yield path objects of the directory
   contents::

      >>> p = Path('docs')
      >>> for child in p.iterdir(): child
      ...
      PosixPath('docs/conf.py')
      PosixPath('docs/_templates')
      PosixPath('docs/make.bat')
      PosixPath('docs/index.rst')
      PosixPath('docs/_build')
      PosixPath('docs/_static')
      PosixPath('docs/Makefile')

   The children are yielded in arbitrary order, and the special entries
   ``'.'`` and ``'..'`` are not included.  If a file is removed from or added
   to the directory after creating the iterator, it is unspecified whether
   a path object for that file is included.

   If the path is not a directory or otherwise inaccessible, :exc:`OSError` is
   raised.

.. method:: Path.glob(pattern, *, case_sensitive=None)

   Glob the given relative *pattern* in the directory represented by this path,
   yielding all matching files (of any kind)::

      >>> sorted(Path('.').glob('*.py'))
      [PosixPath('pathlib.py'), PosixPath('setup.py'), PosixPath('test_pathlib.py')]
      >>> sorted(Path('.').glob('*/*.py'))
      [PosixPath('docs/conf.py')]

   Patterns are the same as for :mod:`fnmatch`, with the addition of "``**``"
   which means "this directory and all subdirectories, recursively".  In other
   words, it enables recursive globbing::

      >>> sorted(Path('.').glob('**/*.py'))
      [PosixPath('build/lib/pathlib.py'),
       PosixPath('docs/conf.py'),
       PosixPath('pathlib.py'),
       PosixPath('setup.py'),
       PosixPath('test_pathlib.py')]

   This method calls :meth:`Path.is_dir` on the top-level directory and
   propagates any :exc:`OSError` exception that is raised. Subsequent
   :exc:`OSError` exceptions from scanning directories are suppressed.

   By default, or when the *case_sensitive* keyword-only argument is set to
   ``None``, this method matches paths using platform-specific casing rules:
   typically, case-sensitive on POSIX, and case-insensitive on Windows.
   Set *case_sensitive* to ``True`` or ``False`` to override this behaviour.

   .. note::
      Using the "``**``" pattern in large directory trees may consume
      an inordinate amount of time.

   .. audit-event:: pathlib.Path.glob self,pattern pathlib.Path.glob

   .. versionchanged:: 3.11
      Return only directories if *pattern* ends with a pathname components
      separator (:data:`~os.sep` or :data:`~os.altsep`).

   .. versionchanged:: 3.12
      The *case_sensitive* parameter was added.


.. method:: Path.rglob(pattern, *, case_sensitive=None)

   Glob the given relative *pattern* recursively.  This is like calling
   :func:`Path.glob` with "``**/``" added in front of the *pattern*, where
   *patterns* are the same as for :mod:`fnmatch`::

      >>> sorted(Path().rglob("*.py"))
      [PosixPath('build/lib/pathlib.py'),
       PosixPath('docs/conf.py'),
       PosixPath('pathlib.py'),
       PosixPath('setup.py'),
       PosixPath('test_pathlib.py')]

   By default, or when the *case_sensitive* keyword-only argument is set to
   ``None``, this method matches paths using platform-specific casing rules:
   typically, case-sensitive on POSIX, and case-insensitive on Windows.
   Set *case_sensitive* to ``True`` or ``False`` to override this behaviour.

   .. audit-event:: pathlib.Path.rglob self,pattern pathlib.Path.rglob

   .. versionchanged:: 3.11
      Return only directories if *pattern* ends with a pathname components
      separator (:data:`~os.sep` or :data:`~os.altsep`).

   .. versionchanged:: 3.12
      The *case_sensitive* parameter was added.


.. method:: Path.walk(top_down=True, on_error=None, follow_symlinks=False)

   Generate the file names in a directory tree by walking the tree
   either top-down or bottom-up.

   For each directory in the directory tree rooted at *self* (including
   *self* but excluding '.' and '..'), the method yields a 3-tuple of
   ``(dirpath, dirnames, filenames)``.

   *dirpath* is a :class:`Path` to the directory currently being walked,
   *dirnames* is a list of strings for the names of subdirectories in *dirpath*
   (excluding ``'.'`` and ``'..'``), and *filenames* is a list of strings for
   the names of the non-directory files in *dirpath*. To get a full path
   (which begins with *self*) to a file or directory in *dirpath*, do
   ``dirpath / name``. Whether or not the lists are sorted is file
   system-dependent.

   If the optional argument *top_down* is true (which is the default), the triple for a
   directory is generated before the triples for any of its subdirectories
   (directories are walked top-down).  If *top_down* is false, the triple
   for a directory is generated after the triples for all of its subdirectories
   (directories are walked bottom-up). No matter the value of *top_down*, the
   list of subdirectories is retrieved before the triples for the directory and
   its subdirectories are walked.

   When *top_down* is true, the caller can modify the *dirnames* list in-place
   (for example, using :keyword:`del` or slice assignment), and :meth:`Path.walk`
   will only recurse into the subdirectories whose names remain in *dirnames*.
   This can be used to prune the search, or to impose a specific order of visiting,
   or even to inform :meth:`Path.walk` about directories the caller creates or
   renames before it resumes :meth:`Path.walk` again. Modifying *dirnames* when
   *top_down* is false has no effect on the behavior of :meth:`Path.walk` since the
   directories in *dirnames* have already been generated by the time *dirnames*
   is yielded to the caller.

   By default, errors from :func:`os.scandir` are ignored.  If the optional
   argument *on_error* is specified, it should be a callable; it will be
   called with one argument, an :exc:`OSError` instance. The callable can handle the
   error to continue the walk or re-raise it to stop the walk. Note that the
   filename is available as the ``filename`` attribute of the exception object.

   By default, :meth:`Path.walk` does not follow symbolic links, and instead adds them
   to the *filenames* list. Set *follow_symlinks* to true to resolve symlinks
   and place them in *dirnames* and *filenames* as appropriate for their targets, and
   consequently visit directories pointed to by symlinks (where supported).

   .. note::

      Be aware that setting *follow_symlinks* to true can lead to infinite
      recursion if a link points to a parent directory of itself. :meth:`Path.walk`
      does not keep track of the directories it has already visited.

   .. note::
      :meth:`Path.walk` assumes the directories it walks are not modified during
      execution. For example, if a directory from *dirnames* has been replaced
      with a symlink and *follow_symlinks* is false, :meth:`Path.walk` will
      still try to descend into it. To prevent such behavior, remove directories
      from *dirnames* as appropriate.

   .. note::

      Unlike :func:`os.walk`, :meth:`Path.walk` lists symlinks to directories in
      *filenames* if *follow_symlinks* is false.

   This example displays the number of bytes used by all files in each directory,
   while ignoring ``__pycache__`` directories::

      from pathlib import Path
      for root, dirs, files in Path("cpython/Lib/concurrent").walk(on_error=print):
        print(
            root,
            "consumes",
            sum((root / file).stat().st_size for file in files),
            "bytes in",
            len(files),
            "non-directory files"
        )
        if '__pycache__' in dirs:
              dirs.remove('__pycache__')

   This next example is a simple implementation of :func:`shutil.rmtree`.
   Walking the tree bottom-up is essential as :func:`rmdir` doesn't allow
   deleting a directory before it is empty::

      # Delete everything reachable from the directory "top".
      # CAUTION:  This is dangerous! For example, if top == Path('/'),
      # it could delete all of your files.
      for root, dirs, files in top.walk(top_down=False):
          for name in files:
              (root / name).unlink()
          for name in dirs:
              (root / name).rmdir()

   .. versionadded:: 3.12


Creating files and directories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. method:: Path.touch(mode=0o666, exist_ok=True)

   Create a file at this given path.  If *mode* is given, it is combined
   with the process's ``umask`` value to determine the file mode and access
   flags.  If the file already exists, the function succeeds when *exist_ok*
   is true (and its modification time is updated to the current time),
   otherwise :exc:`FileExistsError` is raised.

   .. seealso::
      The :meth:`~Path.open`, :meth:`~Path.write_text` and
      :meth:`~Path.write_bytes` methods are often used to create files.


.. method:: Path.mkdir(mode=0o777, parents=False, exist_ok=False)

   Create a new directory at this given path.  If *mode* is given, it is
   combined with the process's ``umask`` value to determine the file mode
   and access flags.  If the path already exists, :exc:`FileExistsError`
   is raised.

   If *parents* is true, any missing parents of this path are created
   as needed; they are created with the default permissions without taking
   *mode* into account (mimicking the POSIX ``mkdir -p`` command).

   If *parents* is false (the default), a missing parent raises
   :exc:`FileNotFoundError`.

   If *exist_ok* is false (the default), :exc:`FileExistsError` is
   raised if the target directory already exists.

   If *exist_ok* is true, :exc:`FileExistsError` will not be raised unless the given
   path already exists in the file system and is not a directory (same
   behavior as the POSIX ``mkdir -p`` command).

   .. versionchanged:: 3.5
      The *exist_ok* parameter was added.


.. method:: Path.symlink_to(target, target_is_directory=False)

   Make this path a symbolic link pointing to *target*.

   On Windows, a symlink represents either a file or a directory, and does not
   morph to the target dynamically.  If the target is present, the type of the
   symlink will be created to match. Otherwise, the symlink will be created
   as a directory if *target_is_directory* is true or a file symlink (the
   default) otherwise.  On non-Windows platforms, *target_is_directory* is ignored.

   ::

      >>> p = Path('mylink')
      >>> p.symlink_to('setup.py')
      >>> p.resolve()
      PosixPath('/home/antoine/pathlib/setup.py')
      >>> p.stat().st_size
      956
      >>> p.lstat().st_size
      8

   .. note::
      The order of arguments (link, target) is the reverse
      of :func:`os.symlink`'s.


.. method:: Path.hardlink_to(target)

   Make this path a hard link to the same file as *target*.

   .. note::
      The order of arguments (link, target) is the reverse
      of :func:`os.link`'s.

   .. versionadded:: 3.10


Renaming and deleting
^^^^^^^^^^^^^^^^^^^^^

.. method:: Path.rename(target)

   Rename this file or directory to the given *target*, and return a new
   :class:`!Path` instance pointing to *target*.  On Unix, if *target* exists
   and is a file, it will be replaced silently if the user has permission.
   On Windows, if *target* exists, :exc:`FileExistsError` will be raised.
   *target* can be either a string or another path object::

      >>> p = Path('foo')
      >>> p.open('w').write('some text')
      9
      >>> target = Path('bar')
      >>> p.rename(target)
      PosixPath('bar')
      >>> target.open().read()
      'some text'

   The target path may be absolute or relative. Relative paths are interpreted
   relative to the current working directory, *not* the directory of the
   :class:`!Path` object.

   It is implemented in terms of :func:`os.rename` and gives the same guarantees.

   .. versionchanged:: 3.8
      Added return value, return the new :class:`!Path` instance.


.. method:: Path.replace(target)

   Rename this file or directory to the given *target*, and return a new
   :class:`!Path` instance pointing to *target*.  If *target* points to an
   existing file or empty directory, it will be unconditionally replaced.

   The target path may be absolute or relative. Relative paths are interpreted
   relative to the current working directory, *not* the directory of the
   :class:`!Path` object.

   .. versionchanged:: 3.8
      Added return value, return the new :class:`!Path` instance.


.. method:: Path.unlink(missing_ok=False)

   Remove this file or symbolic link.  If the path points to a directory,
   use :func:`Path.rmdir` instead.

   If *missing_ok* is false (the default), :exc:`FileNotFoundError` is
   raised if the path does not exist.

   If *missing_ok* is true, :exc:`FileNotFoundError` exceptions will be
   ignored (same behavior as the POSIX ``rm -f`` command).

   .. versionchanged:: 3.8
      The *missing_ok* parameter was added.


.. method:: Path.rmdir()

   Remove this directory.  The directory must be empty.


Permissions and ownership
^^^^^^^^^^^^^^^^^^^^^^^^^

.. method:: Path.owner()

   Return the name of the user owning the file.  :exc:`KeyError` is raised
   if the file's user identifier (UID) isn't found in the system database.


.. method:: Path.group()

