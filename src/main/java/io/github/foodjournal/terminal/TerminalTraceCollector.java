package io.github.foodjournal.terminal;

import io.github.foodjournal.application.*;
import java.util.*;
import java.util.concurrent.ConcurrentLinkedQueue;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

/** In-memory trace for local prompt evaluation; it stores tool names and outcomes only. */
@Component @Profile("terminal")
public class TerminalTraceCollector implements AgentTraceSink {
  public record ToolTrace(String name, String outcome) {}
  public record Trace(List<ToolTrace> tools, int modelTurns, int replyLength) {}
  private final ThreadLocal<MutableTrace> active = new ThreadLocal<>();
  private final Queue<Trace> completed = new ConcurrentLinkedQueue<>();

  @Override public void started(AgentContext context) { active.set(new MutableTrace()); }
  @Override public void modelReply(JournalAgentModel.AgentReply reply) { MutableTrace trace=active.get(); if(trace!=null) trace.modelTurns++; }
  @Override public void toolResult(JournalAgentModel.ToolCall call, AgentToolResult result) { MutableTrace trace=active.get(); if(trace!=null) trace.tools.add(new ToolTrace(call.name(), result.code())); }
  @Override public void completed(String reply) { MutableTrace trace=active.get(); if(trace!=null) { completed.add(new Trace(List.copyOf(trace.tools),trace.modelTurns,reply==null?0:reply.length())); active.remove(); } }
  public Trace await() { return completed.poll(); }
  private static final class MutableTrace { private final List<ToolTrace> tools=new ArrayList<>(); private int modelTurns; }
}
