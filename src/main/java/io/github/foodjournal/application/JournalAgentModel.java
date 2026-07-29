package io.github.foodjournal.application;

import java.util.List;
import io.github.foodjournal.domain.ConversationMemory;

public interface JournalAgentModel {
  AgentReply next(AgentContext context, List<ConversationMemory> memory, List<AgentExchange> exchanges);
  record AgentReply(String text, List<ToolCall> toolCalls) {}
  record ToolCall(String id, String name, String arguments) {}
  record AgentExchange(ToolCall call, AgentToolResult result) {}
}
