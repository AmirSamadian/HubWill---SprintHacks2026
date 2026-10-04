-- Reference data only; no fabricated transactions or customer identities.
INSERT INTO source (name)
VALUES ('Amazon'), ('eBay'), ('ShopGoodwill')
ON CONFLICT (name) DO NOTHING;

-- Flat starting taxonomy from the ShopGoodwill fixture's Category Name column.
-- The input does not define a hierarchy. Category names are not identity keys.
-- This migration runs once; do not infer UNIQUE(name) from these seed values.
INSERT INTO category (name)
VALUES
    ('Art'),
    ('Books'),
    ('Clothing'),
    ('Collectibles'),
    ('Electronics'),
    ('Home'),
    ('Jewelry & Gemstones');
