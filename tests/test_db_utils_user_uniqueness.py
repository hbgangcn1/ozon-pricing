import time

from db_utils import create_user


def test_username_and_email_case_insensitive_uniqueness():
    ts = int(time.time() * 1000)
    base_user = f"CaseUser_{ts}"
    base_mail_upper = f"User{ts}@Mail.com"
    base_mail_lower = base_mail_upper.lower()

    # 创建基准用户
    user_id = create_user(
        base_user, "Strong-P@ss-12345", role="user", email=base_mail_upper,
        is_test_user=True
    )
    assert user_id is not None

    # 用户名大小写不同但相同：应失败（使用不同邮箱避免被邮箱冲突遮蔽）
    result = create_user(
        base_user.lower(), "Strong-P@ss-AAAAB", role="user",
        email=f"another{ts}@mail.com"
    )
    assert result is None

    # 邮箱大小写不同但相同：应失败（使用不同用户名避免被用户名冲突遮蔽）
    result = create_user(
        f"another_user_xyz_{ts}", "Strong-P@ss-BBBB1", role="user",
        email=base_mail_lower
    )
    assert result is None

