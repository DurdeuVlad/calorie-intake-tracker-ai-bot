package io.github.foodjournal.application;

import java.util.*;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/** A bounded tool loop. The model is never given repositories or provider credentials. */
@Service
public class JournalAgent {
  private final JournalAgentModel model;
  private final JournalToolExecutor tools;
  private final int maxCalls; private final MeterRegistry metrics;

  @Autowired public JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties, MeterRegistry metrics) {
    this.model = model; this.tools = tools; this.maxCalls = properties.agentMaxToolCalls(); this.metrics=metrics;
  }
  public JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties) { this(model,tools,properties,null); }

  public String run(AgentContext context) {
    count("food_journal_agent_runs_total");
    List<JournalAgentModel.AgentExchange> exchanges = new ArrayList<>();
    List<String> todos = new ArrayList<>();
    for (int calls = 0; calls < maxCalls; ) {
      JournalAgentModel.AgentReply reply = model.next(context, List.copyOf(exchanges));
      if (reply == null) return unavailable(context);
      if (reply.toolCalls() == null || reply.toolCalls().isEmpty()) return safeReply(reply.text(), context);
      for (JournalAgentModel.ToolCall call : reply.toolCalls()) {
        if (calls++ >= maxCalls) { count("food_journal_agent_loop_limit_total"); return limit(context); }
        AgentToolResult raw=tools.execute(context, call, todos); Map<String,Object> data=new LinkedHashMap<>(raw.data()); data.put("todos",List.copyOf(todos)); AgentToolResult result=new AgentToolResult(raw.ok(),raw.code(),Map.copyOf(data),raw.userHint()); count("food_journal_agent_tool_calls_total"); if(!result.ok()) count("food_journal_agent_tool_failures_total");
        exchanges.add(new JournalAgentModel.AgentExchange(call, result));
      }
    }
    count("food_journal_agent_loop_limit_total"); return limit(context);
  }

  private String safeReply(String text, AgentContext context) {
    if (text == null || text.isBlank()) return unavailable(context);
    return text.length() > 3500 ? text.substring(0, 3500) : text;
  }
  private String unavailable(AgentContext c) { return c.romanian() ? "Nu pot procesa cererea acum. Încearcă din nou sau trimite detaliile mesei în text." : "I cannot process that right now. Please try again or send the meal details as text."; }
  private String limit(AgentContext c) { return c.romanian() ? "Am nevoie de un detaliu în plus ca să termin în siguranță. Spune exact alimentul, cantitatea sau intrarea vizată." : "I need one more detail to finish safely. Tell me the food, quantity, or journal entry involved."; }
  private void count(String metric){if(metrics!=null)metrics.counter(metric).increment();}
}
