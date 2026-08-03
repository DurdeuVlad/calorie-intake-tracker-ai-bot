package io.github.foodjournal.application;

import java.util.*;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

/** A bounded tool loop. The model is never given repositories or provider credentials. */
@Service
public class JournalAgent {
  private final JournalAgentModel model;
  private final JournalToolExecutor tools;
  private final int maxCalls; private final MeterRegistry metrics; private final ConversationMemoryService memory; private final AgentTraceSink trace;

  @Autowired public JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties, MeterRegistry metrics, ConversationMemoryService memory, ObjectProvider<AgentTraceSink> traces) {
    this.model = model; this.tools = tools; this.maxCalls = properties.agentMaxToolCalls(); this.metrics=metrics; this.memory=memory; this.trace=traces.getIfAvailable(AgentTraceSink::noop);
  }
  public JournalAgent(JournalAgentModel model, JournalToolExecutor tools, io.github.foodjournal.config.BotProperties properties) { this.model=model; this.tools=tools; this.maxCalls=properties.agentMaxToolCalls(); this.metrics=null; this.memory=null; this.trace=AgentTraceSink.noop(); }

  public String run(AgentContext context) {
    trace.started(context);
    count("food_journal_agent_runs_total");
    List<JournalAgentModel.AgentExchange> exchanges = new ArrayList<>();
    List<String> todos = new ArrayList<>();
    List<io.github.foodjournal.domain.ConversationMemory> recent=memory==null?List.of():memory.recent(context.user());
    AgentContext active=estimateFollowupContext(context,recent);
    for (int calls = 0; calls < maxCalls; ) {
      JournalAgentModel.AgentReply reply = model.next(active, recent, List.copyOf(exchanges));
      trace.modelReply(reply);
      if (reply == null) return complete(unavailable(active));
      if (reply.toolCalls() == null || reply.toolCalls().isEmpty()) return complete(safeReply(reply.text(), active));
      for (JournalAgentModel.ToolCall call : reply.toolCalls()) {
        if (calls++ >= maxCalls) { count("food_journal_agent_loop_limit_total"); return complete(limit(active)); }
        AgentToolResult raw; try { raw=tools.execute(active, call, todos); } catch (AgentToolFailure failure) { raw=failure.result(); } catch (RuntimeException failure) { raw=AgentToolResult.failure("TEMPORARY_FAILURE","That operation could not be completed now."); } Map<String,Object> data=new LinkedHashMap<>(raw.data()); data.put("todos",List.copyOf(todos)); AgentToolResult result=new AgentToolResult(raw.ok(),raw.code(),Map.copyOf(data),raw.userHint()); count("food_journal_agent_tool_calls_total"); if(!result.ok()) count("food_journal_agent_tool_failures_total");
        exchanges.add(new JournalAgentModel.AgentExchange(call, result));
        trace.toolResult(call, result);
        String rendered=canonicalReply(active,call,result);
        if(rendered!=null)return complete(rendered);
      }
    }
    count("food_journal_agent_loop_limit_total"); return complete(limit(active));
  }

  private String complete(String reply) { trace.completed(reply); return reply; }

  private AgentContext estimateFollowupContext(AgentContext context,List<io.github.foodjournal.domain.ConversationMemory> recent){
    String reply=context.message()==null?"":context.message().trim().toLowerCase(Locale.ROOT);
    boolean declined=reply.contains("nu știu")||reply.contains("nu stiu")||reply.contains("estimează")||reply.contains("estimeaza")||reply.contains("i don't know")||reply.contains("estimate it");
    if(!declined||recent.size()<2)return context;
    io.github.foodjournal.domain.ConversationMemory previousAssistant=recent.get(recent.size()-1);
    if(!"assistant".equals(previousAssistant.getRole())||!looksLikePortionQuestion(previousAssistant.getContent()))return context;
    for(int i=recent.size()-2;i>=0;i--){io.github.foodjournal.domain.ConversationMemory turn=recent.get(i);if("user".equals(turn.getRole()))return new AgentContext(context.user(),context.chatId(),context.romanian(),"Estimate this meal now: "+turn.getContent(),context.startedAt());}
    return context;
  }
  private boolean looksLikePortionQuestion(String text){String value=text==null?"":text.toLowerCase(Locale.ROOT);return value.contains("gram")||value.contains("quantity")||value.contains("cantitate")||value.contains("cât")||value.contains("cat ");}

  private String safeReply(String text, AgentContext context) {
    if (text == null || text.isBlank()) return unavailable(context);
    return text.length() > 3500 ? text.substring(0, 3500) : text;
  }
  @SuppressWarnings("unchecked") private String canonicalReply(AgentContext c,JournalAgentModel.ToolCall call,AgentToolResult result){
    if("apply_journal_actions".equals(call.name())&&result.ok()){
      Object raw=result.data().get("results"); List<Map<String,Object>> rows=raw instanceof List<?> list?list.stream().filter(Map.class::isInstance).map(value->(Map<String,Object>)value).toList():List.of();
      if(rows.isEmpty())return c.romanian()?"Nu am putut aplica nicio schimbare.":"No journal changes could be applied.";
      List<String> rendered=new ArrayList<>();
      for(Map<String,Object> row:rows){boolean ok=Boolean.TRUE.equals(row.get("ok"));String type=String.valueOf(row.getOrDefault("type","ACTION"));if(!ok){rendered.add("- "+String.valueOf(row.getOrDefault("message",c.romanian()?"Schimbarea a eÈ™uat.":"The change failed.")));continue;}Object entryRaw=row.get("entry");Map<String,Object> entry=entryRaw instanceof Map<?,?> map?(Map<String,Object>)map:Map.of();String description=String.valueOf(entry.getOrDefault("description","entry"));String calories=String.valueOf(entry.getOrDefault("calories","?"));String date=String.valueOf(row.getOrDefault("date",entry.getOrDefault("date","")));String verb=switch(type){case "CREATE"->c.romanian()?"Notat":"Logged";case "EDIT"->c.romanian()?"Modificat":"Updated";case "MOVE"->c.romanian()?"Mutat":"Moved";case "DELETE"->c.romanian()?"È˜ters":"Deleted";default->c.romanian()?"Aplicat":"Applied";};rendered.add("- "+verb+": "+description+" â€” "+calories+" kcal"+(date.isBlank()?"":" ("+date+")"));}
      boolean undoable=Boolean.TRUE.equals(result.data().get("undoAvailable"));String suffix=undoable?(c.romanian()?"\nScrie Undo Ã®n urmÄƒtoarele 10 minute pentru a anula schimbÄƒrile reuÈ™ite.":"\nSend Undo within 10 minutes to reverse the successful changes."):"";
      return String.join("\n",rendered)+suffix;
    }
    if("undo_last_change".equals(call.name())&&result.ok())return c.romanian()?"Am anulat ultima schimbare din jurnal.":"Undid the latest journal change.";
    if(!result.ok())return null;
    if("create_food_entry".equals(call.name())){
      Object raw=result.data().get("entry"); Map<String,Object> entry=raw instanceof Map<?,?> map?(Map<String,Object>)map:Map.of();
      if(!entry.containsKey("description")||!entry.containsKey("calories"))return null;
      String description=String.valueOf(entry.get("description")); Object calories=entry.get("calories");
      Object todayRaw=result.data().get("today"); Map<String,Object> today=todayRaw instanceof Map<?,?> map?(Map<String,Object>)map:Map.of();
      String estimated=Boolean.TRUE.equals(result.data().get("estimated"))?(c.romanian()?" Estimare; spune-mi porția exactă dacă vrei să o corectez.":" Estimate; tell me the exact portion to correct it."):"";
      return c.romanian()?(Boolean.TRUE.equals(result.data().get("estimated"))?"Am estimat ":"Am notat ")+description+": "+calories+" kcal. Total azi: "+today.getOrDefault("calories",calories)+" kcal."+estimated:(Boolean.TRUE.equals(result.data().get("estimated"))?"Estimated ":"Logged ")+description+": "+calories+" kcal. Today: "+today.getOrDefault("calories",calories)+" kcal."+estimated;
    }
    return null;
  }
  private String unavailable(AgentContext c) { return c.romanian() ? "Nu pot procesa cererea acum. Încearcă din nou sau trimite detaliile mesei în text." : "I cannot process that right now. Please try again or send the meal details as text."; }
  private String limit(AgentContext c) { return c.romanian() ? "Am nevoie de un detaliu în plus ca să termin în siguranță. Spune exact alimentul, cantitatea sau intrarea vizată." : "I need one more detail to finish safely. Tell me the food, quantity, or journal entry involved."; }
  private void count(String metric){if(metrics!=null)metrics.counter(metric).increment();}
}
