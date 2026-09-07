"""No-op context passthrough.

The v2.0 agent previously rewrote the user's message before sending it to the
model — replacing "mulțumesc" with "Estimate this meal now: ..." or prepending
"[Server note: estimate and log ...]". That was wrong: it put words in the
user's mouth and made the model act on instructions the user never sent.

The model is smart. It sees the real conversation history and the real
current message. The system prompt and capability docs guide its behavior.
Application code must not fabricate or alter user input.
"""

from app.db.models.conversation import ConversationMemory
from app.domain.agent_types import AgentContext


def estimate_followup_context(context: AgentContext, recent: list[ConversationMemory]) -> AgentContext:
    """Return the context unchanged. The model sees exactly what the user sent."""
    return context
