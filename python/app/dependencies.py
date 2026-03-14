from fastapi import Header, HTTPException

def get_optional_user_uuid(x_user_uuid: str | None = Header(default=None)):
    return x_user_uuid

def require_user_uuid(x_user_uuid: str | None = Header(default=None)):
    if not x_user_uuid:
        raise HTTPException(status_code=401, detail="사용자 인증 정보가 없습니다.")
    return x_user_uuid