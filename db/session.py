import logging

from db._proxy import _db

logger = logging.getLogger(__name__)


def _get_st():
    return getattr(_db, "_st", None)


def _read_session_user(st):
    user = None
    try:
        if hasattr(st.session_state, "__contains__"):
            try:
                if "user" in st.session_state:
                    user = st.session_state["user"]
            except (TypeError, AttributeError):
                pass
    except (TypeError, AttributeError):
        pass

    if user is None:
        try:
            if hasattr(st.session_state, "user"):
                user = st.session_state.user
        except (AttributeError, TypeError):
            pass

    return user


def current_user_id():
    st = _get_st()
    user = _read_session_user(st)

    if user is None:
        raise ValueError("用户未登录")

    if isinstance(user, dict):
        return user["id"]
    return getattr(user, "id", None)


def is_admin():
    st = _get_st()
    user = _read_session_user(st)

    if user is None:
        return False

    if isinstance(user, dict):
        role = user.get("role")
    else:
        role = getattr(user, "role", None)
    return role == "admin"


def require_admin():
    if not _db.is_admin():
        raise PermissionError("此操作需要管理员权限")
