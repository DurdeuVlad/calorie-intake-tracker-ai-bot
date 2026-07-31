package io.github.foodjournal.application;

/** Optional local-only observer. It intentionally receives no provider request or response payloads. */
public interface AgentTraceSink {
  default void started(AgentContext context) {}
  default void modelReply(JournalAgentModel.AgentReply reply) {}
  default void toolResult(JournalAgentModel.ToolCall call, AgentToolResult result) {}
  default void completed(String reply) {}
  static AgentTraceSink noop() { return new AgentTraceSink() {}; }
}
