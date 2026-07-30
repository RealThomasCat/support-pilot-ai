class DatabaseWriteError(RuntimeError):
    """
    Raised when a database write cannot be committed safely.
    """
