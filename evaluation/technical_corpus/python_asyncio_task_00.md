# Python 3.12.7 asyncio-task 原始文档摘录 1

来源：https://raw.githubusercontent.com/python/cpython/v3.12.7/Doc/library/asyncio-task.rst
许可：PSF License；原始 RST 格式保留，未改写技术陈述。

.. currentmodule:: asyncio


====================
Coroutines and Tasks
====================

This section outlines high-level asyncio APIs to work with coroutines
and Tasks.

.. contents::
   :depth: 1
   :local:


.. _coroutine:

Coroutines
==========

**Source code:** :source:`Lib/asyncio/coroutines.py`

----------------------------------------------------

:term:`Coroutines <coroutine>` declared with the async/await syntax is the
preferred way of writing asyncio applications.  For example, the following
snippet of code prints "hello", waits 1 second,
and then prints "world"::

    >>> import asyncio

    >>> async def main():
    ...     print('hello')
    ...     await asyncio.sleep(1)
    ...     print('world')

    >>> asyncio.run(main())
    hello
    world

Note that simply calling a coroutine will not schedule it to
be executed::

    >>> main()
    <coroutine object main at 0x1053bb7c8>

To actually run a coroutine, asyncio provides the following mechanisms:

* The :func:`asyncio.run` function to run the top-level
  entry point "main()" function (see the above example.)

* Awaiting on a coroutine.  The following snippet of code will
  print "hello" after waiting for 1 second, and then print "world"
  after waiting for *another* 2 seconds::

      import asyncio
      import time

      async def say_after(delay, what):
          await asyncio.sleep(delay)
          print(what)

      async def main():
          print(f"started at {time.strftime('%X')}")

          await say_after(1, 'hello')
          await say_after(2, 'world')

          print(f"finished at {time.strftime('%X')}")

      asyncio.run(main())

  Expected output::

      started at 17:13:52
      hello
      world
      finished at 17:13:55

* The :func:`asyncio.create_task` function to run coroutines
  concurrently as asyncio :class:`Tasks <Task>`.

  Let's modify the above example and run two ``say_after`` coroutines
  *concurrently*::

      async def main():
          task1 = asyncio.create_task(
              say_after(1, 'hello'))

          task2 = asyncio.create_task(
              say_after(2, 'world'))

          print(f"started at {time.strftime('%X')}")

          # Wait until both tasks are completed (should take
          # around 2 seconds.)
          await task1
          await task2

          print(f"finished at {time.strftime('%X')}")

  Note that expected output now shows that the snippet runs
  1 second faster than before::

      started at 17:14:32
      hello
      world
      finished at 17:14:34

* The :class:`asyncio.TaskGroup` class provides a more modern
  alternative to :func:`create_task`.
  Using this API, the last example becomes::

      async def main():
          async with asyncio.TaskGroup() as tg:
              task1 = tg.create_task(
                  say_after(1, 'hello'))

              task2 = tg.create_task(
                  say_after(2, 'world'))

              print(f"started at {time.strftime('%X')}")

          # The await is implicit when the context manager exits.

          print(f"finished at {time.strftime('%X')}")

  The timing and output should be the same as for the previous version.

  .. versionadded:: 3.11
     :class:`asyncio.TaskGroup`.


.. _asyncio-awaitables:

Awaitables
==========

We say that an object is an **awaitable** object if it can be used
in an :keyword:`await` expression.  Many asyncio APIs are designed to
accept awaitables.

There are three main types of *awaitable* objects:
**coroutines**, **Tasks**, and **Futures**.


.. rubric:: Coroutines

Python coroutines are *awaitables* and therefore can be awaited from
other coroutines::

    import asyncio

    async def nested():
        return 42

    async def main():
        # Nothing happens if we just call "nested()".
        # A coroutine object is created but not awaited,
        # so it *won't run at all*.
        nested()

        # Let's do it differently now and await it:
        print(await nested())  # will print "42".

    asyncio.run(main())

.. important::

   In this documentation the term "coroutine" can be used for
   two closely related concepts:

   * a *coroutine function*: an :keyword:`async def` function;

   * a *coroutine object*: an object returned by calling a
     *coroutine function*.


.. rubric:: Tasks

*Tasks* are used to schedule coroutines *concurrently*.

When a coroutine is wrapped into a *Task* with functions like
:func:`asyncio.create_task` the coroutine is automatically
scheduled to run soon::

    import asyncio

    async def nested():
        return 42

    async def main():
        # Schedule nested() to run soon concurrently
        # with "main()".
        task = asyncio.create_task(nested())

        # "task" can now be used to cancel "nested()", or
        # can simply be awaited to wait until it is complete:
        await task

    asyncio.run(main())


.. rubric:: Futures

A :class:`Future` is a special **low-level** awaitable object that
represents an **eventual result** of an asynchronous operation.

