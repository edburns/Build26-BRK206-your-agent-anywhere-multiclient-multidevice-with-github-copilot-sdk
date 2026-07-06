package com.microsoft.build.spike;

import java.util.List;

import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.inject.Named;
import jakarta.transaction.Transactional;

@Named
@ApplicationScoped
public class PropertyBean {

    @Inject
    private PropertyRepository repo;

    private List<Property> results;
    private String message;

    @PostConstruct
    @Transactional
    public void init() {
        // Seed sample data on startup
        repo.save(new Property("123 Main St", "Seattle", 3, 750000));
        repo.save(new Property("456 Oak Ave", "Seattle", 4, 950000));
        repo.save(new Property("789 Pine Rd", "Portland", 2, 450000));
        repo.save(new Property("321 Elm Blvd", "Portland", 5, 1200000));
        repo.save(new Property("654 Cedar Ln", "Seattle", 3, 680000));
        message = "Seed data loaded (5 properties).";
        results = List.of();
    }

    @Transactional
    public void searchSeattle() {
        results = repo.findByCity("Seattle");
        message = "SPIKE CONFIRMED: Jakarta Data @Repository with H2 in-memory works on OpenLiberty 26.0.0.5. "
                + "Found " + results.size() + " properties in Seattle.";
    }

    @Transactional
    public void searchLargeHomes() {
        results = repo.findLargeHomes(4);
        message = "SPIKE CONFIRMED: Jakarta Data @Query with H2 in-memory works. "
                + "Found " + results.size() + " properties with 4+ bedrooms.";
    }

    public List<Property> getResults() { return results; }
    public String getMessage() { return message; }
}
