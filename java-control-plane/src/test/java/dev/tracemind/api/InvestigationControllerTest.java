package dev.tracemind.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

class InvestigationControllerTest {
    @Test
    void invalidIncidentIdentifierRejectedWithoutCallingEngine() {
        InvestigationController controller = new InvestigationController(null);
        ResponseStatusException ex = assertThrows(ResponseStatusException.class,
                () -> controller.incident("../etc/passwd"));
        assertEquals(400, ex.getStatusCode().value());
    }
}
