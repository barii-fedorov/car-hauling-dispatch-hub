-- ==============================================================================
-- DRIVER CASES & DISPUTE RESOLUTION SCHEMA (PostgreSQL)
-- Tracks all driver interactions, recovered money, equipment types, and facilities
-- ==============================================================================

CREATE TABLE IF NOT EXISTS driver_cases (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    driver_id VARCHAR(100),              -- GDPR-compliant anonymized hash (e.g. 'drv_8f9a2b')
    driver_setup VARCHAR(50) NOT NULL,   -- 'Stinger 9-car', 'High-Mount 7-car', 'Pickup + 3-4 car Wedge'
    category VARCHAR(50) NOT NULL,       -- 'Detention', 'Inop / Winch', 'TONU / Dry Run', 'Overhang / DOT Dispute', etc.
    facility VARCHAR(100),               -- 'Copart', 'IAAI', 'Manheim', 'Private Dealer', 'POV'
    facility_location VARCHAR(100),      -- e.g. 'Atlanta, GA', 'Dallas, TX'
    state VARCHAR(10),                   -- 2-letter US state code
    broker_name VARCHAR(150),            -- Freight broker name
    broker_mc VARCHAR(30),               -- Broker MC number (e.g. 'MC-582910')
    claimed_amount NUMERIC(10,2) DEFAULT 0.00,
    recovered_amount NUMERIC(10,2) DEFAULT 0.00,
    status VARCHAR(30) DEFAULT 'Resolved',
    time_to_resolve_minutes INT DEFAULT 30,
    sanitized_case_summary TEXT,         -- Fully anonymized description (GDPR compliant)
    resolution_strategy TEXT             -- Playbook / strategy used (e.g. 'BMC-84 bond notice', 'Gate slip timestamp')
);

CREATE INDEX IF NOT EXISTS idx_driver_cases_created ON driver_cases(created_at);
CREATE INDEX IF NOT EXISTS idx_driver_cases_category ON driver_cases(category);
CREATE INDEX IF NOT EXISTS idx_driver_cases_status ON driver_cases(status);
CREATE INDEX IF NOT EXISTS idx_driver_cases_setup ON driver_cases(driver_setup);
CREATE INDEX IF NOT EXISTS idx_driver_cases_facility ON driver_cases(facility);
