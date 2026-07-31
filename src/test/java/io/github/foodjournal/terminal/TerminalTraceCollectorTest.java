package io.github.foodjournal.terminal;

import static org.assertj.core.api.Assertions.assertThat;

import io.github.foodjournal.application.*;
import io.github.foodjournal.domain.FoodUser;
import java.util.Map;
import org.junit.jupiter.api.Test;

class TerminalTraceCollectorTest {
  @Test void retainsOnlyToolNameAndOutcomeInsteadOfArgumentsOrProviderPayloads() {
    TerminalTraceCollector collector=new TerminalTraceCollector();
    collector.started(new AgentContext(new FoodUser(1,"Local"),1,true,"secret meal"));
    collector.modelReply(new JournalAgentModel.AgentReply(null,java.util.List.of()));
    collector.toolResult(new JournalAgentModel.ToolCall("call","create_food_entry","{\"apiKey\":\"must-not-appear\"}"),AgentToolResult.ok(Map.of()));
    collector.completed("Saved.");

    TerminalTraceCollector.Trace trace=collector.await();

    assertThat(trace.modelTurns()).isEqualTo(1);
    assertThat(trace.tools()).containsExactly(new TerminalTraceCollector.ToolTrace("create_food_entry","OK"));
  }
}
