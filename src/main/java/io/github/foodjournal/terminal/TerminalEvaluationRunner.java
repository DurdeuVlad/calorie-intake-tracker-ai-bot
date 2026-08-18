package io.github.foodjournal.terminal;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.InputStream;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import io.github.foodjournal.config.BotProperties;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/** Opt-in real-model evaluation runner. It is deliberately outside Maven and CI. */
@Component @Profile("terminal")
public class TerminalEvaluationRunner {
  public record Fixture(String version, List<Scenario> scenarios) {}
  public record Scenario(String id, boolean startOnboarded, List<Turn> turns) {}
  public record Turn(String input, List<Expectation> assertions) {}
  public record Expectation(String category, boolean critical, String type, String tool, String outcome, Long value, List<String> values) {}
  private record Snapshot(long entries, long pendingActions, long pendingDrafts, long pendingQuotes, long memories) {}
  private final TerminalConversation chat; private final TerminalProperties terminal; private final ObjectMapper json; private final JdbcTemplate db; private final BotProperties bot;

  public TerminalEvaluationRunner(TerminalConversation chat, TerminalProperties terminal, ObjectMapper json, JdbcTemplate db, BotProperties bot) { this.chat=chat; this.terminal=terminal; this.json=json; this.db=db; this.bot=bot; }

  public int run(String fixturePath) throws Exception {
    Fixture fixture=read(fixturePath); List<Scenario> scenarios=fixture.scenarios()==null?List.of():fixture.scenarios();
    if(terminal.evalScenario()!=null) scenarios=scenarios.stream().filter(s->s.id().equals(terminal.evalScenario())).toList();
    if(scenarios.isEmpty()) throw new IllegalArgumentException("No evaluation scenarios selected");
    List<Map<String,Object>> runs=new ArrayList<>(); List<TerminalEvaluationScorer.AssertionResult> allAssertions=new ArrayList<>(); OutcomeMetrics outcomes=new OutcomeMetrics();
    for(Scenario scenario:scenarios) for(int repetition=1;repetition<=terminal.evalRepeats();repetition++) {
      cleanUserState(); if(scenario.startOnboarded()) completeOnboarding(); Snapshot before=snapshot(); outcomes.recordScenarioStart(before); List<Map<String,Object>> turns=new ArrayList<>(); int turnIndex=0;
      for(Turn turn:scenario.turns()) {
        TerminalConversation.Result response=chat.send(turn.input()); Snapshot after=snapshot(); List<TerminalEvaluationScorer.AssertionResult> results=evaluate(turn.assertions(),response,after); String runLabel=scenario.id()+"#"+repetition+"/";
        outcomes.recordTurn(turnIndex++,before,after,response.reply());
        allAssertions.addAll(results.stream().map(result->new TerminalEvaluationScorer.AssertionResult(result.category(),result.critical(),result.passed(),runLabel+result.label())).toList()); Map<String,Object> detail=new LinkedHashMap<>();
        detail.put("input", terminal.evalFullReport()?turn.input():redact(turn.input())); detail.put("reply",terminal.evalFullReport()?response.reply():redact(response.reply()));
        detail.put("trace",response.trace()); detail.put("before",before); detail.put("after",after); detail.put("assertions",results); turns.add(detail); before=after;
      }
      runs.add(Map.of("scenario",scenario.id(),"startOnboarded",scenario.startOnboarded(),"repetition",repetition,"turns",turns));
    }
    TerminalEvaluationScorer.Score score=TerminalEvaluationScorer.score(allAssertions); Path output=reportPath(); Files.createDirectories(output.getParent());
    Map<String,Object> report=new LinkedHashMap<>(); report.put("ranAt",Instant.now().toString()); report.put("fixture",fixturePath); report.put("fixtureVersion",fixture.version()); report.put("model",bot.openaiModel()); report.put("repeats",terminal.evalRepeats()); report.put("fullText",terminal.evalFullReport()); report.put("score",score); report.put("userOutcomes",outcomes.summary()); report.put("runs",runs); report.put("baselineDelta",baselineDelta(score));
    json.writerWithDefaultPrettyPrinter().writeValue(output.toFile(),report); print(score,output); return score.safetyReleasePassed()&&score.qualityScore()>=75?0:1;
  }