When a Future object is *awaited* it means that the coroutine will
wait until the Future is resolved in some other place.

Future objects in asyncio are needed to allow callback-based code
to be used with async/await.

Normally **there is no need** to create Future objects at the
application level code.

Future objects, sometimes exposed by libraries and some asyncio
APIs, can be awaited::

    async def main():
        await function_that_returns_a_future_object()

        # this is also valid:
        await asyncio.gather(
            function_that_returns_a_future_object(),
            some_python_coroutine()
        )

A good example of a low-level function that returns a Future object
is :meth:`loop.run_in_executor`.


Creating Tasks
==============

**Source code:** :source:`Lib/asyncio/tasks.py`

-----------------------------------------------

.. function:: create_task(coro, *, name=None, context=None)

   Wrap the *coro* :ref:`coroutine <coroutine>` into a :class:`Task`
   and schedule its execution.  Return the Task object.

   If *name* is not ``None``, it is set as the name of the task using
   :meth:`Task.set_name`.

   An optional keyword-only *context* argument allows specifying a
   custom :class:`contextvars.Context` for the *coro* to run in.
   The current context copy is created when no *context* is provided.

   The task is executed in the loop returned by :func:`get_running_loop`,
   :exc:`RuntimeError` is raised if there is no running loop in
   current thread.

   .. note::

      :meth:`asyncio.TaskGroup.create_task` is a new alternative
      leveraging structural concurrency; it allows for waiting
      for a group of related tasks with strong safety guarantees.

   .. important::

      Save a reference to the result of this function, to avoid
      a task disappearing mid-execution. The event loop only keeps
      weak references to tasks. A task that isn't referenced elsewhere
      may get garbage collected at any time, even before it's done.
      For reliable "fire-and-forget" background tasks, gather them in
      a collection::

          background_tasks = set()

          for i in range(10):
              task = asyncio.create_task(some_coro(param=i))

              # Add task to the set. This creates a strong reference.
              background_tasks.add(task)

              # To prevent keeping references to finished tasks forever,
              # make each task remove its own reference from the set after
              # completion:
              task.add_done_callback(background_tasks.discard)

   .. versionadded:: 3.7

   .. versionchanged:: 3.8
      Added the *name* parameter.

   .. versionchanged:: 3.11
      Added the *context* parameter.


Task Cancellation
=================

Tasks can easily and safely be cancelled.
When a task is cancelled, :exc:`asyncio.CancelledError` will be raised
in the task at the next opportunity.

It is recommended that coroutines use ``try/finally`` blocks to robustly
perform clean-up logic. In case :exc:`asyncio.CancelledError`
is explicitly caught, it should generally be propagated when
clean-up is complete. :exc:`asyncio.CancelledError` directly subclasses
:exc:`BaseException` so most code will not need to be aware of it.

The asyncio components that enable structured concurrency, like
:class:`asyncio.TaskGroup` and :func:`asyncio.timeout`,
are implemented using cancellation internally and might misbehave if
a coroutine swallows :exc:`asyncio.CancelledError`. Similarly, user code
should not generally call :meth:`uncancel <asyncio.Task.uncancel>`.
However, in cases when suppressing :exc:`asyncio.CancelledError` is
truly desired, it is necessary to also call ``uncancel()`` to completely
remove the cancellation state.

.. _taskgroups:

Task Groups
===========

Task groups combine a task creation API with a convenient
and reliable way to wait for all tasks in the group to finish.

.. class:: TaskGroup()

   An :ref:`asynchronous context manager <async-context-managers>`
   holding a group of tasks.
   Tasks can be added to the group using :meth:`create_task`.
   All tasks are awaited when the context manager exits.

   .. versionadded:: 3.11

   .. method:: create_task(coro, *, name=None, context=None)

      Create a task in this task group.
      The signature matches that of :func:`asyncio.create_task`.

Example::

    async def main():
        async with asyncio.TaskGroup() as tg:
            task1 = tg.create_task(some_coro(...))
            task2 = tg.create_task(another_coro(...))
        print(f"Both tasks have completed now: {task1.result()}, {task2.result()}")

The ``async with`` statement will wait for all tasks in the group to finish.
While waiting, new tasks may still be added to the group
(for example, by passing ``tg`` into one of the coroutines
and calling ``tg.create_task()`` in that coroutine).
Once the last task has finished and the ``async with`` block is exited,
no new tasks may be added to the group.

