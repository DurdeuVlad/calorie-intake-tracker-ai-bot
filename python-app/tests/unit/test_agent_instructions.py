from app.agent.capabilities import registry as capabilities_registry
from app.agent.openai_model_client import _user_content
from app.agent.system_prompt import instructions
from app.agent.tool_schemas import all_tool_names, tool_categories, tool_definitions
from app.domain.agent_types import AgentContext


def test_core_prompt_is_small_and_contains_capability_index():
    prompt = instructions()
    # Core prompt should be small (was a 5000+ char monolith)
    assert len(prompt) < 12000
    assert "Capability index" in prompt
    assert "load_instructions" in prompt
    for topic in ("nutrition", "portions", "combos", "editing", "daily_totals", "onboarding", "aliases"):
        assert topic in prompt

    assert "a user-owned private-food result, and a photo's Label line" in prompt
    assert "as trusted nutrition" in prompt
    assert "always try to ground the value with search_web" in prompt
    assert "search_web checks a fresh cache first" in prompt
    assert "Only use estimate_food after search_web/fetch_web_page are unavailable or yield no usable nutrition" in prompt
    assert "Do not use 1 kcal as a fallback" in prompt
    assert "gin tonic is not water" in prompt
    assert '"do 150 kcal" means EDIT it with calories 150' in prompt

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


def test_media_context_is_not_duplicated_in_model_user_content():
    voice = AgentContext(
        user=None,
        chat_id="1",
        message="transcript\nUser caption: oatmeal",
        media_kind="voice",
        media_text="transcript",
        media_caption="oatmeal",
    )
    photo = AgentContext(
        user=None,
        chat_id="1",
        message="photo interpretation\nUser caption: lunch",
        media_kind="photo",
        media_text="photo interpretation",
    )

    voice_content = _user_content(voice)
    photo_content = _user_content(photo)

    assert voice_content.count("[Server transcript:") == 1
    assert voice_content.count("oatmeal") == 1
    assert "[Server transcript: transcript]" in voice_content
    assert photo_content.count("[Photo interpretation:") == 1
    assert "[Photo interpretation: photo interpretation]" in photo_content


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


def test_feedback_instructions_cover_unprompted_capture_frustration_and_privacy_questions():
    prompt = instructions(romanian=False)

    assert "call save_feedback with their own words before replying" in prompt
    assert "call get_recent_feedback and read it back; never call save_feedback again just to answer that question" in prompt
    assert "correcting a meal you logged wrong is an EDIT/DELETE, not feedback" in prompt
    assert "offer once to note it as feedback even though they did not ask" in prompt
    assert "do not offer again in the same conversation" in prompt
    assert "ask one short clarifying question" in prompt
    assert "submit whatever they already gave you rather than asking again" in prompt
    assert "answer directly from here rather than deflecting to /privacy" in prompt
    assert "original media files are not retained" in prompt

    save_feedback = next(tool for tool in tool_definitions() if tool["function"]["name"] == "save_feedback")
    assert "not a food log" in save_feedback["function"]["description"]
    assert save_feedback["function"]["parameters"]["required"] == ["message"]

    get_recent_feedback = next(tool for tool in tool_definitions() if tool["function"]["name"] == "get_recent_feedback")
    assert "never call save_feedback again" in get_recent_feedback["function"]["description"]


def test_a_why_question_about_an_estimate_is_answered_not_logged_as_feedback():
    """Live production regression (user_feedback rows 1-2): the user asked "why
    is this 710 kcal" about a KFC estimate and "why so many calories" about a
    total -- both genuine questions about a number the agent already produced,
    not complaints -- and the agent silently filed them as feedback instead of
    answering. The user flagged this themselves, unprompted, in row 3."""
    prompt = instructions(romanian=False)

    assert '"why is this 710 kcal", "why so many calories"' in prompt
    assert "is a request to see your own reasoning, not a complaint" in prompt
    assert "answer it directly from the entry's basis or derivation" in prompt
    assert "for a daily total, by naming the entries that make it up" in prompt
    assert "only call save_feedback if they push back after that explanation or are clearly complaining rather than asking" in prompt


