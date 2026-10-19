# Python 3.12.7 pathlib 原始文档摘录 4

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/pathlib.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

   Return the name of the group owning the file.  :exc:`KeyError` is raised
   if the file's group identifier (GID) isn't found in the system database.


.. method:: Path.chmod(mode, *, follow_symlinks=True)

   Change the file mode and permissions, like :func:`os.chmod`.

   This method normally follows symlinks. Some Unix flavours support changing
   permissions on the symlink itself; on these platforms you may add the
   argument ``follow_symlinks=False``, or use :meth:`~Path.lchmod`.

   ::

      >>> p = Path('setup.py')
      >>> p.stat().st_mode
      33277
      >>> p.chmod(0o444)
      >>> p.stat().st_mode
      33060

   .. versionchanged:: 3.10
      The *follow_symlinks* parameter was added.


.. method:: Path.lchmod(mode)

   Like :meth:`Path.chmod` but, if the path points to a symbolic link, the
   symbolic link's mode is changed rather than its target's.


Correspondence to tools in the :mod:`os` module
-----------------------------------------------

Below is a table mapping various :mod:`os` functions to their corresponding
:class:`PurePath`/:class:`Path` equivalent.

=====================================   ==============================================
:mod:`os` and :mod:`os.path`            :mod:`pathlib`
=====================================   ==============================================
:func:`os.path.dirname`                 :attr:`PurePath.parent`
:func:`os.path.basename`                :attr:`PurePath.name`
:func:`os.path.splitext`                :attr:`PurePath.stem`, :attr:`PurePath.suffix`
:func:`os.path.join`                    :meth:`PurePath.joinpath`
:func:`os.path.isabs`                   :meth:`PurePath.is_absolute`
:func:`os.path.relpath`                 :meth:`PurePath.relative_to` [1]_
:func:`os.path.expanduser`              :meth:`Path.expanduser` [2]_
:func:`os.path.realpath`                :meth:`Path.resolve`
:func:`os.path.abspath`                 :meth:`Path.absolute` [3]_
:func:`os.path.exists`                  :meth:`Path.exists`
:func:`os.path.isfile`                  :meth:`Path.is_file`
:func:`os.path.isdir`                   :meth:`Path.is_dir`
:func:`os.path.islink`                  :meth:`Path.is_symlink`
:func:`os.path.isjunction`              :meth:`Path.is_junction`
:func:`os.path.ismount`                 :meth:`Path.is_mount`
:func:`os.path.samefile`                :meth:`Path.samefile`
:func:`os.getcwd`                       :meth:`Path.cwd`
:func:`os.stat`                         :meth:`Path.stat`
:func:`os.lstat`                        :meth:`Path.lstat`
:func:`os.listdir`                      :meth:`Path.iterdir`
:func:`os.walk`                         :meth:`Path.walk` [4]_
:func:`os.mkdir`, :func:`os.makedirs`   :meth:`Path.mkdir`
:func:`os.link`                         :meth:`Path.hardlink_to`
:func:`os.symlink`                      :meth:`Path.symlink_to`
:func:`os.readlink`                     :meth:`Path.readlink`
:func:`os.rename`                       :meth:`Path.rename`
:func:`os.replace`                      :meth:`Path.replace`
:func:`os.remove`, :func:`os.unlink`    :meth:`Path.unlink`
:func:`os.rmdir`                        :meth:`Path.rmdir`
:func:`os.chmod`                        :meth:`Path.chmod`
:func:`os.lchmod`                       :meth:`Path.lchmod`
=====================================   ==============================================

.. rubric:: Footnotes

.. [1] :func:`os.path.relpath` calls :func:`~os.path.abspath` to make paths
   absolute and remove "``..``" parts, whereas :meth:`PurePath.relative_to`
   is a lexical operation that raises :exc:`ValueError` when its inputs'
   anchors differ (e.g. if one path is absolute and the other relative.)
.. [2] :func:`os.path.expanduser` returns the path unchanged if the home
   directory can't be resolved, whereas :meth:`Path.expanduser` raises
   :exc:`RuntimeError`.
.. [3] :func:`os.path.abspath` removes "``..``" components without resolving
   symlinks, which may change the meaning of the path, whereas
   :meth:`Path.absolute` leaves any "``..``" components in the path.
.. [4] :func:`os.walk` always follows symlinks when categorizing paths into
   *dirnames* and *filenames*, whereas :meth:`Path.walk` categorizes all
   symlinks into *filenames* when *follow_symlinks* is false (the default.)


