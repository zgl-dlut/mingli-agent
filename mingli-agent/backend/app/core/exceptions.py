from fastapi import HTTPException, status


class NotAuthenticated(HTTPException):
    def __init__(self, detail: str = "未登录"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionDenied(HTTPException):
    def __init__(self, detail: str = "权限不足"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class InsufficientPoints(HTTPException):
    def __init__(self, detail: str = "积分不足"):
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail,
        )


class ResourceNotFound(HTTPException):
    def __init__(self, detail: str = "资源不存在"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )


class BusinessError(HTTPException):
    def __init__(self, detail: str = "业务错误"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
