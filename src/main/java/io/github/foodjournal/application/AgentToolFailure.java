package io.github.foodjournal.application;

final class AgentToolFailure extends RuntimeException {
  private final AgentToolResult result;
  AgentToolFailure(AgentToolResult result) { this.result = result; }
  AgentToolResult result() { return result; }
}
