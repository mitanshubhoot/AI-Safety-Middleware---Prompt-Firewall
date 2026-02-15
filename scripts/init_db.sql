"""Initialize SQL database script for first-time setup."""
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create a default user (change password in production)
-- This is just for initial development setup
