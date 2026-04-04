# db/__init__.py
# 用户相关
from db.users import (  # noqa: F401
    create_user,
    verify_user,
    update_user_password,
    delete_user,
    get_user_preferred_mode,
    update_user_preferred_mode,
    find_by_username,
    get_user_by_id,
    get_user_role,
)

# 产品相关
from db.products import (  # noqa: F401
    add_product,
    get_all_products_for_user,
    get_product_by_id,
    delete_product,
    batch_delete_products,
    update_product,
    batch_update_pricing_params,
)

# 管理员相关
from db.admin import (  # noqa: F401
    authenticate_admin,
    get_all_users,
    get_user_detail,
    update_user_subscription_admin,
    freeze_user,
    unfreeze_user,
    delete_user_admin,
    batch_update_users,
    get_audit_logs,
    reset_user_password,
)

# 日志相关
from db.logging_utils import (  # noqa: F401
    log_user_login,
    log_user_behavior,
    log_admin_action,
    create_alert,
)

# 统计相关
from db.statistics import (  # noqa: F401
    get_statistics_cache,
    set_statistics_cache,
    clear_expired_cache,
    clear_all_statistics_cache,
    get_dashboard_stats,
)

# 订阅相关
from db.subscriptions import (  # noqa: F401
    get_user_subscription_info,
    update_user_subscription,
    check_user_subscription_status,
    decrement_user_calculations,
)

# 计划相关
from db.plans import (  # noqa: F401
    get_plans,
    get_plan_by_code,
    get_plan_by_id,
    create_plan,
    update_plan,
    delete_plan,
    toggle_plan_active,
    get_plan_price,
)

# 系统配置
from db.config import (  # noqa: F401
    get_system_config,
    set_system_config,
    is_registration_open,
    get_all_config,
)

# 汇率
from db.exchange import (  # noqa: F401
    get_exchange_rate_fallback,
    update_exchange_rate_fallback,
)

# 物流 CRUD
from db.logistics_crud import (  # noqa: F401
    get_logistics_list,
    get_logistics_by_id,
    create_logistics,
    update_logistics,
    delete_logistics,
    batch_delete_logistics,
)

# 订单
from db.orders import (  # noqa: F401
    get_user_orders,
)

# 会话安全 CRUD
from db.sessions_crud import *  # noqa: F401, F403

# 密码（不改）
from db.password import *  # noqa: F401, F403
