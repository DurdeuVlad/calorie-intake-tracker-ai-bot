package io.github.foodjournal.application;

import java.util.*;
import io.github.foodjournal.application.observability.ObservabilityService;
import io.github.foodjournal.application.observability.AgentRunRequestContext;
import io.github.foodjournal.domain.AgentRun;
import io.github.foodjournal.domain.AgentTracePayload;
import io.github.foodjournal.domain.IntegrationEvent;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/** A bounded tool loop. The model is never given repositories or provider credentials. */
@Service
public class JournalAgent {
  private final JournalAgentModel model;
  private final JournalToolExecutor tools;
  private final int maxCalls; private final MeterRegistry metrics; private final ConversationMemoryService memory; private final ObservabilityService observability; private final AgentRunRequestContext requestContext;

  public JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties, MeterRegistry metrics, ConversationMemoryService memory) {
    this(model,tools,properties,metrics,memory,(ObservabilityService)null,null);
  }
  @Autowired public JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties, MeterRegistry metrics, ConversationMemoryService memory, org.springframework.beans.factory.ObjectProvider<ObservabilityService> observability, AgentRunRequestContext requestContext) { this(model,tools,properties,metrics,memory,observability.getIfAvailable(),requestContext); }
  private JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties, MeterRegistry metrics, ConversationMemoryService memory, ObservabilityService observability, AgentRunRequestContext requestContext) { this.model=model;this.tools=tools;this.maxCalls=properties.agentMaxToolCalls();this.metrics=metrics;this.memory=memory;this.observability=observability;this.requestContext=requestContext; }
  public JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties) { this(model,tools,properties,null,null); }

  public String run(AgentContext context) {
    UUID runId=UUID.randomUUID(); AgentRunRequestContext.State request=requestContext==null?null:requestContext.current(); if(requestContext!=null)requestContext.attach(runId); safe(() -> { observability.startRun(runId,request==null?null:request.updateId(),context.user(),request==null?"TEXT":request.inputType(),null); observability.storePrivatePayload(runId,AgentTracePayload.Type.INPUT,context.message()); });
    count("food_journal_agent_runs_total");
    List<JournalAgentModel.AgentExchange> exchanges = new ArrayList<>();
    List<String> todos = new ArrayList<>();
    List<io.github.foodjournal.domain.ConversationMemory> recent=memory==null?List.of():memory.recent(context.user());
    for (int calls = 0; calls < maxCalls; ) {
      long modelStarted=System.nanoTime(); JournalAgentModel.AgentReply reply;
      try { reply=model.next(context, recent, List.copyOf(exchanges)); safe(() -> observability.recordIntegration(runId,"OPENAI","agent_step",null,IntegrationEvent.Outcome.SUCCEEDED,(System.nanoTime()-modelStarted)/1_000_000,null)); }
      catch(RuntimeException failure){safe(() -> { observability.recordIntegration(runId,"OPENAI","agent_step",null,IntegrationEvent.Outcome.FAILED,(System.nanoTime()-modelStarted)/1_000_000,"PROVIDER_FAILURE"); observability.finishRun(runId,AgentRun.Outcome.FAILED,"No reply generated","PROVIDER_FAILURE"); });throw failure;}
      if (reply == null) return finish(runId,unavailable(context),AgentRun.Outcome.FAILED,"EMPTY_REPLY");
      if (reply.toolCalls() == null || reply.toolCalls().isEmpty()) return finish(runId,safeReply(reply.text(), context),AgentRun.Outcome.SUCCEEDED,null);
      for (JournalAgentModel.ToolCall call : reply.toolCalls()) {
        if (calls++ >= maxCalls) { count("food_journal_agent_loop_limit_total"); return finish(runId,limit(context),AgentRun.Outcome.LOOP_LIMIT,"LOOP_LIMIT"); }
        long toolStarted=System.nanoTime(); AgentToolResult raw; try { raw=tools.execute(context, call, todos); } catch (AgentToolFailure failure) { raw=failure.result(); } catch (RuntimeException failure) { raw=AgentToolResult.failure("TEMPORARY_FAILURE","That operation could not be completed now."); } Map<String,Object> data=new LinkedHashMap<>(raw.data()); data.put("todos",List.copyOf(todos)); AgentToolResult result=new AgentToolResult(raw.ok(),raw.code(),Map.copyOf(data),raw.userHint()); final int sequence=calls; final long elapsed=(System.nanoTime()-toolStarted)/1_000_000; safe(() -> observability.recordTool(runId,sequence,call.name(),"validated arguments",""+result.code(),"result fields: "+String.join(",",result.data().keySet()),elapsed,result.ok()?null:result.code())); count("food_journal_agent_tool_calls_total"); if(!result.ok()) count("food_journal_agent_tool_failures_total");
        exchanges.add(new JournalAgentModel.AgentExchange(call, result));
      }
    }
    count("food_journal_agent_loop_limit_total"); return finish(runId,limit(context),AgentRun.Outcome.LOOP_LIMIT,"LOOP_LIMIT");
  }

  private String finish(UUID runId,String reply,AgentRun.Outcome outcome,String error){safe(() -> {observability.storePrivatePayload(runId,AgentTracePayload.Type.FINAL_REPLY,reply);observability.finishRun(runId,outcome,"Reply generated ("+reply.length()+" characters)",error);});return reply;}
  private void safe(Runnable operation){if(observability==null)return;try{operation.run();}catch(RuntimeException ignored){/* tracing must never affect food-journal delivery */}}

  private String safeReply(String text, AgentContext context) {
    if (text == null || text.isBlank()) return unavailable(context);
    return text.length() > 3500 ? text.substring(0, 3500) : text;
  }
  private String unavailable(AgentContext c) { return c.romanian() ? "Nu pot procesa cererea acum. Încearcă din nou sau trimite detaliile mesei în text." : "I cannot process that right now. Please try again or send the meal details as text."; }
  private String limit(AgentContext c) { return c.romanian() ? "Am nevoie de un detaliu în plus ca să termin în siguranță. Spune exact alimentul, cantitatea sau intrarea vizată." : "I need one more detail to finish safely. Tell me the food, quantity, or journal entry involved."; }
  private void count(String metric){if(metrics!=null)metrics.counter(metric).increment();}
}
