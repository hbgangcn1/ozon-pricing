from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List


class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    email: Optional[EmailStr] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    role: str = "user"


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    role: str
    user_type: str = "free"
    subscription_type: str = "free"
    remaining_calculations: int = -1

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1)
    russian_name: Optional[str] = None
    category: Optional[str] = None
    model: Optional[str] = None
    unit_price: float = 0
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
    labeling_fee: float = 0
    shipping_fee: float = 0
    battery_capacity_mah: int = 0
    battery_voltage: float = 0
    commission_rate: float = Field(default=0, ge=0, le=100)
    commission_category_id: Optional[int] = None
    target_profit_margin: float = Field(default=0, ge=0, le=100)
    promotion_cost_rate: float = Field(default=0, ge=0, le=100)
    withdrawal_fee_rate: float = Field(default=0, ge=0, le=100)
    payment_processing_fee: float = Field(default=0, ge=0, le=100)
    return_rate: float = Field(default=0, ge=0, le=100)
    vat_rate: float = Field(default=0, ge=0, le=100)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    russian_name: Optional[str] = None
    category: Optional[str] = None
    model: Optional[str] = None
    unit_price: Optional[float] = None
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
    labeling_fee: Optional[float] = None
    shipping_fee: Optional[float] = None
    battery_capacity_mah: Optional[int] = None
    battery_voltage: Optional[float] = None
    commission_rate: Optional[float] = None
    commission_category_id: Optional[int] = None
    target_profit_margin: Optional[float] = None
    promotion_cost_rate: Optional[float] = None
    withdrawal_fee_rate: Optional[float] = None
    payment_processing_fee: Optional[float] = None
    return_rate: Optional[float] = None
    vat_rate: Optional[float] = None


class ProductResponse(ProductBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class LogisticsBase(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = "land"
    min_days: int = 1
    max_days: int = 30
    price_limit_cny: float = 0
    price_min_cny: float = 0
    base_fee: float = 0
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
    first_fee: float = 0
    first_weight_g: int = 0
    continue_fee: float = 0
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
    price_limit_cny: Optional[float] = None
    price_min_cny: Optional[float] = None
    base_fee: Optional[float] = None
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
    first_fee: Optional[float] = None
    first_weight_g: Optional[int] = None
    continue_fee: Optional[float] = None
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
    value: float
    color: str


class PricingResultItem(BaseModel):
    """单个物流计算结果"""

    price_cny: float = 0
    price_rub: float = 0
    logistics_name: str = ""
    logistics_cost: float = 0
    days_min: int = 0
    days_max: int = 0
    profit_cny: float = 0
    profit_margin_pct: float = 0
    priority_group: str = ""
    is_available: bool = False
    pricing_mode: str = ""
    avg_cost: float = 0
    saved_cost: float = 0
    avg_days: float = 0
    saved_days: float = 0
    is_smart: int = 0
    breakdown: List[BreakdownItem] = []


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
    exchange_rates: dict
    filtered_logistics: dict = {}
    product: Optional[dict] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    security_question: str
    security_answer: str


class ChangePassword(BaseModel):
    current_password: str
    new_password: str


class MessageResponse(BaseModel):
    message: str
    success: bool = True


class CommissionCategoryCreate(BaseModel):
    name: str
    rfbs_tier1_rate: float
    rfbs_tier2_rate: float
    rfbs_tier3_rate: float


class CommissionCategoryUpdate(BaseModel):
    name: Optional[str] = None
    rfbs_tier1_rate: Optional[float] = None
    rfbs_tier2_rate: Optional[float] = None
    rfbs_tier3_rate: Optional[float] = None
    is_active: Optional[int] = None


class CommissionCategoryResponse(BaseModel):
    id: int
    name: str
    rfbs_tier1_rate: float
    rfbs_tier2_rate: float
    rfbs_tier3_rate: float
    fbp_tier1_rate: float
    fbp_tier2_rate: float
    fbp_tier3_rate: float
    is_active: int = 1

    model_config = ConfigDict(from_attributes=True)


class LogisticsPoolItem(BaseModel):
    id: int
    name: Optional[str] = None
    type: Optional[str] = None
    min_days: Optional[int] = None
    max_days: Optional[int] = None
    price_limit_cny: Optional[float] = 0
    price_min_cny: Optional[float] = 0
    base_fee: Optional[float] = 0
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
    first_fee: Optional[float] = 0
    first_weight_g: Optional[int] = 0
    continue_fee: Optional[float] = 0
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


class ProductImportConfirm(BaseModel):
    column_mapping: dict
    rows: List[dict]
    conflict_action: str = "skip"


class PricingGroupResult(BaseModel):
    land: PricingResultItem = PricingResultItem()
    air: PricingResultItem = PricingResultItem()


class PricingDualPriorityGroupResult(BaseModel):
    price_priority: PricingGroupResult = PricingGroupResult()
    speed_priority: PricingGroupResult = PricingGroupResult()
    filtered_logistics: dict = {}


class PricingGroupedResponse(BaseModel):
    calculation_mode: str
    rfbs_ru: PricingDualPriorityGroupResult = PricingDualPriorityGroupResult()
    rfbs_KZ: PricingDualPriorityGroupResult = PricingDualPriorityGroupResult()
    rfbs_BY: PricingDualPriorityGroupResult = PricingDualPriorityGroupResult()
    rfbs_KGZ: PricingDualPriorityGroupResult = PricingDualPriorityGroupResult()
    rfbs_UZ: PricingDualPriorityGroupResult = PricingDualPriorityGroupResult()
    rfbs_GE: PricingDualPriorityGroupResult = PricingDualPriorityGroupResult()
    rfbs_AZ: PricingDualPriorityGroupResult = PricingDualPriorityGroupResult()
    fbp_ru: PricingDualPriorityGroupResult = PricingDualPriorityGroupResult()
    fbp_cis: PricingDualPriorityGroupResult = PricingDualPriorityGroupResult()
    breakeven_rfbs_ru: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_KZ: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_BY: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_KGZ: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_UZ: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_GE: Optional[PricingDualPriorityGroupResult] = None
    breakeven_rfbs_AZ: Optional[PricingDualPriorityGroupResult] = None
    breakeven_fbp_ru: Optional[PricingDualPriorityGroupResult] = None
    breakeven_fbp_cis: Optional[PricingDualPriorityGroupResult] = None
    exchange_rates: dict = {}
    filtered_logistics: dict = {}
    product: Optional[dict] = None
