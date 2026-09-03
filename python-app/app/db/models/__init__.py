"""Import every model module here so app.db.base.Base.metadata is fully populated
(needed by Alembic autogenerate and by any code that touches Base.metadata directly)."""

from app.db.models.conversation import ConversationMemory
from app.db.models.entries import FoodEntry, FoodItem
from app.db.models.feedback import UserFeedback
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
from app.db.models.nutrition import (
    NutritionEvidence,
    NutritionSourceCache,
    OpenFoodFactsLookupCache,
    PendingNutritionQuote,
    PrivateFood,
)
from app.db.models.reports import ReportDelivery
from app.db.models.users import FoodUser, UserSettings

__all__ = [
    "ConversationMemory",
    "FoodEntry",
    "FoodItem",
    "FoodUser",
    "FrontendLinkCode",
    "JournalChangeMutation",
    "JournalChangeSet",
    "MessagingDailyStatus",
    "MessagingIdentity",
    "MessagingInboxMessage",
    "MessagingOutboundMessage",
    "MessagingRoute",
    "NutritionEvidence",
    "NutritionSourceCache",
    "OpenFoodFactsLookupCache",
    "PendingNutritionQuote",
    "PinnedDailyStatus",
    "PrivateFood",
    "ReportDelivery",
    "TelegramAccessGrant",
    "UserFeedback",
    "UserSettings",
]
