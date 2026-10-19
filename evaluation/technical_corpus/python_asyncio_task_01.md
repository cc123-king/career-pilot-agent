# Python 3.12.7 asyncio-task 原始文档摘录 2

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/asyncio-task.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

      async def factorial(name, number):
          f = 1
          for i in range(2, number + 1):
              print(f"Task {name}: Compute factorial({number}), currently i={i}...")
              await asyncio.sleep(1)
              f *= i
          print(f"Task {name}: factorial({number}) = {f}")
          return f

      async def main():
          # Schedule three calls *concurrently*:
          L = await asyncio.gather(
              factorial("A", 2),
              factorial("B", 3),
              factorial("C", 4),
          )
          print(L)

      asyncio.run(main())

      # Expected output:
      #
      #     Task A: Compute factorial(2), currently i=2...
      #     Task B: Compute factorial(3), currently i=2...
      #     Task C: Compute factorial(4), currently i=2...
      #     Task A: factorial(2) = 2
      #     Task B: Compute factorial(3), currently i=3...
      #     Task C: Compute factorial(4), currently i=3...
      #     Task B: factorial(3) = 6
      #     Task C: Compute factorial(4), currently i=4...
      #     Task C: factorial(4) = 24
      #     [2, 6, 24]

   .. note::
      If *return_exceptions* is false, cancelling gather() after it
      has been marked done won't cancel any submitted awaitables.
      For instance, gather can be marked done after propagating an
      exception to the caller, therefore, calling ``gather.cancel()``
      after catching an exception (raised by one of the awaitables) from
      gather won't cancel any other awaitables.

   .. versionchanged:: 3.7
      If the *gather* itself is cancelled, the cancellation is
      propagated regardless of *return_exceptions*.

   .. versionchanged:: 3.10
      Removed the *loop* parameter.

   .. deprecated:: 3.10
      Deprecation warning is emitted if no positional arguments are provided
      or not all positional arguments are Future-like objects
      and there is no running event loop.


.. _eager-task-factory:

Eager Task Factory
==================

.. function:: eager_task_factory(loop, coro, *, name=None, context=None)

    A task factory for eager task execution.

    When using this factory (via :meth:`loop.set_task_factory(asyncio.eager_task_factory) <loop.set_task_factory>`),
    coroutines begin execution synchronously during :class:`Task` construction.
    Tasks are only scheduled on the event loop if they block.
    This can be a performance improvement as the overhead of loop scheduling
    is avoided for coroutines that complete synchronously.

    A common example where this is beneficial is coroutines which employ
    caching or memoization to avoid actual I/O when possible.

    .. note::

        Immediate execution of the coroutine is a semantic change.
        If the coroutine returns or raises, the task is never scheduled
        to the event loop. If the coroutine execution blocks, the task is
        scheduled to the event loop. This change may introduce behavior
        changes to existing applications. For example,
        the application's task execution order is likely to change.

    .. versionadded:: 3.12

.. function:: create_eager_task_factory(custom_task_constructor)

    Create an eager task factory, similar to :func:`eager_task_factory`,
    using the provided *custom_task_constructor* when creating a new task instead
    of the default :class:`Task`.

    *custom_task_constructor* must be a *callable* with the signature matching
    the signature of :class:`Task.__init__ <Task>`.
    The callable must return a :class:`asyncio.Task`-compatible object.

    This function returns a *callable* intended to be used as a task factory of an
    event loop via :meth:`loop.set_task_factory(factory) <loop.set_task_factory>`).

    .. versionadded:: 3.12


Shielding From Cancellation
===========================

.. awaitablefunction:: shield(aw)

   Protect an :ref:`awaitable object <asyncio-awaitables>`
   from being :meth:`cancelled <Task.cancel>`.

   If *aw* is a coroutine it is automatically scheduled as a Task.

   The statement::

       task = asyncio.create_task(something())
       res = await shield(task)

   is equivalent to::

       res = await something()

   *except* that if the coroutine containing it is cancelled, the
   Task running in ``something()`` is not cancelled.  From the point
   of view of ``something()``, the cancellation did not happen.
   Although its caller is still cancelled, so the "await" expression
   still raises a :exc:`CancelledError`.

   If ``something()`` is cancelled by other means (i.e. from within
   itself) that would also cancel ``shield()``.

   If it is desired to completely ignore cancellation (not recommended)
   the ``shield()`` function should be combined with a try/except
   clause, as follows::

       task = asyncio.create_task(something())
       try:
           res = await shield(task)
       except CancelledError:
           res = None

   .. important::

      Save a reference to tasks passed to this function, to avoid
      a task disappearing mid-execution. The event loop only keeps
      weak references to tasks. A task that isn't referenced elsewhere
      may get garbage collected at any time, even before it's done.

   .. versionchanged:: 3.10
      Removed the *loop* parameter.

   .. deprecated:: 3.10
      Deprecation warning is emitted if *aw* is not Future-like object
      and there is no running event loop.


