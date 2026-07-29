package io.github.foodjournal.admin.web;

import io.github.foodjournal.admin.api_key.*;
import io.github.foodjournal.application.observability.ObservabilityService;
import io.github.foodjournal.domain.*;
import io.github.foodjournal.repository.*;
import java.time.Instant;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

@Controller
@RequestMapping("/admin")
public class AdminDashboardController {
  private final AgentRunRepository runs; private final AgentToolEventRepository tools; private final IntegrationEventRepository integrations; private final OutboundTelegramMessageRepository outbound; private final FoodEntryRepository entries; private final ApiKeyService keys; private final ObservabilityService traces;
  public AdminDashboardController(AgentRunRepository runs,AgentToolEventRepository tools,IntegrationEventRepository integrations,OutboundTelegramMessageRepository outbound,FoodEntryRepository entries,ApiKeyService keys,ObservabilityService traces){this.runs=runs;this.tools=tools;this.integrations=integrations;this.outbound=outbound;this.entries=entries;this.keys=keys;this.traces=traces;}
  @GetMapping({"","/"}) public String overview(Model model){Instant day=Instant.now().minusSeconds(86400);List<AgentRun> recent=runs.findAll();long succeeded=recent.stream().filter(r->r.getStartedAt().isAfter(day)&&r.getOutcome()==AgentRun.Outcome.SUCCEEDED).count();long failed=recent.stream().filter(r->r.getStartedAt().isAfter(day)&&r.getOutcome()!=AgentRun.Outcome.SUCCEEDED).count();model.addAttribute("runs24h",succeeded+failed);model.addAttribute("succeeded24h",succeeded);model.addAttribute("failed24h",failed);model.addAttribute("outboxPending",outbound.findAll().stream().filter(m->m.getStatus()!=OutboundTelegramMessage.Status.SENT).count());model.addAttribute("entries24h",entries.findAll().stream().filter(e->e.getEatenAt().isAfter(day)).count());return "admin/overview";}
  @GetMapping("/runs") public String runs(@RequestParam(defaultValue="0") int page,Model model){model.addAttribute("runs",runs.findAll(PageRequest.of(Math.max(0,page),25,Sort.by(Sort.Direction.DESC,"startedAt"))));return "admin/runs";}
  @GetMapping("/runs/{id}") public String run(@PathVariable UUID id,Model model){AgentRun run=runs.findById(id).orElseThrow(()->new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.NOT_FOUND));model.addAttribute("run",run);model.addAttribute("events",tools.findByAgentRunCorrelationIdOrderBySequenceNumber(id));model.addAttribute("integrations",integrations.findByAgentRunCorrelationIdOrderByCreatedAt(id));return "admin/run";}
  @PostMapping("/runs/{id}/reveal/{type}") public String reveal(@PathVariable UUID id,@PathVariable AgentTracePayload.Type type,@RequestParam(defaultValue="") String reason,Authentication auth,Model model){String value=traces.revealPrivatePayload(id,type).orElse("Private payload unavailable: configure ADMIN_TRACE_ENCRYPTION_KEY before processing the run.");traces.audit("ADMIN",auth.getName(),"TRACE_PAYLOAD_REVEALED","AGENT_RUN",id.toString(),reason,"payloadType="+type);model.addAttribute("payload",value);model.addAttribute("payloadType",type);return run(id,model);}
  @GetMapping("/outbox") public String outbox(Model model){model.addAttribute("messages",outbound.findAll(PageRequest.of(0,100,Sort.by(Sort.Direction.DESC,"id"))));return "admin/outbox";}
  @GetMapping("/api-keys") public String apiKeys(Model model){model.addAttribute("keys",keys.list());model.addAttribute("scopes",ApiKeyScope.values());return "admin/api-keys";}
  @PostMapping("/api-keys") public String createKey(@RequestParam String name,@RequestParam(required=false) Set<ApiKeyScope> scopes,@RequestParam(required=false) String expiresAt,Authentication auth,Model model){java.time.Instant expiry=expiresAt==null||expiresAt.isBlank()?null:java.time.OffsetDateTime.parse(expiresAt).toInstant();IssuedApiKey issued=keys.issue(name,scopes==null?Set.of():scopes,expiry,auth.getName());model.addAttribute("issued",issued);model.addAttribute("keys",keys.list());model.addAttribute("scopes",ApiKeyScope.values());return "admin/api-keys";}
  @PostMapping("/api-keys/{id}/revoke") public String revoke(@PathVariable long id,Authentication auth){keys.revoke(id,auth.getName());return "redirect:/admin/api-keys";}
}
