from rest_framework.pagination import CursorPagination
from rest_framework.response import Response


class DefaultCursorPagination(CursorPagination):
    """목록 API 공용 커서 페이지네이션 — ?cursor=&limit="""

    page_size = 20
    max_page_size = 100
    page_size_query_param = "limit"
    cursor_query_param = "cursor"
    ordering = "-created_at"

    def get_paginated_response(self, data):
        return Response(
            {
                "results": data,
                "next_cursor": self.get_next_link(),
                "previous_cursor": self.get_previous_link(),
            }
        )
