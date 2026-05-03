"""Pydantic models for payment and subscription APIs."""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class SubscriptionTier(str, Enum):
    """Available subscription tiers."""
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class Subscription(BaseModel):
    """Subscription record stored in DB."""
    id: str
    user_id: str
    tier: SubscriptionTier
    status: str = Field(default="pending", description="pending | active | cancelled | expired")
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    payment_provider: Optional[str] = None
    provider_subscription_id: Optional[str] = None
    auto_renew: bool = True


class PaymentTransaction(BaseModel):
    """Payment transaction record."""
    id: str
    subscription_id: Optional[str] = None
    user_id: str
    amount: float = Field(ge=0)
    currency: str = "RUB"
    status: str = Field(default="pending", description="pending | success | failed | refunded")
    provider: str = "prodamus"
    provider_payment_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class ProdamusWebhookPayload(BaseModel):
    """Prodamus payment webhook payload."""
    order_id: Optional[str] = Field(default=None, alias="order_num")
    payment_status: str = Field(default="", alias="payment_status")
    amount: float = Field(default=0.0)
    currency: str = Field(default="RUB")
    email: Optional[str] = None
    phone: Optional[str] = Field(default=None, alias="customer_phone")
    sign: Optional[str] = None
    date: Optional[str] = None
    subscription_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CreateSubscriptionRequest(BaseModel):
    """Request to create a new subscription."""
    user_id: str
    tier: SubscriptionTier
    payment_method: Optional[str] = None
    return_url: Optional[str] = None
    auto_renew: bool = True


class SubscriptionResponse(BaseModel):
    """Response with subscription details."""
    id: str
    user_id: str
    tier: SubscriptionTier
    status: str
    started_at: Optional[datetime]
    expires_at: Optional[datetime]
    payment_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
