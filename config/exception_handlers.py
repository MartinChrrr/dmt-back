from rest_framework.views import exception_handler


def jsend_exception_handler(exc, context):
    """
    Custom exception handler that formats errors in JSend format.

    The renderer detects the JSend keys and skips double-wrapping.
    """
    response = exception_handler(exc, context)

    if response is None:
        return None

    status_code = response.status_code

    if 400 <= status_code < 500:
        response.data = {
            'status': 'fail',
            'data': response.data,
        }
    elif status_code >= 500:
        message = 'Internal server error'
        if isinstance(response.data, dict) and 'detail' in response.data:
            message = str(response.data['detail'])
        response.data = {
            'status': 'error',
            'message': message,
        }

    return response
