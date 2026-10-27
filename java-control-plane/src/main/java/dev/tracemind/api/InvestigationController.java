package dev.tracemind.api;

import org.springframework.web.bind.annotation.*;
import java.util.Set;

/** Spring REST orchestration surface for local TraceMind demo.
 *  Connects Java clients to the running Python investigation engine.
 *  Not an authenticated production control plane.
 */
@RestController
@RequestMapping("/api/v1")
public class InvestigationController {
    private static final Set<String> SCENARIOS = Set.of("db_pool_exhaustion", "payment_timeout");
    private final EngineClient engine;

    public InvestigationController(EngineClient engine) { this.engine = engine; }

    @GetMapping("/health")
    public Object health() { return engine.get("/api/health"); }

    @GetMapping("/overview")
    public Object overview() { return engine.get("/api/overview"); }

    @GetMapping("/services")
    public Object services() { return engine.get("/api/services"); }

    @GetMapping("/incidents")
    public Object incidents() { return engine.get("/api/incidents"); }

    @GetMapping("/incidents/{id}")
    public Object incident(@PathVariable String id) { return engine.get("/api/incidents/" + safeId(id)); }

    @PostMapping("/checkout")
    public Object checkout() { return engine.post("/api/demo/checkout"); }

    @PostMapping("/faults/{scenario}")
    public Object inject(@PathVariable String scenario) {
        if (!SCENARIOS.contains(scenario)) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.BAD_REQUEST, "Unknown fault scenario");
        }
        return engine.post("/api/demo/faults/" + scenario);
    }

    @PostMapping("/incidents/{id}/investigate")
    public Object investigate(@PathVariable String id) { return engine.post("/api/incidents/" + safeId(id) + "/investigate"); }

    @PostMapping("/incidents/{id}/fix")
    public Object propose(@PathVariable String id) { return engine.post("/api/incidents/" + safeId(id) + "/fix"); }

    @PostMapping("/incidents/{id}/approve")
    public Object approve(@PathVariable String id) { return engine.post("/api/incidents/" + safeId(id) + "/approve"); }

    @PostMapping("/incidents/{id}/verify")
    public Object verify(@PathVariable String id) { return engine.post("/api/incidents/" + safeId(id) + "/verify"); }

    private String safeId(String id) {
        if (!id.matches("INC-[A-F0-9]{8}")) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.BAD_REQUEST, "Invalid incident identifier");
        }
        return id;
    }
}