Timeouts
========

.. function:: timeout(delay)

    Return an :ref:`asynchronous context manager <async-context-managers>`
    that can be used to limit the amount of time spent waiting on
    something.

    *delay* can either be ``None``, or a float/int number of
    seconds to wait. If *delay* is ``None``, no time limit will
    be applied; this can be useful if the delay is unknown when
    the context manager is created.

    In either case, the context manager can be rescheduled after
    creation using :meth:`Timeout.reschedule`.

    Example::

        async def main():
            async with asyncio.timeout(10):
                await long_running_task()

    If ``long_running_task`` takes more than 10 seconds to complete,
    the context manager will cancel the current task and handle
    the resulting :exc:`asyncio.CancelledError` internally, transforming it
    into a :exc:`TimeoutError` which can be caught and handled.

    .. note::

      The :func:`asyncio.timeout` context manager is what transforms
      the :exc:`asyncio.CancelledError` into a :exc:`TimeoutError`,
      which means the :exc:`TimeoutError` can only be caught
      *outside* of the context manager.

    Example of catching :exc:`TimeoutError`::

        async def main():
            try:
                async with asyncio.timeout(10):
                    await long_running_task()
            except TimeoutError:
                print("The long operation timed out, but we've handled it.")

            print("This statement will run regardless.")

    The context manager produced by :func:`asyncio.timeout` can be
    rescheduled to a different deadline and inspected.

    .. class:: Timeout(when)

       An :ref:`asynchronous context manager <async-context-managers>`
       for cancelling overdue coroutines.

       ``when`` should be an absolute time at which the context should time out,
       as measured by the event loop's clock:

       - If ``when`` is ``None``, the timeout will never trigger.
       - If ``when < loop.time()``, the timeout will trigger on the next
         iteration of the event loop.

        .. method:: when() -> float | None

           Return the current deadline, or ``None`` if the current
           deadline is not set.

        .. method:: reschedule(when: float | None)

            Reschedule the timeout.

        .. method:: expired() -> bool

           Return whether the context manager has exceeded its deadline
           (expired).

    Example::

        async def main():
            try:
                # We do not know the timeout when starting, so we pass ``None``.
                async with asyncio.timeout(None) as cm:
                    # We know the timeout now, so we reschedule it.
                    new_deadline = get_running_loop().time() + 10
                    cm.reschedule(new_deadline)

                    await long_running_task()
            except TimeoutError:
                pass

            if cm.expired():
                print("Looks like we haven't finished on time.")

    Timeout context managers can be safely nested.

    .. versionadded:: 3.11

.. function:: timeout_at(when)

   Similar to :func:`asyncio.timeout`, except *when* is the absolute time
   to stop waiting, or ``None``.

   Example::

      async def main():
          loop = get_running_loop()
          deadline = loop.time() + 20
          try:
              async with asyncio.timeout_at(deadline):
                  await long_running_task()
          except TimeoutError:
              print("The long operation timed out, but we've handled it.")

          print("This statement will run regardless.")

   .. versionadded:: 3.11

.. coroutinefunction:: wait_for(aw, timeout)

   Wait for the *aw* :ref:`awaitable <asyncio-awaitables>`
   to complete with a timeout.

   If *aw* is a coroutine it is automatically scheduled as a Task.

   *timeout* can either be ``None`` or a float or int number of seconds
   to wait for.  If *timeout* is ``None``, block until the future
   completes.

   If a timeout occurs, it cancels the task and raises
   :exc:`TimeoutError`.

   To avoid the task :meth:`cancellation <Task.cancel>`,
   wrap it in :func:`shield`.

   The function will wait until the future is actually cancelled,
   so the total wait time may exceed the *timeout*. If an exception
   happens during cancellation, it is propagated.

   If the wait is cancelled, the future *aw* is also cancelled.

   .. _asyncio_example_waitfor:

   Example::

       async def eternity():
           # Sleep for one hour
           await asyncio.sleep(3600)
           print('yay!')

       async def main():
           # Wait for at most 1 second
           try:
               await asyncio.wait_for(eternity(), timeout=1.0)
           except TimeoutError:
               print('timeout!')

       asyncio.run(main())

       # Expected output:
       #
       #     timeout!

   .. versionchanged:: 3.7
      When *aw* is cancelled due to a timeout, ``wait_for`` waits
      for *aw* to be cancelled.  Previously, it raised
      :exc:`TimeoutError` immediately.

   .. versionchanged:: 3.10
      Removed the *loop* parameter.

   .. versionchanged:: 3.11
      Raises :exc:`TimeoutError` instead of :exc:`asyncio.TimeoutError`.


