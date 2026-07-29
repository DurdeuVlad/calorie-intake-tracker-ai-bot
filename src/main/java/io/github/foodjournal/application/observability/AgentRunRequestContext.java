package io.github.foodjournal.application.observability;

import java.util.UUID;
import org.springframework.stereotype.Component;

/** Request-thread metadata used only to correlate a Telegram update, agent run, and outbox row. */
@Component
public class AgentRunRequestContext {
  private final ThreadLocal<State> state=new ThreadLocal<>();
  public void begin(Long updateId,String inputType){state.set(new State(updateId,inputType,null));}
  public State current(){return state.get();}
  public void attach(UUID runId){State current=state.get();if(current!=null)state.set(new State(current.updateId(),current.inputType(),runId));}
  public void clear(){state.remove();}
  public record State(Long updateId,String inputType,UUID runId) {}
}
