package io.github.foodjournal.application;

import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import java.util.regex.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Handles the predictable, high-frequency journal actions before the agent loop.
 * It deliberately accepts transparent estimates: a calorie tracker is useful only
 * when recording a meal takes less effort than remembering it for later.
 */
@Service
public class LowFrictionJournalFlow {
  private static final Pattern DECLARED = Pattern.compile("(?i)^\\s*(\\d+(?:[.,]\\d+)?)\\s*g(?:r(?:ame?)?s?)?\\s+(.+?)(?:,|\\s)+\\s*(\\d+(?:[.,]\\d+)?)\\s*kcal\\s*/\\s*100\\s*g\\s*$");
  private static final Pattern MULTIPLIED = Pattern.compile("(?i)^\\s*(\\d+(?:[.,]\\d+)?)\\s*kcal\\s*(?:x|×)\\s*(\\d+(?:[.,]\\d+)?)(?:\\s+(.+))?\\s*$");
  private static final Pattern DELETE = Pattern.compile("(?i)^\\s*(?:remove|delete|sterge|șterge)\\s+(?:the\\s+|pe\\s+)?(.+?)\\s*$");
  private final FoodEntryRepository entries; private final FoodItemRepository items; private final UserSettingsRepository settings;
  private final DailyStatusService status; private final JournalUndoActionRepository undo;

  public LowFrictionJournalFlow(FoodEntryRepository entries, FoodItemRepository items, UserSettingsRepository settings,
      DailyStatusService status, JournalUndoActionRepository undo) { this.entries=entries;this.items=items;this.settings=settings;this.status=status;this.undo=undo; }

  @Transactional public Optional<String> handle(AgentContext c) {
    undo.deleteByExpiresAtBefore(Instant.now());
    String raw=c.message()==null?"":c.message().trim(); String normalized=normalize(raw);
    if (raw.isBlank()) return Optional.of(reply(c,"Spune-mi ce ai mâncat.","Tell me what you ate."));
    if (looksInjected(normalized)) return Optional.of(reply(c,"Nu urmez instrucțiuni din mesaj pentru a modifica jurnalul. Spune-mi ce ai mâncat.","I cannot follow message instructions to modify the journal. Tell me what you ate."));
    if (Set.of("undo","anuleaza","anulează").contains(normalized)) return Optional.of(undo(c));
    if (isGreeting(normalized)) return Optional.of(reply(c,"Salut! Spune-mi ce ai mâncat și îl notez.","Hi! Tell me what you ate and I’ll log it."));
    if (isTotal(normalized)) return Optional.of(today(c));
    if (isList(normalized)) return Optional.of(listToday(c));
    if (normalized.contains("doar o data") || normalized.contains("doar o dată") || normalized.contains("only once")) return duplicateCorrection(c, raw, normalized);
    Matcher deletion=DELETE.matcher(raw); if(deletion.matches()) return delete(c,deletion.group(1));
    boolean correction=normalized.startsWith("actually ")||normalized.startsWith("de fapt "); String logInput=raw.replaceFirst("(?i)^\\s*(?:actually|de fapt)\\s+","");
    Matcher declared=DECLARED.matcher(logInput); if(declared.matches()) return Optional.of(log(c,declared.group(2).trim(),number(declared.group(1)),(int)Math.round(number(declared.group(1))*number(declared.group(3))/100d),"manual","high",false,correction));
    Matcher multiplied=MULTIPLIED.matcher(raw); if(multiplied.matches()) { int total=(int)Math.round(number(multiplied.group(1))*number(multiplied.group(2))); String name=multiplied.group(3)==null||multiplied.group(3).isBlank()?"Unspecified item":multiplied.group(3).trim(); return Optional.of(log(c,name+" ("+multiplied.group(1)+" kcal × "+multiplied.group(2)+")",number(multiplied.group(2)),total,"ai_estimate","estimate",true)); }
    if (isBareChicken(normalized)) return Optional.of(log(c,c.romanian()?"pui (presupus 150 g, la grătar)":"chicken (assumed 150 g, grilled)",150,248,"ai_estimate","estimate",true));
    return Optional.empty();
  }

