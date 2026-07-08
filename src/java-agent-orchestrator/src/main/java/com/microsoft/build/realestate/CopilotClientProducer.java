package com.microsoft.build.realestate;

import java.nio.file.Path;
import java.util.logging.Logger;

import com.github.copilot.CopilotClient;
import com.github.copilot.CopilotClientMode;
import com.github.copilot.CopilotClientOptions;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Disposes;
import jakarta.enterprise.inject.Produces;

@ApplicationScoped
public class CopilotClientProducer {

    private static final Logger LOGGER = Logger.getLogger(CopilotClientProducer.class.getName());

    @Produces
    @ApplicationScoped
    CopilotClient createClient() {
        LOGGER.info("CopilotClientProducer: creating CopilotClient in EMPTY mode");
        return new CopilotClient(
            new CopilotClientOptions()
                .setMode(CopilotClientMode.EMPTY)
                .setCopilotHome(Path.of(System.getProperty("user.home"), ".copilot").toString())
        );
    }

    void destroyClient(@Disposes CopilotClient client) {
        LOGGER.info("CopilotClientProducer: closing CopilotClient");
        client.close();
    }
}
