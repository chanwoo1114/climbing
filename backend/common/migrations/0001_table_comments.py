"""Django/서드파티 내장 테이블에 코멘트를 단다.

우리 모델은 Meta.db_table_comment 로 관리하지만, auth·session·admin·
token_blacklist 테이블은 모델을 수정할 수 없으므로 여기서 직접 COMMENT 를 건다.
PyCharm 등 DB 툴의 public 스키마에서 테이블 용도가 바로 보이게 하기 위함.
"""
from django.db import migrations

TABLE_COMMENTS = {
    # --- Django 인증/권한 ---
    "auth_group": "권한 그룹 — 사용자 묶음에 권한을 한 번에 부여 (admin 용)",
    "auth_permission": "개별 권한 정의 — 모델별 add/change/delete/view",
    "auth_group_permissions": "그룹 ↔ 권한 M:N 매핑",
    "accounts_user_groups": "회원 ↔ 권한그룹 M:N 매핑",
    "accounts_user_user_permissions": "회원에게 직접 부여한 개별 권한 M:N 매핑",
    # --- Django 내부 ---
    "django_migrations": "마이그레이션 적용 이력 — Django가 직접 관리",
    "django_content_type": "모델 종류 레지스트리 — 권한·제네릭 FK가 참조",
    "django_session": "세션 저장소 — admin 로그인용 (API는 JWT 사용)",
    "django_admin_log": "admin 화면에서의 변경 이력 로그",
    # --- SimpleJWT ---
    "token_blacklist_outstandingtoken": (
        "발급된 refresh 토큰 목록 — 만료/블랙리스트 추적용"
    ),
    "token_blacklist_blacklistedtoken": (
        "무효화된 refresh 토큰 — 로그아웃/회전 시 등록되어 재사용을 막는다"
    ),
    # --- PostGIS ---
    "spatial_ref_sys": "PostGIS 좌표계 정의 테이블 — 확장이 자동 생성 (건드리지 말 것)",
}


def apply_comments(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table, comment in TABLE_COMMENTS.items():
            cursor.execute("SELECT to_regclass(%s)", [f"public.{table}"])
            if cursor.fetchone()[0] is None:
                continue  # 아직 없는 테이블은 건너뛴다
            cursor.execute(f'COMMENT ON TABLE public."{table}" IS %s', [comment])


def remove_comments(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in TABLE_COMMENTS:
            cursor.execute("SELECT to_regclass(%s)", [f"public.{table}"])
            if cursor.fetchone()[0] is None:
                continue
            cursor.execute(f'COMMENT ON TABLE public."{table}" IS NULL')


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("admin", "0001_initial"),
        ("token_blacklist", "0001_initial"),
    ]

    operations = [migrations.RunPython(apply_comments, remove_comments)]
