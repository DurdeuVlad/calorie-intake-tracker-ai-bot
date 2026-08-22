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
