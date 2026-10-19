# Python 3.12.7 concurrent.futures 原始文档摘录 2

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/concurrent.futures.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

      Attaches the callable *fn* to the future.  *fn* will be called, with the
      future as its only argument, when the future is cancelled or finishes
      running.

      Added callables are called in the order that they were added and are
      always called in a thread belonging to the process that added them.  If
      the callable raises an :exc:`Exception` subclass, it will be logged and
      ignored.  If the callable raises a :exc:`BaseException` subclass, the
      behavior is undefined.

      If the future has already completed or been cancelled, *fn* will be
      called immediately.

   The following :class:`Future` methods are meant for use in unit tests and
   :class:`Executor` implementations.

   .. method:: set_running_or_notify_cancel()

      This method should only be called by :class:`Executor` implementations
      before executing the work associated with the :class:`Future` and by unit
      tests.

      If the method returns ``False`` then the :class:`Future` was cancelled,
      i.e. :meth:`Future.cancel` was called and returned ``True``.  Any threads
      waiting on the :class:`Future` completing (i.e. through
      :func:`as_completed` or :func:`wait`) will be woken up.

      If the method returns ``True`` then the :class:`Future` was not cancelled
      and has been put in the running state, i.e. calls to
      :meth:`Future.running` will return ``True``.

      This method can only be called once and cannot be called after
      :meth:`Future.set_result` or :meth:`Future.set_exception` have been
      called.

   .. method:: set_result(result)

      Sets the result of the work associated with the :class:`Future` to
      *result*.

      This method should only be used by :class:`Executor` implementations and
      unit tests.

      .. versionchanged:: 3.8
         This method raises
         :exc:`concurrent.futures.InvalidStateError` if the :class:`Future` is
         already done.

   .. method:: set_exception(exception)

      Sets the result of the work associated with the :class:`Future` to the
      :class:`Exception` *exception*.

      This method should only be used by :class:`Executor` implementations and
      unit tests.

      .. versionchanged:: 3.8
         This method raises
         :exc:`concurrent.futures.InvalidStateError` if the :class:`Future` is
         already done.

Module Functions
----------------

.. function:: wait(fs, timeout=None, return_when=ALL_COMPLETED)

   Wait for the :class:`Future` instances (possibly created by different
   :class:`Executor` instances) given by *fs* to complete. Duplicate futures
   given to *fs* are removed and will be returned only once. Returns a named
   2-tuple of sets.  The first set, named ``done``, contains the futures that
   completed (finished or cancelled futures) before the wait completed.  The
   second set, named ``not_done``, contains the futures that did not complete
   (pending or running futures).

   *timeout* can be used to control the maximum number of seconds to wait before
   returning.  *timeout* can be an int or float.  If *timeout* is not specified
   or ``None``, there is no limit to the wait time.

   *return_when* indicates when this function should return.  It must be one of
   the following constants:

   .. list-table::
      :header-rows: 1

      * - Constant
        - Description

      * - .. data:: FIRST_COMPLETED
        - The function will return when any future finishes or is cancelled.

      * - .. data:: FIRST_EXCEPTION
        - The function will return when any future finishes by raising an
          exception. If no future raises an exception
          then it is equivalent to :const:`ALL_COMPLETED`.

      * - .. data:: ALL_COMPLETED
        - The function will return when all futures finish or are cancelled.

.. function:: as_completed(fs, timeout=None)

   Returns an iterator over the :class:`Future` instances (possibly created by
   different :class:`Executor` instances) given by *fs* that yields futures as
   they complete (finished or cancelled futures). Any futures given by *fs* that
   are duplicated will be returned once. Any futures that completed before
   :func:`as_completed` is called will be yielded first.  The returned iterator
   raises a :exc:`TimeoutError` if :meth:`~iterator.__next__`
   is called and the result isn't available after *timeout* seconds from the
   original call to :func:`as_completed`.  *timeout* can be an int or float. If
   *timeout* is not specified or ``None``, there is no limit to the wait time.


.. seealso::

   :pep:`3148` -- futures - execute computations asynchronously
      The proposal which described this feature for inclusion in the Python
      standard library.


Exception classes
-----------------

.. currentmodule:: concurrent.futures

.. exception:: CancelledError

   Raised when a future is cancelled.

.. exception:: TimeoutError

   A deprecated alias of :exc:`TimeoutError`,
   raised when a future operation exceeds the given timeout.

   .. versionchanged:: 3.11

      This class was made an alias of :exc:`TimeoutError`.


.. exception:: BrokenExecutor

   Derived from :exc:`RuntimeError`, this exception class is raised
   when an executor is broken for some reason, and cannot be used
   to submit or execute new tasks.

   .. versionadded:: 3.7

.. exception:: InvalidStateError

   Raised when an operation is performed on a future that is not allowed
   in the current state.

   .. versionadded:: 3.8

.. currentmodule:: concurrent.futures.thread

.. exception:: BrokenThreadPool

   Derived from :exc:`~concurrent.futures.BrokenExecutor`, this exception
   class is raised when one of the workers
   of a :class:`~concurrent.futures.ThreadPoolExecutor`
   has failed initializing.

   .. versionadded:: 3.7

.. currentmodule:: concurrent.futures.process

.. exception:: BrokenProcessPool

   Derived from :exc:`~concurrent.futures.BrokenExecutor` (formerly
   :exc:`RuntimeError`), this exception class is raised when one of the
   workers of a :class:`~concurrent.futures.ProcessPoolExecutor`
   has terminated in a non-clean
   fashion (for example, if it was killed from the outside).

   .. versionadded:: 3.3


