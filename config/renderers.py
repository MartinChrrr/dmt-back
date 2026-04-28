from rest_framework.renderers import JSONRenderer


class JSendRenderer(JSONRenderer):
    """
    Wraps all DRF JSON responses in JSend format.

    Success (2xx): {"status": "success", "data": <original_data>}
    Fail (4xx):    {"status": "fail", "data": <original_data>}
    Error (5xx):   {"status": "error", "message": "Internal server error"}
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get('response') if renderer_context else None

        if response is None:
            return super().render(data, accepted_media_type, renderer_context)

        status_code = response.status_code

        # 204 No Content — no body per HTTP spec
        if status_code == 204:
            return b''

        # Already JSend-formatted (e.g. from our exception handler)
        if (
            isinstance(data, dict)
            and 'status' in data
            and data.get('status') in ('success', 'fail', 'error')
        ):
            return super().render(data, accepted_media_type, renderer_context)

        if 200 <= status_code < 300:
            jsend_data = {
                'status': 'success',
                'data': data,
            }
        elif 400 <= status_code < 500:
            jsend_data = {
                'status': 'fail',
                'data': data,
            }
        else:
            message = 'Internal server error'
            if isinstance(data, dict) and 'detail' in data:
                message = str(data['detail'])
            elif isinstance(data, str):
                message = data
            jsend_data = {
                'status': 'error',
                'message': message,
            }

        # Update response.data so DRF test client reflects JSend format
        response.data = jsend_data

        return super().render(jsend_data, accepted_media_type, renderer_context)