  private List<TerminalEvaluationScorer.AssertionResult> evaluate(List<Expectation> assertions, TerminalConversation.Result response, Snapshot state) {
    if(assertions==null)return List.of(); List<TerminalEvaluationScorer.AssertionResult> results=new ArrayList<>();
    List<TerminalTraceCollector.ToolTrace> tools=response.trace()==null?List.of():response.trace().tools(); String reply=normalize(response.reply());
    for(Expectation expectation:assertions) { boolean pass=switch(expectation.type()) {
      case "tool_required" -> tools.stream().anyMatch(t->t.name().equals(expectation.tool()));
      case "tool_forbidden" -> tools.stream().noneMatch(t->t.name().equals(expectation.tool()));
      case "tool_outcome" -> tools.stream().anyMatch(t->t.name().equals(expectation.tool())&&t.outcome().equals(expectation.outcome()));
      case "entries_exact" -> state.entries()==expectation.value();
      case "entries_at_least" -> state.entries()>=expectation.value();
      case "entries_at_most" -> state.entries()<=expectation.value();
      case "reply_contains_any" -> expectation.values()!=null&&expectation.values().stream().anyMatch(value->containsExpectedPhrase(reply,value));
      case "reply_not_contains" -> expectation.values()==null||expectation.values().stream().map(TerminalEvaluationRunner::normalize).noneMatch(reply::contains);
      default -> throw new IllegalArgumentException("Unknown evaluation assertion: "+expectation.type()); };
      TerminalEvaluationScorer.Category category=TerminalEvaluationScorer.Category.valueOf(expectation.category()); results.add(new TerminalEvaluationScorer.AssertionResult(category,expectation.critical(),pass,label(expectation)));
    } return results;
  }
  private String label(Expectation e){return e.category()+":"+e.type()+(e.tool()==null?"":":"+e.tool());}
  static boolean containsExpectedPhrase(String reply,String expected){String normalized=normalize(expected);return normalized.length()>3?reply.contains(normalized):reply.matches("(?s).*?(?<![\\p{L}\\p{N}])"+java.util.regex.Pattern.quote(normalized)+"(?![\\p{L}\\p{N}]).*");}
  static String normalize(String text){return java.text.Normalizer.normalize(text==null?"":text,java.text.Normalizer.Form.NFD).replaceAll("\\p{M}","").toLowerCase(Locale.ROOT);}
  private Fixture read(String fixture) throws Exception { if(fixture.startsWith("classpath:")) try(InputStream input=getClass().getClassLoader().getResourceAsStream(fixture.substring(10))){if(input==null)throw new IllegalArgumentException("Evaluation fixture not found: "+fixture);return json.readValue(input,Fixture.class);} return json.readValue(Path.of(fixture).toFile(),Fixture.class); }
  private void cleanUserState(){ String userId=String.valueOf(terminal.userId()); db.update("delete from messaging_outbox where provider = 'terminal' and conversation_id = ?",userId); db.update("delete from messaging_inbox where provider = 'terminal'"); db.update("delete from food_users where telegram_user_id = ?",terminal.userId()); }
  private void completeOnboarding() { /* Kept for fixture compatibility: profiles now work without setup. */ }
  private Snapshot snapshot(){ Long id=db.query("select id from food_users where telegram_user_id=?",rs->rs.next()?rs.getLong(1):null,terminal.userId()); if(id==null)return new Snapshot(0,0,0,0,0); return new Snapshot(activeEntries(id),count("pending_agent_actions",id),count("pending_food_drafts",id),count("pending_nutrition_quotes",id),count("conversation_memory",id)); }
  private long activeEntries(Long userId){return db.queryForObject("select count(*) from food_entries where user_id=? and deleted_at is null",Long.class,userId);}
  private long count(String table,Long userId){return db.queryForObject("select count(*) from "+table+" where user_id=?",Long.class,userId);}
  @SuppressWarnings("unchecked") private Map<String,Object> baselineDelta(TerminalEvaluationScorer.Score current){ if(terminal.evalBaselineFile()==null)return Map.of(); try { Map<String,Object> prior=json.readValue(Path.of(terminal.evalBaselineFile()).toFile(),new TypeReference<>(){}); Map<String,Object> score=(Map<String,Object>)prior.get("score"); Number old=(Number)score.get("qualityScore"); Map<String,Object> delta=new LinkedHashMap<>(); delta.put("qualityScore",Math.round((current.qualityScore()-old.doubleValue())*10d)/10d); Map<String,Number> oldCategories=(Map<String,Number>)score.get("categories"); current.categories().forEach((name,value)->delta.put(name,Math.round((value-oldCategories.get(name).doubleValue())*10d)/10d)); delta.put("baseline",terminal.evalBaselineFile()); return delta; } catch(Exception e){return Map.of("error","baseline unreadable");} }
  private Path reportPath(){return terminal.reportFile()==null?Path.of("eval-reports","live-eval-"+Instant.now().toEpochMilli()+".json"):Path.of(terminal.reportFile());}
  static String redact(String value){return "<redacted:length="+(value==null?0:value.length())+">";}
  private void print(TerminalEvaluationScorer.Score score,Path output){System.out.printf("Live evaluation: %.1f/100 (%s); safety release: %s%n",score.qualityScore(),score.band(),score.safetyReleasePassed()?"PASS":"FAIL"); System.out.println("Categories: "+score.categories()); if(!score.criticalFailures().isEmpty())System.out.println("Critical failures: "+score.criticalFailures()); System.out.println("Report: "+output.toAbsolutePath());}
  private static final class OutcomeMetrics {
    private int scenarioRuns; private int leakedScenarios; private int firstTurns; private int firstTurnCaptures; private int turns; private int entryMutations; private int corrections; private int undos; private int clarifications;
    void recordScenarioStart(Snapshot before){scenarioRuns++;if(before.entries()!=0||before.pendingActions()!=0||before.pendingDrafts()!=0||before.pendingQuotes()!=0||before.memories()!=0)leakedScenarios++;}
    void recordTurn(int index,Snapshot before,Snapshot after,String reply){turns++;long delta=after.entries()-before.entries();if(index==0){firstTurns++;if(delta>0)firstTurnCaptures++;}if(delta>0)entryMutations++;if(delta<0)corrections++;String normalized=normalize(reply);if(normalized.contains("restored")||normalized.contains("restaurat"))undos++;if(normalized.contains("how much")||normalized.contains("quantity")||normalized.contains("cantitate")||normalized.contains("which one"))clarifications++;}
    Map<String,Object> summary(){Map<String,Object> m=new LinkedHashMap<>();m.put("scenarioRuns",scenarioRuns);m.put("firstTurnEntryRate",firstTurns==0?0d:round((double)firstTurnCaptures/firstTurns));m.put("entryMutations",entryMutations);m.put("corrections",corrections);m.put("undoRestorations",undos);m.put("clarificationReplies",clarifications);m.put("crossScenarioLeakage",leakedScenarios);m.put("turns",turns);return m;}
    private double round(double value){return Math.round(value*1000d)/1000d;}
  }
}
