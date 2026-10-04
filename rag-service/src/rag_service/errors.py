class AppError(Exception):
    """Error controlado: mensaje seguro para la CLI y registros."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
