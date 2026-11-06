class AppError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def fail(message, status=400):
    raise AppError(message, status)


