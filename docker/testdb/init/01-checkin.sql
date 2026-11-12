-- Läuft nur beim ersten Start (leeres Volume)
CREATE DATABASE IF NOT EXISTS checkin CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON checkin.* TO 'ski'@'%';
FLUSH PRIVILEGES;