Waiting Primitives
==================

.. coroutinefunction:: wait(aws, *, timeout=None, return_when=ALL_COMPLETED)

   Run :class:`~asyncio.Future` and :class:`~asyncio.Task` instances in the *aws*
   iterable concurrently and block until the condition specified
   by *return_when*.

   The *aws* iterable must not be empty.

   Returns two sets of Tasks/Futures: ``(done, pending)``.

   Usage::

        done, pending = await asyncio.wait(aws)

   *timeout* (a float or int), if specified, can be used to control
   the maximum number of seconds to wait before returning.

   Note that this function does not raise :exc:`TimeoutError`.
   Futures or Tasks that aren't done when the timeout occurs are simply
   returned in the second set.

   *return_when* indicates when this function should return.  It must
   be one of the following constants:

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

   Unlike :func:`~asyncio.wait_for`, ``wait()`` does not cancel the
   futures when a timeout occurs.

   .. versionchanged:: 3.10
      Removed the *loop* parameter.

   .. versionchanged:: 3.11
      Passing coroutine objects to ``wait()`` directly is forbidden.

   .. versionchanged:: 3.12
      Added support for generators yielding tasks.


.. function:: as_completed(aws, *, timeout=None)

   Run :ref:`awaitable objects <asyncio-awaitables>` in the *aws*
   iterable concurrently.  Return an iterator of coroutines.
   Each coroutine returned can be awaited to get the earliest next
   result from the iterable of the remaining awaitables.

   Raises :exc:`TimeoutError` if the timeout occurs before
   all Futures are done.

   Example::

       for coro in as_completed(aws):
           earliest_result = await coro
           # ...

   .. versionchanged:: 3.10
      Removed the *loop* parameter.

   .. deprecated:: 3.10
      Deprecation warning is emitted if not all awaitable objects in the *aws*
      iterable are Future-like objects and there is no running event loop.

   .. versionchanged:: 3.12
      Added support for generators yielding tasks.


Running in Threads
==================

.. coroutinefunction:: to_thread(func, /, *args, **kwargs)

   Asynchronously run function *func* in a separate thread.

   Any \*args and \*\*kwargs supplied for this function are directly passed
   to *func*. Also, the current :class:`contextvars.Context` is propagated,
   allowing context variables from the event loop thread to be accessed in the
   separate thread.

   Return a coroutine that can be awaited to get the eventual result of *func*.

   This coroutine function is primarily intended to be used for executing
   IO-bound functions/methods that would otherwise block the event loop if
   they were run in the main thread. For example::

       def blocking_io():
           print(f"start blocking_io at {time.strftime('%X')}")
           # Note that time.sleep() can be replaced with any blocking
           # IO-bound operation, such as file operations.
           time.sleep(1)
           print(f"blocking_io complete at {time.strftime('%X')}")

       async def main():
           print(f"started main at {time.strftime('%X')}")

           await asyncio.gather(
               asyncio.to_thread(blocking_io),
               asyncio.sleep(1))

           print(f"finished main at {time.strftime('%X')}")


       asyncio.run(main())

       # Expected output:
       #
       # started main at 19:50:53
       # start blocking_io at 19:50:53
       # blocking_io complete at 19:50:54
       # finished main at 19:50:54

   Directly calling ``blocking_io()`` in any coroutine would block the event loop
   for its duration, resulting in an additional 1 second of run time. Instead,
   by using ``asyncio.to_thread()``, we can run it in a separate thread without
   blocking the event loop.

   .. note::

      Due to the :term:`GIL`, ``asyncio.to_thread()`` can typically only be used
      to make IO-bound functions non-blocking. However, for extension modules
      that release the GIL or alternative Python implementations that don't
      have one, ``asyncio.to_thread()`` can also be used for CPU-bound functions.

   .. versionadded:: 3.9


Scheduling From Other Threads
=============================

.. function:: run_coroutine_threadsafe(coro, loop)

   Submit a coroutine to the given event loop.  Thread-safe.

   Return a :class:`concurrent.futures.Future` to wait for the result
   from another OS thread.

   This function is meant to be called from a different OS thread
   than the one where the event loop is running.  Example::

     # Create a coroutine
     coro = asyncio.sleep(1, result=3)

     # Submit the coroutine to a given loop
     future = asyncio.run_coroutine_threadsafe(coro, loop)

