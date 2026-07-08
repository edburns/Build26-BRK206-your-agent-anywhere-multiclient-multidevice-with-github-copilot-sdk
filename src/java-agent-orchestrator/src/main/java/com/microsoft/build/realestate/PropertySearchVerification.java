package com.microsoft.build.realestate;

import java.util.logging.Logger;

import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@ApplicationScoped
public class PropertySearchVerification {

    private static final Logger LOGGER = Logger.getLogger(PropertySearchVerification.class.getName());

    @Inject
    PropertyDatabase propertyDatabase;

    @PostConstruct
    void verifySearch() {
        logVerification();
    }

    public void logVerification() {
        var results = propertyDatabase.search("House", null, 0, Integer.MAX_VALUE, 0, 0);
        LOGGER.info("PropertySearchVerification: House search returned " + results.size() + " properties");
    }
}
