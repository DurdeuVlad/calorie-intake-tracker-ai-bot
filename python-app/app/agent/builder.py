"""Shared construction of a fully-wired JournalApplicationService, used by
both the production entrypoint (run.py) and the terminal/eval harness so
they exercise the exact same agent wiring, differing only in the trace sink."""

from app.agent.journal_agent import JournalAgent
from app.agent.openai_model_client import OpenAiJournalAgentModel
from app.agent.trace_sink import AgentTraceSink
from app.config import Settings
from app.integrations.browserless import BrowserlessClient
from app.integrations.openfoodfacts import OpenFoodFactsHttpClient
from app.integrations.searxng import SearxngClient
from app.scheduling import report_scheduler
from app.services import daily_status_service
from app.services.conversation_memory_service import recent as memory_recent
from app.services.journal_application_service import JournalApplicationService
from app.services.journal_tool_executor import JournalToolExecutor


def build_journal_application_service(settings: Settings, trace: AgentTraceSink | None = None) -> JournalApplicationService:
    model = OpenAiJournalAgentModel(settings)
    off = OpenFoodFactsHttpClient(settings)
    searxng = SearxngClient(settings.searxng_base_url)
    browserless = BrowserlessClient(settings.browserless_base_url, settings.browserless_token)
    tools = JournalToolExecutor(
        off=off,
        searxng=searxng,
        browserless=browserless,
        refresh_daily_status=daily_status_service.refresh_for_tool_executor,
        send_budget_alert=report_scheduler.maybe_send_budget_alert_for_tool_executor,
    )
    agent = JournalAgent(model, tools, settings.agent_max_tool_calls, memory_recent=memory_recent, trace=trace)
    return JournalApplicationService(settings.default_timezone, agent=agent)
