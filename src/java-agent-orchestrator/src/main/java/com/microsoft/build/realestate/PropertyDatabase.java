package com.microsoft.build.realestate;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.net.URISyntaxException;
import java.net.URL;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.logging.Logger;
import java.util.stream.Stream;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.context.Initialized;
import jakarta.enterprise.event.Observes;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import jakarta.json.bind.Jsonb;
import jakarta.json.bind.JsonbBuilder;
import jakarta.transaction.Transactional;

@ApplicationScoped
public class PropertyDatabase {

    private static final Logger LOGGER = Logger.getLogger(PropertyDatabase.class.getName());
    private static final String PROPERTIES_RESOURCE_PATH = "data/properties";

    @Inject
    PropertyRepository repository;

    @Inject
    Instance<PropertySearchVerification> propertySearchVerification;

    @Transactional
    void seedDatabase(@Observes @Initialized(ApplicationScoped.class) Object ignored) {
        if (!search(null, null, 0, Integer.MAX_VALUE, 0, 0).isEmpty()) {
            LOGGER.info("PropertyDatabase: skipping seed because property data already exists");
            propertySearchVerification.get().logVerification();
            return;
        }

        var resourceNames = listSeedResourceNames();
        if (resourceNames.isEmpty()) {
            LOGGER.warning("PropertyDatabase: no seed data found in " + PROPERTIES_RESOURCE_PATH);
            return;
        }

        try (Jsonb jsonb = JsonbBuilder.create()) {
            for (String resourceName : resourceNames) {
                try (InputStream inputStream = currentClassLoader().getResourceAsStream(PROPERTIES_RESOURCE_PATH + "/" + resourceName)) {
                    if (inputStream == null) {
                        throw new IllegalStateException("Missing property seed resource " + resourceName);
                    }
                    SeedProperty seedProperty = jsonb.fromJson(inputStream, SeedProperty.class);
                    repository.save(toProperty(seedProperty));
                }
            }
        } catch (Exception e) {
            throw new IllegalStateException("Failed to seed property data", e);
        }

        LOGGER.info("PropertyDatabase: seeded " + resourceNames.size() + " properties from " + PROPERTIES_RESOURCE_PATH);
        propertySearchVerification.get().logVerification();
    }

    public List<Property> search(
            String type,
            String city,
            int minPrice,
            int maxPrice,
            int minBedrooms,
            int minBathrooms) {
        return repository.search(
                normalize(type),
                normalize(city),
                minPrice,
                maxPrice,
                minBedrooms,
                minBathrooms);
    }

    private List<String> listSeedResourceNames() {
        URL directoryUrl = currentClassLoader().getResource(PROPERTIES_RESOURCE_PATH);

        if (directoryUrl != null && "file".equals(directoryUrl.getProtocol())) {
            try (Stream<Path> paths = Files.list(Path.of(directoryUrl.toURI()))) {
                return paths
                        .filter(Files::isRegularFile)
                        .map(Path::getFileName)
                        .map(Path::toString)
                        .filter(name -> name.endsWith(".json"))
                        .sorted(Comparator.naturalOrder())
                        .toList();
            } catch (IOException e) {
                throw new UncheckedIOException("Unable to read property seed directory", e);
            } catch (URISyntaxException e) {
                throw new IllegalStateException("Invalid property seed directory URI", e);
            }
        }

        // Fallback for packaged resources (WAR/JAR) or when the directory entry is not
        // resolvable: probe numbered corpus files directly via ClassLoader.
        List<String> names = new java.util.ArrayList<>();
        for (int i = 1; ; i++) {
            String name = String.format("%05d.json", i);
            if (currentClassLoader().getResource(PROPERTIES_RESOURCE_PATH + "/" + name) == null) {
                break;
            }
            names.add(name);
        }
        return names;
    }

    private ClassLoader currentClassLoader() {
        return Thread.currentThread().getContextClassLoader();
    }

    private Property toProperty(SeedProperty seedProperty) {
        Property property = new Property();
        property.setType(normalizeType(seedProperty.type));
        property.setPrice(seedProperty.price);
        property.setBedrooms(seedProperty.bedrooms);
        property.setBathrooms(seedProperty.bathrooms);
        property.setSquareFeet(seedProperty.squareFootage);
        property.setDescription(sanitize(seedProperty.fullDescription));
        property.setAddress(toAddress(seedProperty.address));
        return property;
    }

    private Address toAddress(SeedAddress seedAddress) {
        Address address = new Address();
        address.setStreet(sanitize(seedAddress.street));
        address.setCity(sanitize(seedAddress.city));
        address.setState(sanitize(seedAddress.province));
        address.setZipCode(sanitize(seedAddress.postalCode));
        return address;
    }

    private String normalize(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private String sanitize(String value) {
        if (value == null) {
            return null;
        }
        return value
                .replace('’', '\'')
                .replace('—', '-');
    }

    private String normalizeType(String type) {
        String sanitizedType = sanitize(type);
        if (sanitizedType == null) {
            return null;
        }

        return switch (sanitizedType.toLowerCase(Locale.ROOT)) {
            case "detached", "semi-detached", "townhouse", "bungalow", "duplex" -> "House";
            case "loft" -> "Apartment";
            default -> sanitizedType;
        };
    }

    public static class SeedProperty {
        public String type;
        public int price;
        public int bedrooms;
        public int bathrooms;
        public int squareFootage;
        public String fullDescription;
        public SeedAddress address;
    }

    public static class SeedAddress {
        public String street;
        public String city;
        public String province;
        public String postalCode;
    }
}
