"""Import every model module here so app.db.base.Base.metadata is fully populated
(needed by Alembic autogenerate and by any code that touches Base.metadata directly)."""

from app.db.models.conversation import ConversationMemory
from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.journal_changes import JournalChangeMutation, JournalChangeSet
from app.db.models.messaging import (
    FrontendLinkCode,
    MessagingDailyStatus,
    MessagingIdentity,
    MessagingInboxMessage,
    MessagingOutboundMessage,
    MessagingRoute,
    PinnedDailyStatus,
    TelegramAccessGrant,
)
from app.db.models.nutrition import OpenFoodFactsLookupCache, NutritionEvidence, NutritionSourceCache, PendingNutritionQuote, PrivateFood
from app.db.models.reports import ReportDelivery
from app.db.models.users import FoodUser, UserSettings

__all__ = [
    "ConversationMemory",
    "FoodEntry",
    "FoodItem",
    "JournalChangeMutation",
    "JournalChangeSet",
    "FrontendLinkCode",
    "MessagingDailyStatus",
    "MessagingIdentity",
    "MessagingInboxMessage",
    "MessagingOutboundMessage",
    "MessagingRoute",
    "PinnedDailyStatus",
    "TelegramAccessGrant",
    "NutritionSourceCache",
    "NutritionEvidence",
    "OpenFoodFactsLookupCache",
    "PendingNutritionQuote",
    "PrivateFood",
    "ReportDelivery",
    "FoodUser",
    "UserSettings",
]
