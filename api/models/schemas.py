from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, PlainSerializer


DecimalField = Annotated[
    Decimal,
    PlainSerializer(lambda x: float(x), return_type=float),
]


class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    email: Optional[EmailStr] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=1, max_length=128)
    role: str = "user"


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(UserBase):
    id: int
    role: str
    user_type: str = "free"
    subscription_type: str = "free"
    remaining_calculations: int = -1
    has_security_question: bool = False
    trial_used: int = 0
    trial_started_at: int = 0
    trial_expires_at: int = 0
    trial_plan_at_start: str = ""

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1)
    russian_name: Optional[str] = None
    category: Optional[str] = None
    model: Optional[str] = None
    unit_price: DecimalField = Decimal("0")
    weight_g: int = 0
    length_cm: int = 0
    width_cm: int = 0
    height_cm: int = 0
    is_cylinder: bool = False
    cylinder_diameter: float = 0
    cylinder_length: float = 0
    has_battery: bool = False
    battery_capacity_wh: float = 0
    has_msds: bool = False
    has_liquid: bool = False
    labeling_fee: DecimalField = Decimal("0")
    shipping_fee: DecimalField = Decimal("0")
    battery_capacity_mah: int = 0
    battery_voltage: float = 0
    commission_rate: DecimalField = Field(default=Decimal("0"), ge=0, le=100)
    commission_category_id: Optional[int] = None
    target_profit_margin: DecimalField = Field(default=Decimal("0"), ge=0, le=100)
    promotion_cost_rate: DecimalField = Field(default=Decimal("0"), ge=0, le=100)
    withdrawal_fee_rate: DecimalField = Field(default=Decimal("0"), ge=0, le=100)
    payment_processing_fee: DecimalField = Field(default=Decimal("0"), ge=0, le=100)
    return_rate: DecimalField = Field(default=Decimal("0"), ge=0, le=100)
    vat_rate: DecimalField = Field(default=Decimal("0"), ge=0, le=100)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    russian_name: Optional[str] = None
    category: Optional[str] = None
    model: Optional[str] = None
    unit_price: Optional[DecimalField] = None
    weight_g: Optional[int] = None
    length_cm: Optional[int] = None
    width_cm: Optional[int] = None
    height_cm: Optional[int] = None
    is_cylinder: Optional[bool] = None
    cylinder_diameter: Optional[float] = None
    cylinder_length: Optional[float] = None
    has_battery: Optional[bool] = None
    battery_capacity_wh: Optional[float] = None
    has_msds: Optional[bool] = None
    has_liquid: Optional[bool] = None
    labeling_fee: Optional[DecimalField] = None
    shipping_fee: Optional[DecimalField] = None
    battery_capacity_mah: Optional[int] = None
    battery_voltage: Optional[float] = None
    commission_rate: Optional[DecimalField] = None
    commission_category_id: Optional[int] = None
    target_profit_margin: Optional[DecimalField] = None
    promotion_cost_rate: Optional[DecimalField] = None
    withdrawal_fee_rate: Optional[DecimalField] = None
    payment_processing_fee: Optional[DecimalField] = None
    return_rate: Optional[DecimalField] = None
    vat_rate: Optional[DecimalField] = None


