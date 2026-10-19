# Python 3.12.7 asyncio-task 原始文档摘录 3

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/asyncio-task.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

     # Wait for the result with an optional timeout argument
     assert future.result(timeout) == 3

   If an exception is raised in the coroutine, the returned Future
   will be notified.  It can also be used to cancel the task in
   the event loop::

     try:
         result = future.result(timeout)
     except TimeoutError:
         print('The coroutine took too long, cancelling the task...')
         future.cancel()
     except Exception as exc:
         print(f'The coroutine raised an exception: {exc!r}')
     else:
         print(f'The coroutine returned: {result!r}')

   See the :ref:`concurrency and multithreading <asyncio-multithreading>`
   section of the documentation.

   Unlike other asyncio functions this function requires the *loop*
   argument to be passed explicitly.

   .. versionadded:: 3.5.1


Introspection
=============


.. function:: current_task(loop=None)

   Return the currently running :class:`Task` instance, or ``None`` if
   no task is running.

   If *loop* is ``None`` :func:`get_running_loop` is used to get
   the current loop.

   .. versionadded:: 3.7


.. function:: all_tasks(loop=None)

   Return a set of not yet finished :class:`Task` objects run by
   the loop.

   If *loop* is ``None``, :func:`get_running_loop` is used for getting
   current loop.

   .. versionadded:: 3.7


.. function:: iscoroutine(obj)

   Return ``True`` if *obj* is a coroutine object.

   .. versionadded:: 3.4


Task Object
===========