def test_onboarding_instructions_explain_capabilities_and_drive_settings_to_completion():
    """Onboarding is driven by the agent, not deterministic if-else stage
    branches -- update_settings is the only path that advances onboarding
    stages, so the prompt must tell the model to complete it through
    conversation, not just set a timezone and move on."""
    prompt = instructions(romanian=False)

    assert "When the user sends /start and onboarding is not complete" in prompt
    assert "meals can be logged from text, a voice note, or a photo" in prompt
    assert "ask once for a daily calorie target between 1200 and 5000, or invite them to say skip" in prompt
    assert "call update_settings with calorieTarget or skipCalorieTarget true" in prompt
    assert "Do not ask about any of these again in later conversations" in prompt

    update_settings = next(tool for tool in tool_definitions() if tool["function"]["name"] == "update_settings")
    assert "skipCalorieTarget" in update_settings["function"]["parameters"]["properties"]
    assert "completes onboarding" in update_settings["function"]["description"]


def test_day_boundary_instructions_explain_the_setting_and_its_reminder():
    prompt = instructions(romanian=False)

    assert "Every user's tracking day starts at midnight by default, but that boundary is configurable" in prompt
    assert "update_settings dayBoundaryHour (0-23; 0 is midnight)" in prompt
    assert "This changes which tracking day a meal counts toward, not the meal's own logged time" in prompt
    assert "update_settings dayBoundaryReminderEnabled true; off is the default" in prompt

    update_settings = next(tool for tool in tool_definitions() if tool["function"]["name"] == "update_settings")
    properties = update_settings["function"]["parameters"]["properties"]
    assert "dayBoundaryHour" in properties
    assert "dayBoundaryReminderEnabled" in properties
    assert "tracking day starts at" in update_settings["function"]["description"]


def test_target_mode_instructions_cover_min_mode_framing_and_notification_toggles():
    prompt = instructions(romanian=False)

    assert "get_today_summary's targetMode tells you how to frame it" in prompt
    assert "in min mode it is a floor, so frame the same gap as how much more they still need to reach it, never as \"remaining\"" in prompt

    update_settings = next(tool for tool in tool_definitions() if tool["function"]["name"] == "update_settings")
    description = update_settings["function"]["description"]
    properties = update_settings["function"]["parameters"]["properties"]
    assert "targetMode is max (calorieTarget is a ceiling, default) or min" in description
    assert "budgetAlertsEnabled turns on an alert" in description
    assert "trackingNudgeEnabled turns on a reminder" in description
    assert properties["targetMode"]["enum"] == ["max", "min"]
    assert "budgetAlertsEnabled" in properties
    assert "trackingNudgeEnabled" in properties


def test_a_failed_correction_search_retries_broadly_before_giving_up():
    """Live production regression: the user asked to delete a duplicate
    "dulceață de ardei iute" entry; search_entries found nothing (a diacritics
    mismatch -- see the food_entry_repo fix), and the agent told the user
    outright that no matching entry existed even though two identical rows
    were sitting in the database for that exact day. The prompt must tell the
    model to retry broadly and match itself before declaring absence."""
    prompt = instructions(romanian=False)

    assert 'If search_entries returns nothing, retry once with the same date but no query' in prompt
    assert "is not the same as the entry being absent" in prompt
    assert "only tell the user nothing matches after that retry still finds nothing" in prompt


def test_feedback_logging_is_not_a_substitute_for_a_still_unresolved_correction():
    """Live production regression (user_feedback rows 6-11): after the failed
    search above, the user pushed back three times and the agent replied only
    "Am notat feedback-ul tău" each time -- never retrying the delete, never
    asking a clarifying question -- until the user got furious. Feedback
    logging must be additive to still attempting the request, never a
    stand-in for it."""
    prompt = instructions(romanian=False)

    assert "Logging feedback never substitutes for a still-unresolved request" in prompt
    assert "retry it -- a broader search_entries call, or one clarifying question -- in the same reply as noting the feedback, not instead of it" in prompt
    assert '"I\'ve noted your feedback" alone is not an acceptable reply to someone waiting on a correction' in prompt


def test_photo_label_line_is_trusted_like_an_explicit_value():
    """Live production gap: a photo whose vision output said "nutrition facts
    are visible" still only produced a rough visual guess, and the user had to
    retype the actual printed number by hand. The agent needs to know a real
    Label line is as trustworthy as a number the user typed directly -- not
    something to re-estimate from the photo's own Interpretation/Estimate, and
    not something to ask the user to retype."""
    prompt = instructions(romanian=False)

    assert "a photo's Label line (when it states a real printed value, not \"none\") as trusted nutrition" in prompt
    assert "without re-estimating from the photo's Interpretation/Estimate" in prompt
    assert "without asking the user to retype a number already printed and captured in Label" in prompt
