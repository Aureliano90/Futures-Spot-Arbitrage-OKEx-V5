from threading import Thread


class MyThread(Thread):
    def __init__(self, target=None, args=(), kwargs=None):
        Thread.__init__(self, target=target, args=args, kwargs=kwargs)
        self.result = None

    def run(self):
        try:
            if self._target:
                self.result = self._target(*self._args, **self._kwargs)
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs

    def get_result(self):
        return self.result