.. class:: Task(coro, *, loop=None, name=None, context=None, eager_start=False)

   A :class:`Future-like <Future>` object that runs a Python
   :ref:`coroutine <coroutine>`.  Not thread-safe.

   Tasks are used to run coroutines in event loops.
   If a coroutine awaits on a Future, the Task suspends
   the execution of the coroutine and waits for the completion
   of the Future.  When the Future is *done*, the execution of
   the wrapped coroutine resumes.

   Event loops use cooperative scheduling: an event loop runs
   one Task at a time.  While a Task awaits for the completion of a
   Future, the event loop runs other Tasks, callbacks, or performs
   IO operations.

   Use the high-level :func:`asyncio.create_task` function to create
   Tasks, or the low-level :meth:`loop.create_task` or
   :func:`ensure_future` functions.  Manual instantiation of Tasks
   is discouraged.

   To cancel a running Task use the :meth:`cancel` method.  Calling it
   will cause the Task to throw a :exc:`CancelledError` exception into
   the wrapped coroutine.  If a coroutine is awaiting on a Future
   object during cancellation, the Future object will be cancelled.

   :meth:`cancelled` can be used to check if the Task was cancelled.
   The method returns ``True`` if the wrapped coroutine did not
   suppress the :exc:`CancelledError` exception and was actually
   cancelled.

   :class:`asyncio.Task` inherits from :class:`Future` all of its
   APIs except :meth:`Future.set_result` and
   :meth:`Future.set_exception`.

   An optional keyword-only *context* argument allows specifying a
   custom :class:`contextvars.Context` for the *coro* to run in.
   If no *context* is provided, the Task copies the current context
   and later runs its coroutine in the copied context.

   An optional keyword-only *eager_start* argument allows eagerly starting
   the execution of the :class:`asyncio.Task` at task creation time.
   If set to ``True`` and the event loop is running, the task will start
   executing the coroutine immediately, until the first time the coroutine
   blocks. If the coroutine returns or raises without blocking, the task
   will be finished eagerly and will skip scheduling to the event loop.

   .. versionchanged:: 3.7
      Added support for the :mod:`contextvars` module.

   .. versionchanged:: 3.8
      Added the *name* parameter.

   .. deprecated:: 3.10
      Deprecation warning is emitted if *loop* is not specified
      and there is no running event loop.

   .. versionchanged:: 3.11
      Added the *context* parameter.

   .. versionchanged:: 3.12
      Added the *eager_start* parameter.

   .. method:: done()

      Return ``True`` if the Task is *done*.

      A Task is *done* when the wrapped coroutine either returned
      a value, raised an exception, or the Task was cancelled.

   .. method:: result()

      Return the result of the Task.

      If the Task is *done*, the result of the wrapped coroutine
      is returned (or if the coroutine raised an exception, that
      exception is re-raised.)

      If the Task has been *cancelled*, this method raises
      a :exc:`CancelledError` exception.

      If the Task's result isn't yet available, this method raises
      an :exc:`InvalidStateError` exception.

   .. method:: exception()

      Return the exception of the Task.

      If the wrapped coroutine raised an exception that exception
      is returned.  If the wrapped coroutine returned normally
      this method returns ``None``.

      If the Task has been *cancelled*, this method raises a
      :exc:`CancelledError` exception.

      If the Task isn't *done* yet, this method raises an
      :exc:`InvalidStateError` exception.

   .. method:: add_done_callback(callback, *, context=None)

      Add a callback to be run when the Task is *done*.

      This method should only be used in low-level callback-based code.

      See the documentation of :meth:`Future.add_done_callback`
      for more details.

   .. method:: remove_done_callback(callback)

      Remove *callback* from the callbacks list.

      This method should only be used in low-level callback-based code.

      See the documentation of :meth:`Future.remove_done_callback`
      for more details.

   .. method:: get_stack(*, limit=None)

      Return the list of stack frames for this Task.

      If the wrapped coroutine is not done, this returns the stack
      where it is suspended.  If the coroutine has completed
      successfully or was cancelled, this returns an empty list.
      If the coroutine was terminated by an exception, this returns
      the list of traceback frames.

      The frames are always ordered from oldest to newest.

      Only one stack frame is returned for a suspended coroutine.

      The optional *limit* argument sets the maximum number of frames
      to return; by default all available frames are returned.
      The ordering of the returned list differs depending on whether
      a stack or a traceback is returned: the newest frames of a
      stack are returned, but the oldest frames of a traceback are
      returned.  (This matches the behavior of the traceback module.)

   .. method:: print_stack(*, limit=None, file=None)

      Print the stack or traceback for this Task.

      This produces output similar to that of the traceback module
      for the frames retrieved by :meth:`get_stack`.

      The *limit* argument is passed to :meth:`get_stack` directly.

      The *file* argument is an I/O stream to which the output
      is written; by default output is written to :data:`sys.stdout`.

   .. method:: get_coro()

      Return the coroutine object wrapped by the :class:`Task`.

      .. note::

         This will return ``None`` for Tasks which have already
         completed eagerly. See the :ref:`Eager Task Factory <eager-task-factory>`.

      .. versionadded:: 3.8

      .. versionchanged:: 3.12

         Newly added eager task execution means result may be ``None``.

   .. method:: get_context()

      Return the :class:`contextvars.Context` object
      associated with the task.

      .. versionadded:: 3.12

   .. method:: get_name()

      Return the name of the Task.

      If no name has been explicitly assigned to the Task, the default
      asyncio Task implementation generates a default name during
      instantiation.

      .. versionadded:: 3.8

   .. method:: set_name(value)

      Set the name of the Task.

      The *value* argument can be any object, which is then
      converted to a string.

      In the default Task implementation, the name will be visible
      in the :func:`repr` output of a task object.

      .. versionadded:: 3.8

   .. method:: cancel(msg=None)

      Request the Task to be cancelled.

      This arranges for a :exc:`CancelledError` exception to be thrown
      into the wrapped coroutine on the next cycle of the event loop.

      The coroutine then has a chance to clean up or even deny the
      request by suppressing the exception with a :keyword:`try` ...
      ... ``except CancelledError`` ... :keyword:`finally` block.
      Therefore, unlike :meth:`Future.cancel`, :meth:`Task.cancel` does
      not guarantee that the Task will be cancelled, although
      suppressing cancellation completely is not common and is actively
      discouraged.  Should the coroutine nevertheless decide to suppress
      the cancellation, it needs to call :meth:`Task.uncancel` in addition
      to catching the exception.

      .. versionchanged:: 3.9
         Added the *msg* parameter.

      .. versionchanged:: 3.11
         The ``msg`` parameter is propagated from cancelled task to its awaiter.

      .. _asyncio_example_task_cancel:

      The following example illustrates how coroutines can intercept
      the cancellation request::

          async def cancel_me():
              print('cancel_me(): before sleep')

              try:
                  # Wait for 1 hour
                  await asyncio.sleep(3600)
              except asyncio.CancelledError:
                  print('cancel_me(): cancel sleep')
                  raise
              finally:
                  print('cancel_me(): after sleep')

          async def main():
              # Create a "cancel_me" Task
              task = asyncio.create_task(cancel_me())

              # Wait for 1 second
              await asyncio.sleep(1)

              task.cancel()
              try:
                  await task
              except asyncio.CancelledError:
                  print("main(): cancel_me is cancelled now")

          asyncio.run(main())

          # Expected output:
          #
          #     cancel_me(): before sleep
          #     cancel_me(): cancel sleep
          #     cancel_me(): after sleep
          #     main(): cancel_me is cancelled now

   .. method:: cancelled()

      Return ``True`` if the Task is *cancelled*.

      The Task is *cancelled* when the cancellation was requested with
      :meth:`cancel` and the wrapped coroutine propagated the
      :exc:`CancelledError` exception thrown into it.

   .. method:: uncancel()

      Decrement the count of cancellation requests to this Task.

      Returns the remaining number of cancellation requests.

      Note that once execution of a cancelled task completed, further
      calls to :meth:`uncancel` are ineffective.

      .. versionadded:: 3.11

      This method is used by asyncio's internals and isn't expected to be
      used by end-user code.  In particular, if a Task gets successfully
      uncancelled, this allows for elements of structured concurrency like
      :ref:`taskgroups` and :func:`asyncio.timeout` to continue running,
      isolating cancellation to the respective structured block.
      For example::

        async def make_request_with_timeout():
            try:
                async with asyncio.timeout(1):
                    # Structured block affected by the timeout:
                    await make_request()
                    await make_another_request()
            except TimeoutError:
                log("There was a timeout")
            # Outer code not affected by the timeout:
            await unrelated_code()

      While the block with ``make_request()`` and ``make_another_request()``
      might get cancelled due to the timeout, ``unrelated_code()`` should
      continue running even in case of the timeout.  This is implemented
      with :meth:`uncancel`.  :class:`TaskGroup` context managers use
      :func:`uncancel` in a similar fashion.

      If end-user code is, for some reason, suppressing cancellation by
      catching :exc:`CancelledError`, it needs to call this method to remove
      the cancellation state.

   .. method:: cancelling()

      Return the number of pending cancellation requests to this Task, i.e.,
      the number of calls to :meth:`cancel` less the number of
      :meth:`uncancel` calls.

      Note that if this number is greater than zero but the Task is
      still executing, :meth:`cancelled` will still return ``False``.
      This is because this number can be lowered by calling :meth:`uncancel`,
      which can lead to the task not being cancelled after all if the
      cancellation requests go down to zero.

      This method is used by asyncio's internals and isn't expected to be
      used by end-user code.  See :meth:`uncancel` for more details.

      .. versionadded:: 3.11


