package com.microsoft.build.realestate;

import com.github.copilot.tool.annotation.CopilotTool;
import com.github.copilot.tool.annotation.CopilotToolParam;
import com.microsoft.build.realestate.data.PropertyRepository;
import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import java.util.List;
import java.util.Locale;
import java.util.logging.Logger;

/**
 * CDI bean that manages the real-estate property database.
 * Seeds the database with sample listings on startup.
 * Exposes a searchProperties tool for the Copilot SDK agents.
 */
@ApplicationScoped
public class PropertyDatabase {

    private static final Logger LOG = Logger.getLogger(PropertyDatabase.class.getName());

    @Inject
    private PropertyRepository repository;

    @PostConstruct
    public void seedDatabase() {
        doSeedDatabase();
    }

    @Transactional
    public void doSeedDatabase() {
        long count = repository.findAll().count();
        if (count > 0) {
            LOG.info("Property database already seeded with " + count + " properties.");
            return;
        }
        LOG.info("Seeding property database...");
        repository.save(new Property("Semi-detached house", "London", "Hackney",        3, 750_000, "Victorian terrace, south-facing garden, 5 min walk to Hackney Central station."));
        repository.save(new Property("Flat",                "London", "Canary Wharf",   2, 520_000, "Modern apartment with river views, concierge service, private gym."));
        repository.save(new Property("Detached house",      "Bristol", "Clifton",       4, 650_000, "Period property with original features, large garden, near Clifton Downs."));
        repository.save(new Property("Terraced house",      "Manchester", "Didsbury",   3, 420_000, "Renovated Victorian terrace, open-plan kitchen, good schools nearby."));
        repository.save(new Property("Flat",                "Edinburgh", "New Town",    2, 380_000, "Georgian conversion, high ceilings, communal garden, central location."));
        repository.save(new Property("Bungalow",            "Brighton", "Hove",         2, 480_000, "Single-storey, fully accessible, large decked garden, quiet street."));
        repository.save(new Property("Detached house",      "London", "Wimbledon",      5, 1_200_000, "Spacious family home, double garage, large south-facing garden."));
        repository.save(new Property("Flat",                "Leeds", "City Centre",     1, 180_000, "High-spec studio, roof terrace, city views, ideal for professionals."));
        repository.save(new Property("Semi-detached house", "Birmingham", "Moseley",    4, 390_000, "Extended family home, two bathrooms, near excellent schools."));
        repository.save(new Property("Cottage",             "Oxford", "Headington",     3, 560_000, "Charming stone cottage, private parking, walking distance to JR Hospital."));
        LOG.info("Seeded 10 properties.");
    }

    /**
     * Searches the property database using the given criteria.
     * String parameters may be null or empty to skip that filter.
     * Numeric parameters use 0 as a sentinel meaning "no filter".
     *
     * @param type        Property type substring (e.g. "flat", "house"); null or blank = no filter
     * @param city        City substring (e.g. "London", "Bristol"); null or blank = no filter
     * @param minBedrooms Minimum number of bedrooms; 0 = no minimum
     * @param maxPriceGbp Maximum price in GBP; 0 = no maximum
     * @return Matching properties, up to 10 results
     */
    @CopilotTool(value = "Searches the real estate listings database. Returns up to 10 matching properties.",
                 name = "search_properties")
    @Transactional
    public List<Property> searchProperties(
            @CopilotToolParam("Property type substring (e.g. 'flat', 'house', 'bungalow')") String type,
            @CopilotToolParam("City substring (e.g. 'London', 'Bristol')") String city,
            @CopilotToolParam("Minimum number of bedrooms (0 for no minimum)") int minBedrooms,
            @CopilotToolParam("Maximum price in GBP (0 for no maximum)") double maxPriceGbp) {

        List<Property> results = repository.findAll().toList();

        if (type != null && !type.isBlank()) {
            String ltype = type.toLowerCase(Locale.ROOT);
            results = results.stream()
                .filter(p -> p.getType().toLowerCase(Locale.ROOT).contains(ltype))
                .toList();
        }
        if (city != null && !city.isBlank()) {
            String lcity = city.toLowerCase(Locale.ROOT);
            results = results.stream()
                .filter(p -> p.getCity().toLowerCase(Locale.ROOT).contains(lcity))
                .toList();
        }
        if (minBedrooms > 0) {
            results = results.stream()
                .filter(p -> p.getBedrooms() >= minBedrooms)
                .toList();
        }
        if (maxPriceGbp > 0) {
            results = results.stream()
                .filter(p -> p.getPriceGbp() <= maxPriceGbp)
                .toList();
        }
        return results.stream().limit(10).toList();
    }
}
