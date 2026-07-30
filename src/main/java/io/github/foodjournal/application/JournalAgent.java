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
  private final int maxCalls; private final MeterRegistry metrics; private final ConversationMemoryService memory;

  @Autowired public JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties, MeterRegistry metrics, ConversationMemoryService memory) {
    this.model = model; this.tools = tools; this.maxCalls = properties.agentMaxToolCalls(); this.metrics=metrics; this.memory=memory;
  }
  public JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties) { this(model,tools,properties,null,null); }

  public String run(AgentContext context) {
    count("food_journal_agent_runs_total");
    List<JournalAgentModel.AgentExchange> exchanges = new ArrayList<>();
    List<String> todos = new ArrayList<>();
    boolean entryCreated = false;
    List<io.github.foodjournal.domain.ConversationMemory> recent=memory==null?List.of():memory.recent(context.user());
    for (int calls = 0; calls < maxCalls; ) {
      JournalAgentModel.AgentReply reply = model.next(context, recent, List.copyOf(exchanges));
      if (reply == null) return unavailable(context);
      if (reply.toolCalls() == null || reply.toolCalls().isEmpty()) return safeReply(reply.text(), context);
      for (JournalAgentModel.ToolCall call : reply.toolCalls()) {
        if (calls++ >= maxCalls) { count("food_journal_agent_loop_limit_total"); return limit(context); }
        AgentToolResult raw; if(entryCreated && "create_food_entry".equals(call.name())) raw=AgentToolResult.failure("CONFLICT","A meal was already logged for this message; verify it before replying."); else try { raw=tools.execute(context, call, todos); } catch (AgentToolFailure failure) { raw=failure.result(); } catch (RuntimeException failure) { raw=AgentToolResult.failure("TEMPORARY_FAILURE","That operation could not be completed now."); } if("create_food_entry".equals(call.name())&&raw.ok())entryCreated=true; Map<String,Object> data=new LinkedHashMap<>(raw.data()); data.put("todos",List.copyOf(todos)); AgentToolResult result=new AgentToolResult(raw.ok(),raw.code(),Map.copyOf(data),raw.userHint()); count("food_journal_agent_tool_calls_total"); if(!result.ok()) count("food_journal_agent_tool_failures_total");
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
