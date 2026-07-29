package io.github.foodjournal.admin.web;

import io.github.foodjournal.admin.auth.AdminAuditService;
import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1")
public class AdminApiController {
  private final AgentRunRepository runs; private final AgentToolEventRepository tools; private final OutboundTelegramMessageRepository outbound; private final FoodEntryRepository entries; private final AdminAuditService audit;
  public AdminApiController(AgentRunRepository runs,AgentToolEventRepository tools,OutboundTelegramMessageRepository outbound,FoodEntryRepository entries,AdminAuditService audit){this.runs=runs;this.tools=tools;this.outbound=outbound;this.entries=entries;this.audit=audit;}
  @GetMapping("/analytics/overview") @PreAuthorize("hasAuthority('SCOPE_observability:read')") public Map<String,Object> overview(Authentication a){audit.record("API_KEY",a.getName(),"ANALYTICS_READ","ANALYTICS","overview");return Map.of("agentRuns",runs.count(),"outboxMessages",outbound.count(),"journalEntries",entries.count());}
  @GetMapping("/agent-runs") @PreAuthorize("hasAuthority('SCOPE_observability:read')") public Map<String,Object> runs(@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="50") int limit){Page<AgentRun> data=runs.findAll(PageRequest.of(Math.max(0,page),Math.min(100,Math.max(1,limit)),Sort.by(Sort.Direction.DESC,"startedAt")));return page(data.map(this::run));}
  @GetMapping("/agent-runs/{id}") @PreAuthorize("hasAuthority('SCOPE_observability:read')") public Map<String,Object> run(@PathVariable UUID id){AgentRun r=runs.findById(id).orElseThrow(()->new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.NOT_FOUND));return Map.of("run",run(r),"toolEvents",tools.findByAgentRunCorrelationIdOrderBySequenceNumber(id).stream().map(e->Map.of("sequence",e.getSequenceNumber(),"tool",e.getToolName(),"resultCode",e.getResultCode(),"latencyMs",e.getLatencyMs()==null?0:e.getLatencyMs(),"failure",e.getFailureCategory()==null?"":e.getFailureCategory())).toList());}
  @GetMapping("/outbox") @PreAuthorize("hasAuthority('SCOPE_observability:read')") public Map<String,Object> outbox(@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="50") int limit){Page<OutboundTelegramMessage> data=outbound.findAll(PageRequest.of(Math.max(0,page),Math.min(100,Math.max(1,limit)),Sort.by(Sort.Direction.DESC,"id")));return page(data.map(m->Map.of("id",m.getId(),"chatId",m.getChatId(),"status",m.getStatus().name(),"agentRunId",m.getAgentRun()==null?"":m.getAgentRun().getCorrelationId().toString())));}
  @GetMapping("/journal/entries") @PreAuthorize("hasAuthority('SCOPE_journal:export')") public Map<String,Object> journal(@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="50") int limit,Authentication a){audit.record("API_KEY",a.getName(),"JOURNAL_EXPORT","JOURNAL","entries");Page<FoodEntry> data=entries.findAll(PageRequest.of(Math.max(0,page),Math.min(100,Math.max(1,limit)),Sort.by(Sort.Direction.DESC,"eatenAt")));return page(data.map(e->Map.of("id",e.getId(),"telegramUserId",e.getUser().getTelegramUserId(),"eatenAt",e.getEatenAt().toString(),"calories",e.getCalories(),"source",e.getNutritionSource(),"message",e.getOriginalMessage())));}
  private Map<String,Object> run(AgentRun r){return Map.of("correlationId",r.getCorrelationId().toString(),"outcome",r.getOutcome().name(),"inputType",r.getInputType(),"startedAt",r.getStartedAt().toString(),"finishedAt",r.getFinishedAt()==null?"":r.getFinishedAt().toString(),"toolCalls",r.getToolCallCount(),"error",r.getErrorCategory()==null?"":r.getErrorCategory());}
  private <T> Map<String,Object> page(Page<T> value){return Map.of("page",value.getNumber(),"limit",value.getSize(),"total",value.getTotalElements(),"items",value.getContent());}
}
