package com.microsoft.build.realestate.data;

import com.microsoft.build.realestate.Property;
import jakarta.data.repository.BasicRepository;
import jakarta.data.repository.Repository;

/**
 * Jakarta Data repository for Property entities.
 * Extends BasicRepository to inherit save() and findAll() (as Stream).
 */
@Repository
public interface PropertyRepository extends BasicRepository<Property, Long> {
}