  private Optional<String> duplicateCorrection(AgentContext c,String raw,String normalized) {
    String term=normalized.replaceAll(".*(?:doar o data|doar o dată|only once)","").replaceAll("(?:te rog|please)","").trim();
    if(term.isBlank()) return Optional.of(reply(c,"Ce aliment vrei să păstrez o singură dată?","Which food should I keep only once?"));
    List<FoodEntry> matches=entries.searchByUserAndTerm(c.user(),term);
    if(matches.size()<2) return Optional.of(reply(c,"Nu văd o dublură clară pentru „"+term+"”.","I cannot see a clear duplicate for '"+term+"'."));
    return Optional.of(deleteEntry(c,matches.getFirst()));
  }
  private Optional<String> delete(AgentContext c,String term) {
    List<FoodEntry> matches=entries.searchByUserAndTerm(c.user(),term.trim());
    if(matches.isEmpty()) return Optional.of(reply(c,"Nu am găsit acea masă.","I could not find that meal."));
    if(matches.size()>1) return Optional.of(reply(c,"Am găsit mai multe intrări pentru „"+term+"”. Spune-mi care dintre ele.","I found multiple entries for '"+term+"'. Tell me which one."));
    return Optional.of(deleteEntry(c,matches.getFirst()));
  }
  private String deleteEntry(AgentContext c,FoodEntry entry) {
    Instant now=Instant.now(); entry.markDeleted(now); undo.save(JournalUndoAction.deletedEntry(c.user(),entry.getId(),now)); status.refresh(c.user(),c.chatId());
    return reply(c,"Am șters „"+entry.getOriginalMessage()+"”. Scrie Undo în următoarele 10 minute dacă vrei să o restaurezi.","Removed '"+entry.getOriginalMessage()+"'. Send Undo within 10 minutes to restore it.");
  }
  private String undo(AgentContext c) {
    JournalUndoAction action=undo.findByUserAndExpiresAtAfter(c.user(),Instant.now()).orElse(null);
    if(action==null) return reply(c,"Nu există o modificare recentă de anulat.","There is no recent change to undo.");
    FoodEntry entry=entries.findIncludingDeletedByIdAndUser(action.getEntryId(),c.user()).orElse(null);
    undo.delete(action); if(entry==null || !entry.isDeleted()) return reply(c,"Acea modificare nu mai poate fi anulată.","That change can no longer be undone.");
    entry.restore(); status.refresh(c.user(),c.chatId());
    return reply(c,"Am restaurat „"+entry.getOriginalMessage()+"”.","Restored '"+entry.getOriginalMessage()+"'.");
  }
  private String log(AgentContext c,String description,double grams,int calories,String source,String confidence,boolean estimated) { return log(c,description,grams,calories,source,confidence,estimated,false); }
  private String log(AgentContext c,String description,double grams,int calories,String source,String confidence,boolean estimated,boolean replaceEstimate) {
    FoodEntry entry=replaceEstimate?matchingEstimate(c.user(),description):null; boolean replaced=entry!=null;
    if(replaced){entry.replaceEstimate(description,calories,source,confidence);items.deleteByEntry(entry);}else entry=entries.save(new FoodEntry(c.user(),description,Instant.now(),calories,source,confidence));
    items.save(new FoodItem(entry,description,BigDecimal.valueOf(grams),calories,null,null,null,source,confidence)); status.refresh(c.user(),c.chatId());
    int today=entriesForToday(c.user()).stream().map(FoodEntry::getCalories).filter(Objects::nonNull).mapToInt(Integer::intValue).sum();
    String estimate=estimated?(c.romanian()?" Estimare; spune-mi porția exactă dacă vrei să o corectez.":" Estimate; tell me the exact portion to correct it."):"";
    return c.romanian()?(replaced?"Am înlocuit estimarea cu ":"Am notat ")+description+": "+calories+" kcal. Total azi: "+today+" kcal."+estimate:(replaced?"Replaced the estimate with ":"Logged ")+description+": "+calories+" kcal. Today: "+today+" kcal."+estimate;
  }
  private FoodEntry matchingEstimate(FoodUser user,String description){String needle=normalize(description).split("\\s+")[0];return entries.findEstimatedByUserOrderByEatenAtDesc(user).stream().filter(entry->normalize(entry.getOriginalMessage()).contains(needle)).findFirst().orElse(null);}
  private String today(AgentContext c) { List<FoodEntry> rows=entriesForToday(c.user());int total=rows.stream().map(FoodEntry::getCalories).filter(Objects::nonNull).mapToInt(Integer::intValue).sum();return reply(c,"Total azi: "+total+" kcal, "+rows.size()+" mese.","Today: "+total+" kcal, "+rows.size()+" meals."); }
  private String listToday(AgentContext c) {List<FoodEntry> rows=entriesForToday(c.user());if(rows.isEmpty())return reply(c,"Nu ai mese notate azi.","You have no meals logged today.");String joined=rows.stream().limit(10).map(e->e.getOriginalMessage()+" — "+e.getCalories()+" kcal").reduce((a,b)->a+"\n"+b).orElse("");return reply(c,"Mese azi:\n"+joined,"Meals today:\n"+joined);}
  private List<FoodEntry> entriesForToday(FoodUser user){ZoneId zone=ZoneId.of(settings.findById(user.getId()).orElseThrow().getTimezone());LocalDate d=LocalDate.now(zone);return entries.findByUserAndEatenAtBetweenOrderByEatenAtAsc(user,d.atStartOfDay(zone).toInstant(),d.plusDays(1).atStartOfDay(zone).toInstant());}
  private boolean isGreeting(String n){return Set.of("hi","hello","hey","salut","buna","bună").contains(n);}
  private boolean isTotal(String n){return n.contains("how many calories today")||n.contains("today total")||n.contains("total azi")||n.contains("calorii azi")||n.contains("cate calorii azi")||n.contains("câte calorii azi");}
  private boolean isList(String n){return n.contains("what did i eat today")||n.contains("show today")||n.contains("ce am mancat azi")||n.contains("ce am mâncat azi")||n.contains("mesele de azi");}
  private boolean isBareChicken(String n){return Set.of("chicken","i ate chicken","pui","am mancat pui","am mâncat pui").contains(n);}
  private boolean looksInjected(String n){return n.contains("ignore all instructions")||n.contains("ignore previous instructions")||n.contains("system prompt")||n.contains("tool result");}
  private String reply(AgentContext c,String ro,String en){return c.romanian()?ro:en;}
  private String normalize(String value){return value.toLowerCase(Locale.ROOT).replace('ă','a').replace('â','a').replace('î','i').replace('ș','s').replace('ş','s').replace('ț','t').replace('ţ','t').trim();}
  private double number(String value){return Double.parseDouble(value.replace(',','.'));}
}