class ProductResponse(ProductBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class LogisticsBase(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = "land"
    min_days: int = 1
    max_days: int = 30
    price_limit_cny: DecimalField = Decimal("0")
    price_min_cny: DecimalField = Decimal("0")
    base_fee: DecimalField = Decimal("0")
    min_weight: int = 0
    max_weight: int = 100000
    max_sum_of_sides: int = 0
    max_longest_side: int = 0
    max_second_side: int = 0
    max_third_side: int = 0
    min_second_side: int = 0
    min_length: int = 0
    max_cylinder_sum: int = 0
    min_cylinder_sum: int = 0
    max_cylinder_length: int = 0
    min_cylinder_length: int = 0
    volume_mode: str = "none"
    longest_side_threshold: int = 0
    sum_of_sides_threshold: int = 0
    allow_battery: bool = False
    allow_liquid: bool = False
    battery_capacity_limit_wh: float = 0
    require_msds: bool = False
    fee_mode: str = "base_weight"
    first_fee: DecimalField = Decimal("0")
    first_weight_g: int = 0
    continue_fee: DecimalField = Decimal("0")
    continue_unit: str = "g"
    volume_coefficient: float = 5000
    delivery_method: Optional[str] = None
    priority_group: str = "D"
    is_active: bool = True
    fulfillment_type: str = "rfbs"
    destination: str = "RU"
    fbp_service_level: Optional[str] = None
    fbp_company: Optional[str] = None
    is_smart: int = 0


class LogisticsCreate(LogisticsBase):
    pass


class LogisticsUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    min_days: Optional[int] = None
    max_days: Optional[int] = None
    price_limit_cny: Optional[DecimalField] = None
    price_min_cny: Optional[DecimalField] = None
    base_fee: Optional[DecimalField] = None
    min_weight: Optional[int] = None
    max_weight: Optional[int] = None
    max_sum_of_sides: Optional[int] = None
    max_longest_side: Optional[int] = None
    max_second_side: Optional[int] = None
    max_third_side: Optional[int] = None
    min_second_side: Optional[int] = None
    min_length: Optional[int] = None
    max_cylinder_sum: Optional[int] = None
    min_cylinder_sum: Optional[int] = None
    max_cylinder_length: Optional[int] = None
    min_cylinder_length: Optional[int] = None
    volume_mode: Optional[str] = None
    longest_side_threshold: Optional[int] = None
    sum_of_sides_threshold: Optional[int] = None
    allow_battery: Optional[bool] = None
    allow_liquid: Optional[bool] = None
    battery_capacity_limit_wh: Optional[float] = None
    require_msds: Optional[bool] = None
    fee_mode: Optional[str] = None
    first_fee: Optional[DecimalField] = None
    first_weight_g: Optional[int] = None
    continue_fee: Optional[DecimalField] = None
    continue_unit: Optional[str] = None
    volume_coefficient: Optional[float] = None
    delivery_method: Optional[str] = None
    priority_group: Optional[str] = None
    is_active: Optional[bool] = None
    fulfillment_type: Optional[str] = None
    destination: Optional[str] = None
    fbp_service_level: Optional[str] = None
    fbp_company: Optional[str] = None
    is_smart: Optional[int] = None


class LogisticsResponse(LogisticsBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class BreakdownItem(BaseModel):
    """价格构成分解项"""

    label: str
    value: DecimalField
    color: str


class PricingResultItem(BaseModel):
    """单个物流计算结果"""

    price_cny: DecimalField = Decimal("0")
    price_rub: DecimalField = Decimal("0")
    logistics_name: str = ""
    logistics_cost: DecimalField = Decimal("0")
    days_min: int = 0
    days_max: int = 0
    profit_cny: DecimalField = Decimal("0")
    profit_margin_pct: DecimalField = Decimal("0")
    priority_group: str = ""
    is_available: bool = False
    pricing_mode: str = ""
    avg_cost: DecimalField = Decimal("0")
    saved_cost: DecimalField = Decimal("0")
    avg_days: float = 0
    saved_days: float = 0
    is_smart: int = 0
    breakdown: List[BreakdownItem] = Field(default_factory=list)


class PricingComboResult(BaseModel):
    """陆运/空运组合结果"""

    land: PricingResultItem
    air: PricingResultItem


class PricingRequest(BaseModel):
    """定价计算请求"""

    product_id: Optional[int] = None
    product_data: Optional[dict] = None
    mode: str = "fast"


class PricingResponse(BaseModel):
    """定价计算完整响应"""

    calculation_mode: str
    price_priority: PricingComboResult
    speed_priority: PricingComboResult
    breakeven_price_priority: Optional[PricingComboResult] = None
    breakeven_speed_priority: Optional[PricingComboResult] = None
    exchange_rates: dict = Field(default_factory=dict)
    filtered_logistics: dict = Field(default_factory=dict)
    product: Optional[dict] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)
    security_question: str = Field(..., min_length=1, max_length=200)
    security_answer: str = Field(..., min_length=1, max_length=200)


class ChangePassword(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


class PasswordRecoveryStartRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)


class PasswordRecoveryStartResponse(BaseModel):
    message: str
    questions: List[str]


class PasswordRecoveryVerifyRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    answer: str = Field(..., min_length=1, max_length=200)


class PasswordRecoveryVerifyResponse(BaseModel):
    reset_token: str


class PasswordRecoveryResetRequest(BaseModel):
    reset_token: str = Field(..., min_length=1, max_length=512)
    new_password: str = Field(..., min_length=1, max_length=128)


class MessageResponse(BaseModel):
    message: str
    success: bool = True


class SetSecurityQuestionRequest(BaseModel):
    question: str
    answer: str


class CommissionCategoryCreate(BaseModel):
    name: str
    rfbs_tier1_rate: DecimalField
    rfbs_tier2_rate: DecimalField
    rfbs_tier3_rate: DecimalField


class CommissionCategoryUpdate(BaseModel):
    name: Optional[str] = None
    rfbs_tier1_rate: Optional[DecimalField] = None
    rfbs_tier2_rate: Optional[DecimalField] = None
    rfbs_tier3_rate: Optional[DecimalField] = None
    is_active: Optional[int] = None


class CommissionCategoryResponse(BaseModel):
    id: int
    name: str
    rfbs_tier1_rate: DecimalField
    rfbs_tier2_rate: DecimalField
    rfbs_tier3_rate: DecimalField
    fbp_tier1_rate: DecimalField
    fbp_tier2_rate: DecimalField
    fbp_tier3_rate: DecimalField
    is_active: int = 1

    model_config = ConfigDict(from_attributes=True)


class LogisticsPoolItem(BaseModel):
    id: int
    name: Optional[str] = None
    type: Optional[str] = None
    min_days: Optional[int] = None
    max_days: Optional[int] = None
    price_limit_cny: Optional[DecimalField] = Decimal("0")
    price_min_cny: Optional[DecimalField] = Decimal("0")
    base_fee: Optional[DecimalField] = Decimal("0")
    min_weight: Optional[int] = None
    max_weight: Optional[int] = None
    max_sum_of_sides: Optional[int] = None
    max_longest_side: Optional[int] = None
    max_second_side: Optional[int] = 0
    max_third_side: Optional[int] = 0
    min_second_side: Optional[int] = 0
    min_length: Optional[int] = 0
    max_cylinder_sum: Optional[int] = 0
    min_cylinder_sum: Optional[int] = 0
    max_cylinder_length: Optional[int] = 0
    min_cylinder_length: Optional[int] = 0
    volume_mode: Optional[str] = "none"
    longest_side_threshold: Optional[int] = 0
    sum_of_sides_threshold: Optional[int] = 0
    allow_battery: Optional[bool] = False
    allow_liquid: Optional[bool] = False
    battery_capacity_limit_wh: Optional[float] = 0
    require_msds: Optional[bool] = False
    fee_mode: Optional[str] = "base_weight"
    first_fee: Optional[DecimalField] = Decimal("0")
    first_weight_g: Optional[int] = 0
    continue_fee: Optional[DecimalField] = Decimal("0")
    continue_unit: Optional[str] = "g"
    volume_coefficient: Optional[float] = 5000
    delivery_method: Optional[str] = "pickup"
    priority_group: Optional[str] = "D"
    fulfillment_type: str = "rfbs"
    destination: str = "RU"
    fbp_service_level: Optional[str] = None
    fbp_company: Optional[str] = None
    is_smart: int = 0
    source_file: Optional[str] = None
    imported_at: Optional[int] = None
    is_active: int = 1

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class ProductImportPreview(BaseModel):
    columns: List[str]
    preview_rows: List[dict]


class ProductImportItem(BaseModel):
    """单条产品导入校验项。"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    russian_name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    unit_price: Optional[DecimalField] = Field(None, ge=Decimal("0"))
    weight_g: Optional[int] = Field(None, ge=0, le=1_000_000)
    length_cm: Optional[int] = Field(None, ge=0, le=10_000)
    width_cm: Optional[int] = Field(None, ge=0, le=10_000)
    height_cm: Optional[int] = Field(None, ge=0, le=10_000)
    is_cylinder: Optional[bool] = None
    cylinder_diameter: Optional[float] = Field(None, ge=0)
    cylinder_length: Optional[float] = Field(None, ge=0)
    has_battery: Optional[bool] = None
    battery_capacity_wh: Optional[float] = Field(None, ge=0)
    has_msds: Optional[bool] = None
    has_liquid: Optional[bool] = None
    labeling_fee: Optional[DecimalField] = Field(None, ge=Decimal("0"))
    shipping_fee: Optional[DecimalField] = Field(None, ge=Decimal("0"))
    battery_capacity_mah: Optional[int] = Field(None, ge=0)
    battery_voltage: Optional[float] = Field(None, ge=0)
    commission_rate: Optional[DecimalField] = Field(None, ge=Decimal("0"), le=100)
    commission_category_id: Optional[int] = Field(None, ge=1)
    target_profit_margin: Optional[DecimalField] = Field(None, ge=Decimal("0"), le=100)
    promotion_cost_rate: Optional[DecimalField] = Field(None, ge=Decimal("0"), le=100)
    withdrawal_fee_rate: Optional[DecimalField] = Field(None, ge=Decimal("0"), le=100)
    payment_processing_fee: Optional[DecimalField] = Field(None, ge=Decimal("0"), le=100)
    return_rate: Optional[DecimalField] = Field(None, ge=Decimal("0"), le=100)
    vat_rate: Optional[DecimalField] = Field(None, ge=Decimal("0"), le=100)

    # 允许 Excel 解析后产生的额外列（用户在 column_mapping 之外的列），
    # 但这些字段不会进入 ORM。
    model_config = ConfigDict(extra="allow")


class ProductImportConfirm(BaseModel):
    column_mapping: dict
    rows: List[dict]
    conflict_action: str = "skip"


class PricingGroupResult(BaseModel):
    land: PricingResultItem = Field(default_factory=PricingResultItem)
    air: PricingResultItem = Field(default_factory=PricingResultItem)


class PricingDualPriorityGroupResult(BaseModel):
    price_priority: PricingGroupResult = Field(default_factory=PricingGroupResult)
    speed_priority: PricingGroupResult = Field(default_factory=PricingGroupResult)
    filtered_logistics: dict = Field(default_factory=dict)


class PricingGroupedResponse(BaseModel):
    calculation_mode: str
    rfbs_AM: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    rfbs_ru: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    rfbs_KZ: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    rfbs_BY: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    rfbs_KGZ: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    rfbs_UZ: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    rfbs_GE: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    rfbs_AZ: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    fbp_ru: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    fbp_cis: PricingDualPriorityGroupResult = Field(default_factory=PricingDualPriorityGroupResult)
    breakeven_rfbs_AM: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_ru: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_KZ: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_BY: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_KGZ: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_UZ: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_GE: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_AZ: Optional[PricingDualPriorityGroupResult] = None
    breakeven_fbp_ru: Optional[PricingDualPriorityGroupResult] = None
    breakeven_fbp_cis: Optional[PricingDualPriorityGroupResult] = None
    exchange_rates: dict = Field(default_factory=dict)
    filtered_logistics: dict = Field(default_factory=dict)
    product: Optional[dict] = None
