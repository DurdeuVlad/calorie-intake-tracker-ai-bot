package io.github.foodjournal.terminal;

import java.io.*;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

@Component @Profile("terminal") @ConditionalOnProperty(prefix="food-journal.terminal",name="runner-enabled",havingValue="true",matchIfMissing=true)
public class TerminalChatRunner implements ApplicationRunner {
  private final TerminalConversation chat; private final TerminalProperties terminal; private final TerminalEvaluationRunner evaluations;
  public TerminalChatRunner(TerminalConversation chat, TerminalProperties terminal, TerminalEvaluationRunner evaluations) { this.chat=chat; this.terminal=terminal; this.evaluations=evaluations; }

  @Override public void run(ApplicationArguments arguments) throws Exception {
    if (terminal.evalFile()!=null) { System.exit(evaluations.run(terminal.evalFile())); return; }
    boolean trace=false; System.out.println("Food Journal terminal chat. Type :help for commands.");
    try (BufferedReader input=new BufferedReader(new InputStreamReader(System.in))) {
      while (true) {
        System.out.print("you> "); String line=input.readLine(); if(line==null||":quit".equalsIgnoreCase(line.trim())) break;
        String command=line.trim(); if(":help".equalsIgnoreCase(command)) { System.out.println(":help, :trace on, :trace off, :quit. Any other text is sent as a Telegram-style message."); continue; }
        if(":trace on".equalsIgnoreCase(command)) { trace=true; System.out.println("Trace enabled."); continue; }
        if(":trace off".equalsIgnoreCase(command)) { trace=false; System.out.println("Trace disabled."); continue; }
        if(line.isBlank()) continue;
        try { TerminalConversation.Result result=chat.send(line); System.out.println("bot> "+result.reply()); if(trace) printTrace(result.trace()); }
        catch(Exception failure) { System.out.println("bot> Local processing failed: "+failure.getClass().getSimpleName()); }
      }
    }
  }
  private void printTrace(TerminalTraceCollector.Trace trace) { if(trace==null) { System.out.println("trace> no agent call"); return; } System.out.println("trace> model turns="+trace.modelTurns()+", tools="+trace.tools()); }
}