The first time any of the tasks belonging to the group fails
with an exception other than :exc:`asyncio.CancelledError`,
the remaining tasks in the group are cancelled.
No further tasks can then be added to the group.
At this point, if the body of the ``async with`` statement is still active
(i.e., :meth:`~object.__aexit__` hasn't been called yet),
the task directly containing the ``async with`` statement is also cancelled.
The resulting :exc:`asyncio.CancelledError` will interrupt an ``await``,
but it will not bubble out of the containing ``async with`` statement.

Once all tasks have finished, if any tasks have failed
with an exception other than :exc:`asyncio.CancelledError`,
those exceptions are combined in an
:exc:`ExceptionGroup` or :exc:`BaseExceptionGroup`
(as appropriate; see their documentation)
which is then raised.

Two base exceptions are treated specially:
If any task fails with :exc:`KeyboardInterrupt` or :exc:`SystemExit`,
the task group still cancels the remaining tasks and waits for them,
but then the initial :exc:`KeyboardInterrupt` or :exc:`SystemExit`
is re-raised instead of :exc:`ExceptionGroup` or :exc:`BaseExceptionGroup`.

If the body of the ``async with`` statement exits with an exception
(so :meth:`~object.__aexit__` is called with an exception set),
this is treated the same as if one of the tasks failed:
the remaining tasks are cancelled and then waited for,
and non-cancellation exceptions are grouped into an
exception group and raised.
The exception passed into :meth:`~object.__aexit__`,
unless it is :exc:`asyncio.CancelledError`,
is also included in the exception group.
The same special case is made for
:exc:`KeyboardInterrupt` and :exc:`SystemExit` as in the previous paragraph.


Terminating a Task Group
------------------------

While terminating a task group is not natively supported by the standard
library, termination can be achieved by adding an exception-raising task
to the task group and ignoring the raised exception:

.. code-block:: python

   import asyncio
   from asyncio import TaskGroup

   class TerminateTaskGroup(Exception):
       """Exception raised to terminate a task group."""

   async def force_terminate_task_group():
       """Used to force termination of a task group."""
       raise TerminateTaskGroup()

   async def job(task_id, sleep_time):
       print(f'Task {task_id}: start')
       await asyncio.sleep(sleep_time)
       print(f'Task {task_id}: done')

   async def main():
       try:
           async with TaskGroup() as group:
               # spawn some tasks
               group.create_task(job(1, 0.5))
               group.create_task(job(2, 1.5))
               # sleep for 1 second
               await asyncio.sleep(1)
               # add an exception-raising task to force the group to terminate
               group.create_task(force_terminate_task_group())
       except* TerminateTaskGroup:
           pass

   asyncio.run(main())

Expected output:

.. code-block:: text

   Task 1: start
   Task 2: start
   Task 1: done

Sleeping
========

.. coroutinefunction:: sleep(delay, result=None)

   Block for *delay* seconds.

   If *result* is provided, it is returned to the caller
   when the coroutine completes.

   ``sleep()`` always suspends the current task, allowing other tasks
   to run.

   Setting the delay to 0 provides an optimized path to allow other
   tasks to run. This can be used by long-running functions to avoid
   blocking the event loop for the full duration of the function call.

   .. _asyncio_example_sleep:

   Example of coroutine displaying the current date every second
   for 5 seconds::

    import asyncio
    import datetime

    async def display_date():
        loop = asyncio.get_running_loop()
        end_time = loop.time() + 5.0
        while True:
            print(datetime.datetime.now())
            if (loop.time() + 1.0) >= end_time:
                break
            await asyncio.sleep(1)

    asyncio.run(display_date())


   .. versionchanged:: 3.10
      Removed the *loop* parameter.


Running Tasks Concurrently
==========================

.. awaitablefunction:: gather(*aws, return_exceptions=False)

   Run :ref:`awaitable objects <asyncio-awaitables>` in the *aws*
   sequence *concurrently*.

   If any awaitable in *aws* is a coroutine, it is automatically
   scheduled as a Task.

   If all awaitables are completed successfully, the result is an
   aggregate list of returned values.  The order of result values
   corresponds to the order of awaitables in *aws*.

   If *return_exceptions* is ``False`` (default), the first
   raised exception is immediately propagated to the task that
   awaits on ``gather()``.  Other awaitables in the *aws* sequence
   **won't be cancelled** and will continue to run.

   If *return_exceptions* is ``True``, exceptions are treated the
   same as successful results, and aggregated in the result list.

   If ``gather()`` is *cancelled*, all submitted awaitables
   (that have not completed yet) are also *cancelled*.

   If any Task or Future from the *aws* sequence is *cancelled*, it is
   treated as if it raised :exc:`CancelledError` -- the ``gather()``
   call is **not** cancelled in this case.  This is to prevent the
   cancellation of one submitted Task/Future to cause other
   Tasks/Futures to be cancelled.

   .. note::
      A new alternative to create and run tasks concurrently and
      wait for their completion is :class:`asyncio.TaskGroup`. *TaskGroup*
      provides stronger safety guarantees than *gather* for scheduling a nesting of subtasks:
      if a task (or a subtask, a task scheduled by a task)
      raises an exception, *TaskGroup* will, while *gather* will not,
      cancel the remaining scheduled tasks).

   .. _asyncio_example_gather:

   Example::

      import asyncio

