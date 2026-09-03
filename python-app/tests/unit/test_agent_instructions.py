from app.agent.system_prompt import instructions
from app.agent.tool_schemas import tool_definitions


def test_gin_tonic_is_estimated_and_edit_calories_replace_the_total():
    prompt = instructions(romanian=False)

    assert "user-owned private-food result as trusted nutrition" in prompt
    assert "always try to ground the value with search_web" in prompt
    assert "search_web checks a fresh cache first" in prompt
    assert "Only use estimate_food after search_web/fetch_web_page are unavailable or yield no usable nutrition" in prompt
    assert "Do not use 1 kcal as a fallback" in prompt
    assert "gin tonic is not water" in prompt
    assert '"do 150 kcal" means EDIT it with calories 150' in prompt

    apply_actions = next(tool for tool in tool_definitions() if tool["function"]["name"] == "apply_journal_actions")
    assert "replacement total, never an increment or delta" in apply_actions["function"]["description"]
    search_web = next(tool for tool in tool_definitions() if tool["function"]["name"] == "search_web")
    assert "trusted local, private-food, or exact packaged result" in search_web["function"]["description"]
    assert "Checks a fresh cache before an outbound query" in search_web["function"]["description"]


def test_feedback_instructions_cover_unprompted_capture_frustration_and_privacy_questions():
    prompt = instructions(romanian=False)

    assert "call submit_feedback with their own words before replying" in prompt
    assert "call get_recent_feedback and read it back; never call submit_feedback again just to answer that question" in prompt
    assert "correcting a meal you logged wrong is an EDIT/DELETE, not feedback" in prompt
    assert "offer once to note it as feedback even though they did not ask" in prompt
    assert "do not offer again in the same conversation" in prompt
    assert "ask one short clarifying question" in prompt
    assert "submit whatever they already gave you rather than asking again" in prompt
    assert "answer directly from here rather than deflecting to /privacy" in prompt
    assert "original media files are not retained" in prompt

    submit_feedback = next(tool for tool in tool_definitions() if tool["function"]["name"] == "submit_feedback")
    assert "not a food log" in submit_feedback["function"]["description"]
    assert submit_feedback["function"]["parameters"]["required"] == ["message"]

    get_recent_feedback = next(tool for tool in tool_definitions() if tool["function"]["name"] == "get_recent_feedback")
    assert "never call submit_feedback again" in get_recent_feedback["function"]["description"]


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
    assert "only call submit_feedback if they push back after that explanation or are clearly complaining rather than asking" in prompt


def test_onboarding_instructions_explain_capabilities_and_drive_settings_to_completion():
    """continue_onboarding() never runs in production (see
    journal_application_service.py's module docstring) -- update_settings is the
    only path that reaches real onboarding users, so the prompt must tell the
    model to complete it, not just set a timezone and move on."""
    prompt = instructions(romanian=False)

    assert "The first user reply after your /start welcome message is their timezone" in prompt
    assert "briefly explain what you do" in prompt
    assert "logged from text, a voice note, or a photo" in prompt
    assert "ask once for a daily calorie target between 1200 and 5000, or invite them to say skip" in prompt
    assert "call update_settings again with calorieTarget or skipCalorieTarget true" in prompt
    assert "do not ask about the target again in this or any later conversation" in prompt

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
