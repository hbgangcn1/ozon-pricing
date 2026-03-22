from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


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
    remaining_calculations: int = -1

    class Config:
        from_attributes = True


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
    has_flammable: bool = False


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
    has_flammable: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


class LogisticsBase(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = "standard"
    min_days: int = 1
    max_days: int = 30
    price_limit: float = 0
    base_fee: float = 0
    weight_factor: float = 0
    min_weight: int = 0
    max_weight: int = 100000
    max_sum_of_sides: int = 0
    max_longest_side: int = 0
    volume_mode: str = "none"


class LogisticsCreate(LogisticsBase):
    pass


class LogisticsUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    min_days: Optional[int] = None
    max_days: Optional[int] = None
    price_limit: Optional[float] = None
    base_fee: Optional[float] = None
    weight_factor: Optional[float] = None
    min_weight: Optional[int] = None
    max_weight: Optional[int] = None
    max_sum_of_sides: Optional[int] = None
    max_longest_side: Optional[int] = None
    volume_mode: Optional[str] = None


class LogisticsResponse(LogisticsBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True


class PricingRequest(BaseModel):
    product_id: int
    logistics_id: int
    mode: str = "fast"


class PricingResponse(BaseModel):
    final_price: float
    currency: str = "RUB"
    logistics_cost: float
    storage_cost: float
    packaging_cost: float
    other_costs: float
    exchange_rate: float
    calculation_mode: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
    success: bool = True
