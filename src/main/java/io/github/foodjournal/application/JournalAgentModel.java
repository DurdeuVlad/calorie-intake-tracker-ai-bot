package io.github.foodjournal.application;

import java.util.List;

public interface JournalAgentModel {
  AgentReply next(AgentContext context, List<AgentExchange> exchanges);
  record AgentReply(String text, List<ToolCall> toolCalls) {}
  record ToolCall(String id, String name, String arguments) {}
  record AgentExchange(ToolCall call, AgentToolResult result) {}
}
