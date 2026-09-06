from app.agent.capabilities import registry as capabilities_registry
from app.agent.system_prompt import instructions
from app.agent.tool_schemas import all_tool_names, tool_categories, tool_definitions


def test_core_prompt_is_small_and_contains_capability_index():
    prompt = instructions()
    # Core prompt should be small (was a 5000+ char monolith)
    assert len(prompt) < 3500
    assert "Capability index" in prompt
    assert "load_instructions" in prompt
    for topic in ("nutrition", "portions", "combos", "editing", "daily_totals", "onboarding", "aliases"):
        assert topic in prompt


def test_load_instructions_tool_is_registered():
    tools = tool_definitions()
    tool = next((t for t in tools if t["function"]["name"] == "load_instructions"), None)
    assert tool is not None
    params = tool["function"]["parameters"]
    assert "topic" in params["properties"]
    assert "topic" in params["required"]
    enum_values = params["properties"]["topic"]["enum"]
    for topic in ("nutrition", "portions", "combos", "editing", "daily_totals", "onboarding", "aliases"):
        assert topic in enum_values


def test_capability_docs_exist_and_are_readable():
    for topic in capabilities_registry.valid_topics():
        content = capabilities_registry.load(topic)
        assert content is not None
        assert len(content) > 50  # not empty


def test_load_unknown_topic_returns_none():
    assert capabilities_registry.load("nonexistent") is None


def test_apply_actions_description_preserves_edit_is_absolute_rule():
    apply_actions = next(tool for tool in tool_definitions() if tool["function"]["name"] == "apply_journal_actions")
    assert "replacement total, never an increment or delta" in apply_actions["function"]["description"]


def test_search_web_description_preserves_trusted_source_rule():
    search_web = next(tool for tool in tool_definitions() if tool["function"]["name"] == "search_web")
    assert "trusted local, private-food, or exact packaged result" in search_web["function"]["description"]
    assert "Checks a fresh cache before an outbound query" in search_web["function"]["description"]


def test_tool_categories_cover_all_tools():
    """Every tool in tool_definitions() must appear in exactly one category."""
    defined_names = {t["function"]["name"] for t in tool_definitions()}
    categorized_names = set(all_tool_names())
    assert defined_names == categorized_names, (
        f"Tools without category: {defined_names - categorized_names}, "
        f"Categories without tool: {categorized_names - defined_names}"
    )


def test_tool_categories_are_organized():
    categories = tool_categories()
    assert "always_available" in categories
    assert "nutrition" in categories
    assert "settings" in categories
    assert "planning" in categories
    # Always-available tools include the core journal and disclosure tools
    for tool in ("apply_journal_actions", "undo_last_change", "load_instructions", "get_today_summary", "search_entries"):
        assert tool in categories["always_available"]
    # Nutrition tools include search and estimate
    for tool in ("search_web", "fetch_web_page", "estimate_food", "search_packaged_food"):
        assert tool in categories["nutrition"]
