package io.github.foodjournal.web;
import org.springframework.http.ResponseEntity; import org.springframework.web.bind.annotation.*;
@RestController class HealthController { @GetMapping("/health") ResponseEntity<String> health(){return ResponseEntity.ok("ok");} }
