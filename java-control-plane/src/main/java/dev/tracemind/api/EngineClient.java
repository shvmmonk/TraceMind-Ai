package dev.tracemind.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

/** Client adapter for the Python investigation and telemetry engine. */
@Component
public class EngineClient {
    private final RestClient client;

    public EngineClient(@Value("${tracemind.engine.base-url}") String baseUrl) {
        this.client = RestClient.builder().baseUrl(baseUrl).build();
    }

    public Object get(String path) { return exchange(HttpMethod.GET, path); }
    public Object post(String path) { return exchange(HttpMethod.POST, path); }

    private Object exchange(HttpMethod method, String path) {
        try {
            ResponseEntity<Object> response = client.method(method)
                    .uri(path)
                    .retrieve()
                    .toEntity(Object.class);
            return response.getBody();
        } catch (HttpStatusCodeException ex) {
            throw new ResponseStatusException(ex.getStatusCode(), "Investigation engine rejected the request", ex);
        } catch (org.springframework.web.client.ResourceAccessException ex) {
            throw new ResponseStatusException(org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE,
                    "Investigation engine is unreachable", ex);
        }
    }
}
