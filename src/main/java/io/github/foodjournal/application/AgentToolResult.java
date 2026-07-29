package io.github.foodjournal.application;

import java.util.Map;

/** Canonical, non-sensitive result passed back to the model after every tool invocation. */
public record AgentToolResult(boolean ok, String code, Map<String, Object> data, String userHint) {
  public static AgentToolResult ok(Map<String, Object> data) { return new AgentToolResult(true, "OK", data, null); }
  public static AgentToolResult failure(String code, String hint) { return new AgentToolResult(false, code, Map.of(), hint); }
}
