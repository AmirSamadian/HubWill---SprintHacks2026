#!/usr/bin/env python3
"""Generate synthetic multi-year historical data for goodwill_db.

Writes one CSV per table in docs/DATABASE_SPEC.md into this folder. Rows refer
to each other by natural keys (source name, marketplace IDs, SKU, batch file
name), never by internal numeric IDs, so load_historical.sql can insert them
into any migrated database without colliding with existing rows.

Usage (Python 3.9+, standard library only):
    python3 test-data/historical/generate.py

Output is deterministic: the same SEED always produces the same files.
"""

import csv
import math
import random
import string
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SEED = 20261004
OUT_DIR = Path(__file__).resolve().parent

# Goodwill Michiana operates in St. Joseph County, Indiana (Eastern time).
TZ = ZoneInfo("America/Indiana/Indianapolis")
START = date(2023, 11, 4)  # first Saturday of history; weekly batches run Sat–Fri
END = date(2026, 10, 2)  # last Friday with data
CUTOFF = datetime.combine(END + timedelta(days=1), time(0), TZ)  # data snapshot instant

SGW, EBAY, AMZ = "ShopGoodwill", "eBay", "Amazon"

# Catalog prices are typical asking prices; realized sale prices land lower, and
# no single donated item sells for more than a few times its typical price.
PRICE_SCALE = 0.7
MAX_VALUE_MULTIPLE = 3.5
SOURCES = [AMZ, EBAY, SGW]

rng = random.Random(SEED)


# ---------------------------------------------------------------------------
# Catalog: category hierarchy, item names, typical prices, channel affinity
# ---------------------------------------------------------------------------

# (root, child): spread of prices, share of intake, channel weights, shipping class,
# and items as (name, typical price). Shipping classes: small, medium, large, and
# freight (furniture: ShopGoodwill local pickup only).
CATALOG = {
    ("Home", "Furniture"): dict(sigma=0.45, share=3.0, channels={SGW: 1.0}, ship="freight", items=[
        ("Mid-Century Walnut Dresser", 260), ("Leather 3-Seat Sofa", 220), ("Oak Dining Table with 4 Chairs", 240),
        ("Upholstered Wingback Armchair", 120), ("Solid Wood Bookcase", 95), ("Vintage Cedar Chest", 140),
        ("Glass-Top Coffee Table", 70), ("Rattan Accent Chair", 85), ("Antique Oak Rocking Chair", 110),
        ("Pottery Barn Sectional Couch", 380), ("Ethan Allen Nightstand", 130), ("Bistro Table Set", 90)]),
    ("Home", "Lamps & Lighting"): dict(sigma=0.5, share=2.5, channels={SGW: 0.6, EBAY: 0.4}, ship="large", items=[
        ("Brass Table Lamp", 35), ("Tiffany-Style Stained Glass Lamp", 75), ("Mid-Century Floor Lamp", 90),
        ("Crystal Chandelier", 120), ("Ceramic Ginger Jar Lamp", 40), ("Industrial Desk Lamp", 30),
        ("Hurricane Oil Lamp", 28), ("Arc Floor Lamp", 65)]),
    ("Home", "Kitchen & Dining"): dict(sigma=0.5, share=6.0, channels={SGW: 0.5, EBAY: 0.2, AMZ: 0.3}, ship="medium", items=[
        ("Pyrex Butterprint Mixing Bowl Set of 4", 95), ("Le Creuset Dutch Oven 5.5qt", 110), ("Corningware Casserole Set", 35),
        ("KitchenAid Artisan Stand Mixer", 150), ("Fiestaware Dinner Plates Set of 4", 40), ("Lodge Cast Iron Skillet 12in", 30),
        ("Fire-King Jadeite Mug Set", 55), ("Cuisinart Food Processor", 45), ("Waterford Crystal Wine Glasses Pair", 60),
        ("Instant Pot Duo 6qt", 40), ("Pfaltzgraff Dinnerware Set", 45), ("Vintage Pyrex Casserole with Lid", 28)]),
    ("Home", "Home Decor"): dict(sigma=0.55, share=5.0, channels={SGW: 0.7, EBAY: 0.3}, ship="medium", items=[
        ("Brass Candlestick Pair", 25), ("Vintage Wall Mirror", 45), ("Lenox Porcelain Vase", 35),
        ("Ceramic Planter Set", 22), ("Howard Miller Mantel Clock", 55), ("Longaberger Basket", 20),
        ("Hand-Carved Wooden Duck Decoy", 40), ("Vintage Brass Bookends", 30)]),
    ("Home", "Rugs & Textiles"): dict(sigma=0.55, share=2.0, channels={SGW: 0.7, EBAY: 0.3}, ship="large", items=[
        ("Persian-Style Wool Area Rug 5x8", 90), ("Handmade Quilt Queen", 70), ("Pendleton Wool Blanket", 75),
        ("Vintage Chenille Bedspread", 45), ("Hooked Wool Rug 3x5", 40), ("Linen Tablecloth Set", 25)]),

    ("Clothing", "Men's Clothing"): dict(sigma=0.45, share=4.0, channels={EBAY: 0.6, SGW: 0.4}, ship="small", sizes="apparel", items=[
        ("Carhartt Duck Work Jacket", 55), ("Patagonia Fleece Pullover", 45), ("Levi's 501 Jeans", 28),
        ("Brooks Brothers Dress Shirt", 22), ("Pendleton Wool Flannel Shirt", 35), ("Columbia Rain Jacket", 30),
        ("Ralph Lauren Polo Shirt Lot of 3", 32), ("The North Face Puffer Jacket", 75)]),
    ("Clothing", "Women's Clothing"): dict(sigma=0.45, share=5.0, channels={EBAY: 0.6, SGW: 0.4}, ship="small", sizes="apparel", items=[
        ("Eileen Fisher Linen Tunic", 30), ("Free People Maxi Dress", 32), ("Lululemon Align Leggings", 40),
        ("J.Crew Wool Coat", 50), ("Anthropologie Midi Skirt", 26), ("Talbots Cashmere Cardigan", 28),
        ("Madewell Denim Jacket", 35), ("Banana Republic Silk Blouse", 22)]),
    ("Clothing", "Shoes"): dict(sigma=0.45, share=3.0, channels={EBAY: 0.7, SGW: 0.3}, ship="medium", sizes="shoes", items=[
        ("Dr. Martens 1460 Boots", 60), ("Nike Air Max 90 Sneakers", 45), ("Birkenstock Arizona Sandals", 40),
        ("Frye Harness Boots", 80), ("Allen Edmonds Oxford Shoes", 70), ("Converse Chuck Taylor Hi", 25),
        ("Red Wing Iron Ranger Boots", 120), ("Ugg Classic Short Boots", 45)]),
    ("Clothing", "Handbags & Accessories"): dict(sigma=0.6, share=3.0, channels={EBAY: 0.5, SGW: 0.5}, ship="medium", items=[
        ("Coach Leather Shoulder Bag", 65), ("Michael Kors Tote", 45), ("Dooney & Bourke Satchel", 60),
        ("Kate Spade Crossbody Bag", 50), ("Vera Bradley Duffel Bag", 30), ("Louis Vuitton Speedy 30", 520),
        ("Fossil Leather Wallet", 22), ("Ray-Ban Wayfarer Sunglasses", 55)]),
    ("Clothing", "Vintage Apparel"): dict(sigma=0.55, share=2.0, channels={EBAY: 0.6, SGW: 0.4}, ship="small", sizes="apparel", items=[
        ("Vintage 1990s Band T-Shirt", 45), ("Vintage Varsity Letterman Jacket", 60), ("Vintage Levi's Trucker Jacket", 65),
        ("1970s Polyester Disco Shirt", 30), ("Vintage Starter Pullover Jacket", 55), ("Vintage Harley-Davidson Tee", 40)]),

    ("Electronics", "Computers & Laptops"): dict(sigma=0.45, share=2.0, channels={EBAY: 0.6, SGW: 0.3, AMZ: 0.1}, ship="medium", tested=True, items=[
        ("Apple MacBook Air M1 13in", 420), ("Dell Latitude 7420 Laptop", 260), ("Lenovo ThinkPad T480", 190),
        ("Apple iMac 21.5in", 230), ("HP Chromebook 14", 85), ("Microsoft Surface Pro 7", 280)]),
    ("Electronics", "Audio & Headphones"): dict(sigma=0.55, share=3.0, channels={EBAY: 0.5, SGW: 0.3, AMZ: 0.2}, ship="medium", tested=True, items=[
        ("Bose QuietComfort 35 II Headphones", 95), ("Sony WH-1000XM4 Headphones", 140), ("Technics SL-1200 Turntable", 420),
        ("Beats Studio3 Wireless Headphones", 75), ("JBL Flip 5 Bluetooth Speaker", 45), ("Pioneer Stereo Receiver", 80),
        ("Apple AirPods Pro", 90), ("Marantz Vintage Receiver", 260)]),
    ("Electronics", "Phones & Tablets"): dict(sigma=0.45, share=2.0, channels={EBAY: 0.7, SGW: 0.3}, ship="small", tested=True, items=[
        ("Apple iPad 9th Gen 64GB", 170), ("Apple iPhone 12 128GB Unlocked", 230), ("Samsung Galaxy Tab A", 70),
        ("Kindle Paperwhite", 45), ("Apple iPod Classic 160GB", 160), ("Samsung Galaxy S21 Unlocked", 180)]),

    ("Jewelry & Gemstones", "Fine Jewelry"): dict(sigma=0.6, share=3.0, channels={SGW: 0.8, EBAY: 0.2}, ship="small", grams=True, items=[
        ("14K Yellow Gold Rope Chain 20in", 260), ("10K Gold Class Ring", 220), ("14K White Gold Diamond Stud Earrings", 240),
        ("18K Gold Bangle Bracelet", 480), ("14K Gold Cuban Link Bracelet", 350), ("10K Gold Cameo Pendant", 130)]),
    ("Jewelry & Gemstones", "Sterling Silver"): dict(sigma=0.55, share=3.0, channels={SGW: 0.7, EBAY: 0.3}, ship="small", items=[
        ("Sterling Silver Navajo Turquoise Ring", 70), ("Sterling Silver Charm Bracelet", 45), ("James Avery Sterling Charm", 35),
        ("Sterling Silver Cuff Bracelet", 50), ("Sterling Silver 925 Chain Lot", 60)]),
    ("Jewelry & Gemstones", "Watches"): dict(sigma=0.6, share=2.0, channels={SGW: 0.6, EBAY: 0.4}, ship="small", items=[
        ("Seiko 5 Automatic Watch", 85), ("Citizen Eco-Drive Watch", 70), ("Timex Weekender Watch", 25),
        ("Fossil Chronograph Watch", 40), ("Omega Seamaster Automatic Watch", 1450), ("Bulova Marine Star Watch", 90),
        ("Casio G-Shock Watch", 45)]),
    ("Jewelry & Gemstones", "Costume Jewelry"): dict(sigma=0.5, share=4.0, channels={SGW: 0.8, EBAY: 0.2}, ship="small", items=[
        ("Vintage Costume Jewelry Lot 1 lb", 30), ("Monet Gold-Tone Necklace", 18), ("Trifari Brooch", 25),
        ("Napier Clip Earrings Lot", 22), ("Rhinestone Brooch Lot", 28)]),

    ("Collectibles", "Trading Cards"): dict(sigma=0.8, share=3.0, channels={EBAY: 0.8, SGW: 0.2}, ship="small", items=[
        ("Pokemon Card Lot 100+", 40), ("1990s Baseball Card Lot", 20), ("Magic the Gathering Card Lot", 35),
        ("Sports Card Binder Collection", 45), ("Yu-Gi-Oh! Card Lot", 25), ("Pokemon Holo Rare Card", 30)]),
    ("Collectibles", "Vinyl Records"): dict(sigma=0.5, share=3.0, channels={EBAY: 0.5, SGW: 0.3, AMZ: 0.2}, ship="medium", media=True, items=[
        ("Fleetwood Mac Rumours LP", 28), ("Beatles Abbey Road LP", 35), ("Vinyl Record Lot 25 LPs", 45),
        ("Pink Floyd Dark Side of the Moon LP", 32), ("Classic Rock LP Lot", 40), ("Jazz LP Lot", 38)]),
    ("Collectibles", "Figurines"): dict(sigma=0.55, share=2.0, channels={EBAY: 0.5, SGW: 0.3, AMZ: 0.2}, ship="small", items=[
        ("Funko Pop Star Wars Lot of 6", 45), ("Precious Moments Figurine", 18), ("Hummel Figurine", 30),
        ("Lladro Porcelain Figurine", 75), ("Department 56 Village Piece", 35)]),
    ("Collectibles", "Coins & Currency"): dict(sigma=0.6, share=2.0, channels={SGW: 0.8, EBAY: 0.2}, ship="small", items=[
        ("Morgan Silver Dollar", 48), ("Wheat Penny Lot", 18), ("US Mint Silver Proof Set", 55),
        ("Kennedy Half Dollar Lot", 30), ("State Quarters Collection Book", 25), ("Foreign Coin Lot 1 lb", 22)]),

    ("Books", "Hardcover Fiction"): dict(sigma=0.45, share=4.0, channels={AMZ: 0.8, EBAY: 0.2}, ship="medium", media=True, items=[
        ("Stephen King Hardcover", 14), ("Harry Potter Hardcover Set Books 1-7", 85), ("John Grisham Hardcover Lot", 18),
        ("Agatha Christie Hardcover", 12), ("Tolkien Lord of the Rings Hardcover", 30), ("Danielle Steel Hardcover Lot", 12)]),
    ("Books", "Textbooks"): dict(sigma=0.5, share=3.0, channels={AMZ: 0.9, EBAY: 0.1}, ship="medium", media=True, items=[
        ("Campbell Biology 12th Edition", 55), ("Calculus Early Transcendentals", 45), ("Organic Chemistry Textbook", 40),
        ("Principles of Economics Mankiw", 35), ("Fundamentals of Nursing Textbook", 50), ("Psychology Textbook", 28)]),
    ("Books", "Children's Books"): dict(sigma=0.45, share=2.0, channels={AMZ: 0.7, SGW: 0.3}, ship="medium", media=True, items=[
        ("Dr. Seuss Book Lot", 18), ("Little Golden Books Lot", 15), ("Magic Tree House Book Set", 20),
        ("Berenstain Bears Book Lot", 14), ("Junie B. Jones Book Set", 16)]),
    ("Books", "Vintage & Rare Books"): dict(sigma=0.7, share=1.0, channels={SGW: 0.5, EBAY: 0.5}, ship="medium", items=[
        ("First Edition Hardcover Novel", 60), ("Antique Leather-Bound Book", 45), ("Vintage 1950s Cookbook", 22),
        ("Signed First Edition Novel", 95), ("Antique Family Bible", 55)]),

    ("Art", "Paintings"): dict(sigma=0.7, share=2.0, channels={SGW: 1.0}, ship="large", items=[
        ("Original Oil Painting Landscape", 85), ("Signed Watercolor Painting", 55), ("Framed Acrylic Abstract Painting", 45),
        ("Vintage Oil Portrait Painting", 95), ("Original Seascape Oil Painting", 75)]),
    ("Art", "Prints & Posters"): dict(sigma=0.6, share=1.5, channels={SGW: 0.7, EBAY: 0.3}, ship="large", items=[
        ("Framed Art Print", 25), ("Signed Limited Edition Lithograph", 70), ("Vintage Movie Poster", 40),
        ("Thomas Kinkade Framed Print", 45), ("Audubon Bird Print", 35)]),
    ("Art", "Pottery & Glass"): dict(sigma=0.6, share=2.0, channels={SGW: 0.7, EBAY: 0.3}, ship="medium", items=[
        ("Roseville Pottery Vase", 75), ("Fenton Art Glass Bowl", 35), ("Depression Glass Lot", 30),
        ("McCoy Pottery Planter", 28), ("Murano Glass Paperweight", 40), ("Blenko Glass Vase", 45)]),

    ("Toys & Games", "LEGO"): dict(sigma=0.5, share=2.0, channels={EBAY: 0.4, AMZ: 0.4, SGW: 0.2}, ship="medium", items=[
        ("LEGO Star Wars Set", 65), ("LEGO City Set", 30), ("LEGO Bulk Lot 5 lbs", 50),
        ("LEGO Technic Set", 70), ("LEGO Harry Potter Set", 55), ("LEGO Minifigure Lot", 40)]),
    ("Toys & Games", "Board Games"): dict(sigma=0.45, share=2.0, channels={AMZ: 0.6, EBAY: 0.2, SGW: 0.2}, ship="medium", items=[
        ("Monopoly Vintage Edition", 22), ("Settlers of Catan", 25), ("Scrabble Deluxe Edition", 28),
        ("Ticket to Ride", 26), ("Vintage Clue Board Game", 20), ("Jigsaw Puzzle Lot", 16)]),
    ("Toys & Games", "Dolls & Action Figures"): dict(sigma=0.6, share=2.0, channels={EBAY: 0.5, SGW: 0.5}, ship="small", items=[
        ("American Girl Doll", 60), ("Barbie Doll Lot", 30), ("Vintage Star Wars Action Figures", 45),
        ("Transformers G1 Figure", 40), ("Cabbage Patch Kids Doll", 22), ("Hot Wheels Lot", 25)]),

    ("Video Games", "Consoles"): dict(sigma=0.4, share=1.5, channels={EBAY: 0.6, SGW: 0.4}, ship="medium", tested=True, items=[
        ("Nintendo Switch Console", 190), ("PlayStation 4 Slim Console", 140), ("Xbox One S Console", 120),
        ("Nintendo Game Boy Color", 75), ("Nintendo 64 Console Bundle", 130), ("Nintendo Wii Console Bundle", 60),
        ("PlayStation 2 Console", 70)]),
    ("Video Games", "Games"): dict(sigma=0.55, share=4.0, channels={AMZ: 0.5, EBAY: 0.4, SGW: 0.1}, ship="small", media=True, items=[
        ("Nintendo Switch Game", 30), ("PS4 Game Lot", 35), ("Nintendo 64 Game Cartridge", 28),
        ("Game Boy Game Lot", 40), ("Xbox 360 Game Lot", 20), ("Wii Game Lot", 22), ("Super Nintendo Game", 35)]),

    ("Cameras & Photo", "Film Cameras"): dict(sigma=0.5, share=1.5, channels={EBAY: 0.6, SGW: 0.4}, ship="medium", items=[
        ("Canon AE-1 Program 35mm Film Camera", 150), ("Pentax K1000 35mm Camera", 120), ("Nikon FM2 Camera", 210),
        ("Polaroid SX-70 Land Camera", 110), ("Olympus OM-1 Camera", 95), ("Minolta X-700 Camera", 80)]),
    ("Cameras & Photo", "Digital Cameras"): dict(sigma=0.5, share=1.0, channels={EBAY: 0.7, SGW: 0.3}, ship="small", tested=True, items=[
        ("Canon PowerShot Digital Camera", 60), ("Nikon Coolpix Camera", 45), ("Sony Cyber-shot Camera", 55),
        ("Canon EOS Rebel T6 DSLR", 200), ("Fujifilm FinePix Camera", 40)]),
    ("Cameras & Photo", "Lenses"): dict(sigma=0.5, share=1.0, channels={EBAY: 0.8, SGW: 0.2}, ship="small", items=[
        ("Canon EF 50mm f/1.8 Lens", 75), ("Nikon 35mm f/1.8 Lens", 110), ("Canon EF 75-300mm Zoom Lens", 65),
        ("Pentax SMC 50mm Lens", 55), ("Sigma 18-200mm Lens", 90)]),

    ("Musical Instruments", "Guitars"): dict(sigma=0.5, share=1.0, channels={SGW: 0.6, EBAY: 0.4}, ship="large", items=[
        ("Fender Squier Stratocaster Electric Guitar", 140), ("Yamaha Acoustic Guitar", 110), ("Epiphone Les Paul Electric Guitar", 190),
        ("Ibanez Electric Guitar", 160), ("Fender Acoustic Guitar", 130), ("Martin Backpacker Guitar", 150)]),
    ("Musical Instruments", "Keyboards"): dict(sigma=0.5, share=0.7, channels={SGW: 0.7, EBAY: 0.3}, ship="large", items=[
        ("Yamaha 61-Key Digital Keyboard", 75), ("Casio Keyboard", 50), ("Roland Digital Piano", 260), ("Korg Synthesizer", 220)]),
    ("Musical Instruments", "Brass & Woodwind"): dict(sigma=0.5, share=0.7, channels={SGW: 0.6, EBAY: 0.4}, ship="large", items=[
        ("Yamaha Student Trumpet", 150), ("Selmer Clarinet", 110), ("Bundy Flute", 80),
        ("Conn Trombone", 140), ("Yamaha Alto Saxophone", 420)]),

    ("Sporting Goods", "Golf"): dict(sigma=0.55, share=1.5, channels={SGW: 0.6, EBAY: 0.4}, ship="large", items=[
        ("TaylorMade Driver", 70), ("Callaway Iron Set", 140), ("Ping Putter", 60),
        ("Golf Club Set with Bag", 110), ("Titleist Golf Balls Lot", 25), ("Odyssey Putter", 55)]),
    ("Sporting Goods", "Fitness"): dict(sigma=0.5, share=1.0, channels={SGW: 0.6, EBAY: 0.2, AMZ: 0.2}, ship="large", items=[
        ("Bowflex Adjustable Dumbbells", 160), ("Cast Iron Kettlebell 25 lb", 35), ("Yoga Mat & Block Set", 20),
        ("Resistance Band Set", 18), ("Weighted Jump Rope", 15)]),
    ("Sporting Goods", "Outdoor & Camping"): dict(sigma=0.5, share=1.5, channels={SGW: 0.5, EBAY: 0.4, AMZ: 0.1}, ship="medium", items=[
        ("Coleman 4-Person Tent", 45), ("Yeti Rambler Tumbler", 22), ("Camping Lantern", 18),
        ("The North Face Backpack", 40), ("Fishing Rod & Reel Combo", 35), ("Sleeping Bag", 30)]),
}

LEAVES = list(CATALOG)
LEAF_SHARES = [CATALOG[k]["share"] for k in LEAVES]

APPAREL_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
SHOE_SIZES = ["6", "7", "7.5", "8", "8.5", "9", "9.5", "10", "10.5", "11", "12"]

# Monthly multipliers (Jan..Dec). Donations peak after the holidays and in
# spring cleaning; buying peaks in Q4.
DONATION_SEASON = [1.15, 1.0, 1.05, 1.1, 1.1, 1.05, 1.0, 0.95, 0.95, 0.95, 0.95, 0.9]
DEMAND_SEASON = [0.92, 0.88, 0.95, 0.97, 0.98, 0.93, 0.92, 0.96, 1.0, 1.05, 1.22, 1.3]

# Combined state+local sales tax rates for buyer states (marketplace-facilitator
# collection). Weighted toward the Midwest, near Goodwill Michiana.
STATE_TAX = {
    "IN": (0.07, 9), "MI": (0.06, 8), "IL": (0.0886, 6), "OH": (0.0724, 6), "WI": (0.0543, 3), "KY": (0.06, 2),
    "NY": (0.0852, 5), "CA": (0.0882, 7), "TX": (0.082, 6), "FL": (0.0701, 5), "PA": (0.0634, 4), "GA": (0.0738, 3),
    "NC": (0.0699, 3), "WA": (0.0938, 2), "AZ": (0.0837, 2), "CO": (0.0781, 2), "MN": (0.0804, 2), "OR": (0.0, 1),
    "NJ": (0.066, 2), "MA": (0.0625, 2), "TN": (0.0955, 2), "MO": (0.0839, 2), "VA": (0.0577, 2), "DE": (0.0, 1),
}
TAX_STATES = list(STATE_TAX)
TAX_WEIGHTS = [STATE_TAX[s][1] for s in TAX_STATES]

US_CITIES = {
    "IN": [("South Bend", "46601"), ("Mishawaka", "46544"), ("Elkhart", "46514"), ("Indianapolis", "46204"), ("Fort Wayne", "46802"), ("Goshen", "46526")],
    "MI": [("Niles", "49120"), ("Kalamazoo", "49007"), ("Grand Rapids", "49503"), ("Detroit", "48226"), ("Ann Arbor", "48104")],
    "IL": [("Chicago", "60614"), ("Naperville", "60540"), ("Peoria", "61602"), ("Rockford", "61101")],
    "OH": [("Toledo", "43604"), ("Columbus", "43215"), ("Cleveland", "44113"), ("Cincinnati", "45202")],
    "WI": [("Milwaukee", "53202"), ("Madison", "53703")], "KY": [("Louisville", "40202"), ("Lexington", "40507")],
    "NY": [("Brooklyn", "11201"), ("Buffalo", "14202"), ("Rochester", "14604")],
    "CA": [("Los Angeles", "90012"), ("San Diego", "92101"), ("Sacramento", "95814"), ("Oakland", "94612")],
    "TX": [("Austin", "78701"), ("Houston", "77002"), ("Dallas", "75201"), ("San Antonio", "78205")],
    "FL": [("Orlando", "32801"), ("Tampa", "33602"), ("Jacksonville", "32202")],
    "PA": [("Pittsburgh", "15222"), ("Philadelphia", "19103")], "GA": [("Atlanta", "30303"), ("Savannah", "31401")],
    "NC": [("Charlotte", "28202"), ("Raleigh", "27601")], "WA": [("Seattle", "98101"), ("Spokane", "99201")],
    "AZ": [("Phoenix", "85004"), ("Tucson", "85701")], "CO": [("Denver", "80202"), ("Boulder", "80302")],
    "MN": [("Minneapolis", "55401"), ("St. Paul", "55102")], "OR": [("Portland", "97204")],
    "NJ": [("Newark", "07102"), ("Jersey City", "07302")], "MA": [("Boston", "02108"), ("Worcester", "01608")],
    "TN": [("Nashville", "37203"), ("Memphis", "38103")], "MO": [("St. Louis", "63101"), ("Kansas City", "64105")],
    "VA": [("Richmond", "23219"), ("Arlington", "22201")], "DE": [("Wilmington", "19801")],
}
INTERNATIONAL = [  # (city, region, postal code, country)
    ("Toronto", "ON", "M5V 2T6", "CA"), ("Vancouver", "BC", "V6B 1A1", "CA"), ("London", None, "SW1A 1AA", "GB"),
    ("Manchester", None, "M1 1AE", "GB"), ("Sydney", "NSW", "2000", "AU"), ("Berlin", None, "10115", "DE"),
]

FIRST_NAMES = """James Mary Robert Patricia John Jennifer Michael Linda David Elizabeth William Barbara Richard Susan
Joseph Jessica Thomas Sarah Christopher Karen Charles Lisa Daniel Nancy Matthew Betty Anthony Sandra Mark Margaret
Donald Ashley Steven Kimberly Andrew Emily Paul Donna Joshua Michelle Kenneth Carol Kevin Amanda Brian Melissa Timothy
Deborah Ronald Stephanie Jason Rebecca George Laura Edward Sharon Jeffrey Cynthia Ryan Amy Jacob Kathleen Gary Angela
Nicholas Shirley Eric Brenda Jonathan Emma Larry Anna Justin Pamela Scott Nicole Brandon Samantha Benjamin Katherine
Samuel Christine Gregory Debra Alexander Rachel Patrick Carolyn Frank Janet Raymond Maria Jack Olivia Dennis Heather
Jerry Helen Tyler Catherine Aaron Diane Jose Julie Adam Victoria Nathan Joyce Henry Lauren Zachary Kelly Douglas Christina
Peter Ruth Kyle Joan Noah Virginia Ethan Judith Jeremy Evelyn Christian Hannah Walter Andrea Keith Megan Austin Cheryl
Sean Jacqueline Terry Madison Elijah Teresa Gerald Abigail Carl Sophia Harold Martha Dylan Sara Arthur Gloria Lawrence
Janice Jordan Kathryn Jesse Ann Bryan Isabella Billy Judy Bruce Charlotte Gabriel Julia Joe Grace Logan Amber Alan
Alice Juan Jean Albert Denise Willie Frances Elijah Danielle Wayne Marilyn Randy Natalie Mason Beverly Vincent Diana
Liam Brittany Roy Theresa Bobby Kayla Caleb Alexis Bradley Doris Russell Lori Lucas Tiffany Jasmine Marcus Malik Aisha
Mateo Sofia Diego Camila Wei Mei Hiroshi Yuki Priya Arjun""".split()
LAST_NAMES = """Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez Hernandez Lopez Gonzalez Wilson
Anderson Thomas Taylor Moore Jackson Martin Lee Perez Thompson White Harris Sanchez Clark Ramirez Lewis Robinson Walker
Young Allen King Wright Scott Torres Nguyen Hill Flores Green Adams Nelson Baker Hall Rivera Campbell Mitchell Carter
Roberts Gomez Phillips Evans Turner Diaz Parker Cruz Edwards Collins Reyes Stewart Morris Morales Murphy Cook Rogers
Gutierrez Ortiz Morgan Cooper Peterson Bailey Reed Kelly Howard Ramos Kim Cox Ward Richardson Watson Brooks Chavez Wood
James Bennett Gray Mendoza Ruiz Hughes Price Alvarez Castillo Sanders Patel Myers Long Ross Foster Jimenez Powell Jenkins
Perry Russell Sullivan Bell Coleman Butler Henderson Barnes Fisher Vasquez Simmons Romero Jordan Patterson Alexander
Hamilton Graham Reynolds Griffin Wallace Moreno West Cole Hayes Bryant Herrera Gibson Ellis Tran Medina Aguilar Stevens
Murray Ford Castro Marshall Owens Harrison Fernandez McDonald Woods Washington Kennedy Wells Vargas Henry Chen Freeman
Webb Tucker Guzman Burns Crawford Olson Simpson Porter Hunter Gordon Mendez Silva Shaw Snyder Mason Dixon Munoz Hunt
Hicks Holmes Palmer Wagner Black Robertson Boyd Rose Stone Salazar Fox Warren Mills Meyer Rice Schmidt Garza Daniels
Ferguson Nichols Stephens Soto Weaver Ryan Gardner Payne Grant Dunn Kelley Spencer Hawkins Arnold Pierce Vazquez Hansen
Peters Santos Hart Bradley Knight Elliott Cunningham Duncan Armstrong Hudson Carroll Lane Riley Andrews Ray Berry Perkins
Hoffman Johnston Matthews Pena Richards Contreras Willis Carpenter Lawrence Sandoval Kowalski Nowak Schultz Yoder Miller""".split()
USERNAME_WORDS = """thrift vintage retro collector deal hunter treasure bargain vinyl retro golden lucky happy
maple river oak cedar prairie lake harbor sunny blue red green midwest hoosier michigan flea antique""".split()

# Review text by marketplace scale. eBay feedback: 1 positive, 0 neutral, -1 negative.
EBAY_FEEDBACK = {
    1: ["Great item, fast shipping. A+++", "Exactly as described, well packed. Thank you!", "Smooth transaction, would buy again.",
        "Item arrived quickly and in great shape.", "Love it! Great seller supporting a great cause.", "Fast shipping, item as pictured."],
    0: ["Item OK but shipping was slow.", "Minor wear not mentioned in listing.", "Packaging could have been better."],
    -1: ["Item arrived damaged.", "Not as described, had to return.", "Missing pieces not mentioned in listing."],
}
AMAZON_FEEDBACK = {
    5: ["Arrived quickly, great condition for used.", "Exactly as described.", "Great seller, well packaged."],
    4: ["Good condition, a little more wear than expected.", "Arrived a day late but item is fine."],
    3: ["Acceptable condition.", "OK, some highlighting in the book."],
    2: ["Condition worse than listed.", "Slow shipping."],
    1: ["Item never arrived; refunded.", "Wrong item sent."],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def weighted(choices):
    """Pick a key from {key: weight}."""
    keys = list(choices)
    return rng.choices(keys, weights=[choices[k] for k in keys])[0]


def poisson(lam):
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def money(x):
    return round(x + 1e-9, 2)


def local_dt(d, hour_lo, hour_hi):
    """A random local time on date d between the given hours."""
    seconds = rng.randint(int(hour_lo * 3600), int(hour_hi * 3600) - 1)
    return datetime.combine(d, time(0), TZ) + timedelta(seconds=seconds)


def shopper_time(d):
    """Purchase time of day: low overnight, peaking in the evening."""
    hour = rng.choices(range(24), weights=[2, 1, 1, 1, 1, 1, 2, 3, 4, 5, 5, 6, 6, 6, 5, 5, 6, 7, 8, 9, 10, 9, 6, 4])[0]
    return datetime.combine(d, time(hour, rng.randint(0, 59), rng.randint(0, 59)), TZ)


def years_since_start(d):
    return (d - START).days / 365.25


def week_start(d):
    """Saturday that starts the Sat–Fri batch week containing local date d."""
    return d - timedelta(days=(d.weekday() - 5) % 7)


def ts(dt):
    return dt.isoformat(timespec="seconds") if dt else ""


def unique_id(seen, make):
    while True:
        value = make()
        if value not in seen:
            seen.add(value)
            return value


def digits(n):
    return "".join(rng.choices(string.digits, k=n))


# ---------------------------------------------------------------------------
# Ingestion batches: one weekly export per marketplace, Saturday–Friday
# ---------------------------------------------------------------------------

def batch_archived_path(source, start, end):
    if source == AMZ:
        return f"{start.year}{start:%b}{start.day}-{end.year}{end:%b}{end.day}CustomTransaction.csv"
    if source == EBAY:
        return f"Transaction_report_{start:%Y%m%d}_{end:%Y%m%d}.csv"
    return f"ShopGoodwill_Listings_{start:%Y%m%d}_{end:%Y%m%d}.csv"


SOURCE_FOLDER = {AMZ: "amazon-data", EBAY: "ebay-data", SGW: "goodwill-data"}
batches = {}  # (source, week_start) -> row
d = START
while d <= END:
    end = d + timedelta(days=6)
    for source in SOURCES:
        name = batch_archived_path(source, d, end)
        ingested = datetime.combine(end + timedelta(days=1), time(6, 0), TZ) + timedelta(minutes=rng.randint(0, 50))
        batches[(source, d)] = dict(
            source_name=source, file_name=name,
            archived_path=f"archive/{SOURCE_FOLDER[source]}/{d.year}/{name}",
            ingested_at=ts(ingested), period_start=d.isoformat(), period_end=end.isoformat())
    d += timedelta(days=7)


def batch_for(source, dt):
    """Archive path of the weekly batch containing dt; batches are matched by archive path."""
    return batches[(source, week_start(dt.astimezone(TZ).date()))]["archived_path"]


# ---------------------------------------------------------------------------
# Products and listing attempts
# ---------------------------------------------------------------------------

SKU_PREFIX = {SGW: "GWM-SGW", EBAY: "GWM-EBY", AMZ: "GWM-AMZ"}
sku_counter = {SGW: 0, EBAY: 0, AMZ: 0}
products, listings, sales = [], [], []


def product_name(leaf):
    spec = CATALOG[leaf]
    name, typical = rng.choice(spec["items"])
    if spec.get("sizes") == "apparel":
        name += f" Size {rng.choice(APPAREL_SIZES)}"
    elif spec.get("sizes") == "shoes":
        name += f" Size {rng.choice(SHOE_SIZES)}"
    if spec.get("grams"):
        grams = round(rng.uniform(1.2, 9.0), 1)
        name += f" {grams}g"
        typical *= grams / 6.0  # gold pieces are priced largely by weight
    if spec.get("tested") and rng.random() < 0.6:
        name += " - Tested Works"
    return name, typical


def simulate_listing(channel, value, listed_at, attempt):
    """Return (status, ended_at, sale_price, ordered_at) for one listing attempt."""
    season = DEMAND_SEASON[listed_at.month - 1]
    if rng.random() < 0.015:  # withdrawn: damaged, missing parts, or pulled for store
        ended = listed_at + timedelta(days=rng.uniform(0.5, 6))
        return ("CANCELLED", ended, None, None) if ended < CUTOFF else ("ACTIVE", None, None, None)

    auction = channel == SGW or (channel == EBAY and rng.random() < 0.25)
    if auction:
        days = 7 if channel == EBAY else rng.choices([5, 7, 10], weights=[2, 6.5, 1.5])[0]
        ended = listed_at + timedelta(days=days)
        if ended >= CUTOFF:
            return ("ACTIVE", None, None, None)
        p_sell = min(0.92, (0.72 if attempt == 0 else 0.62) * season)
        if rng.random() < p_sell:
            price = value * rng.lognormvariate(0, 0.32) * (0.98 + 0.06 * (season - 1))
            # Checkout lands just after the auction closes; fixed-price sales end exactly at checkout.
            return ("SOLD", ended, max(4.99, price), ended + timedelta(seconds=rng.randint(1, 600)))
        return ("ENDED_UNSOLD", ended, None, None)

    # Fixed price: eBay good-'til-cancelled (90-day cap) or Amazon used offer (120 days).
    window, mean_days, p_sell = (90, 20, 0.8) if channel == EBAY else (120, 26, 0.82)
    days_to_sell = rng.expovariate(season / mean_days)
    if rng.random() < p_sell and days_to_sell < window:
        sold_on = (listed_at + timedelta(days=days_to_sell)).date()
        ordered = max(shopper_time(sold_on), listed_at + timedelta(minutes=30))
        if ordered >= CUTOFF:
            return ("ACTIVE", None, None, None)
        price = value * rng.lognormvariate(0.02, 0.15)
        return ("SOLD", ordered, max(3.99, price), ordered)
    ended = listed_at + timedelta(days=window)
    return ("ENDED_UNSOLD", ended, None, None) if ended < CUTOFF else ("ACTIVE", None, None, None)


d = START
while d <= END:
    if d.weekday() != 6:  # e-commerce team processes donations Monday–Saturday
        lam = 34 * (1.14 ** years_since_start(d)) * DONATION_SEASON[d.month - 1] * (0.5 if d.weekday() == 5 else 1.0)
        for _ in range(poisson(lam)):
            leaf = rng.choices(LEAVES, weights=LEAF_SHARES)[0]
            spec = CATALOG[leaf]
            channel = weighted(spec["channels"])
            name, typical = product_name(leaf)
            inflation = 1.03 ** years_since_start(d)
            value = typical * PRICE_SCALE * inflation * min(MAX_VALUE_MULTIPLE, rng.lognormvariate(0, spec["sigma"]))
            sku_counter[channel] += 1
            sku = f"{SKU_PREFIX[channel]}-{sku_counter[channel]:06d}"
            products.append(dict(sku_number=sku, product_name=name, category_name=leaf[1], parent_category_name=leaf[0]))

            listed_at = local_dt(d + timedelta(days=rng.randint(0, 3)), 9, 17)
            if channel == SGW:  # ShopGoodwill auctions are scheduled to close in the evening
                listed_at = local_dt(listed_at.date(), 19, 22)
            for attempt in range(3):
                if listed_at >= CUTOFF:
                    break
                status, ended, price, ordered = simulate_listing(channel, value, listed_at, attempt)
                listing = dict(source_name=channel, sku_number=sku, listed_at=listed_at, ended_at=ended, status=status, leaf=leaf)
                listings.append(listing)
                if status == "SOLD":
                    sales.append(dict(listing=listing, channel=channel, price=money(price), ordered_at=ordered, leaf=leaf))
                if status != "ENDED_UNSOLD" or rng.random() > 0.55:
                    break  # sold, active, withdrawn, or sent back to the retail stores
                # Relist the same physical item, often cheaper or on another marketplace.
                options = [c for c in spec["channels"] if c != channel]
                if options and rng.random() < 0.4:
                    channel = rng.choice(options)
                value *= rng.uniform(0.78, 0.92)
                listed_at = local_dt(ended.date() + timedelta(days=rng.randint(1, 6)), 9, 17)
                if channel == SGW:
                    listed_at = local_dt(listed_at.date(), 19, 22)
    d += timedelta(days=1)

# Marketplace listing IDs increase over time, as real marketplaces assign them.
seen_ids = set()
next_numeric = {SGW: 186_400_000, EBAY: 266_100_000_000}
for listing in sorted(listings, key=lambda l: l["listed_at"]):
    source = listing["source_name"]
    if source == AMZ:
        alphabet = string.ascii_uppercase + string.digits
        listing["source_listing_id"] = unique_id(seen_ids, lambda: rng.choice("0123") + "".join(rng.choices(alphabet, k=9)))
    else:
        next_numeric[source] += rng.randint(40, 900) if source == SGW else rng.randint(2_000, 90_000)
        listing["source_listing_id"] = str(next_numeric[source])


# ---------------------------------------------------------------------------
# Customers (eBay only), orders, and order lines
# ---------------------------------------------------------------------------

customers = []
customer_pool = []  # one entry per past eBay order: repeat buyers are drawn in proportion to history
seen_customer_ids, seen_usernames = set(), set()


def new_ebay_customer(first_order_at):
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    style = rng.random()
    if style < 0.4:
        base = f"{rng.choice(USERNAME_WORDS)}{rng.choice(USERNAME_WORDS)}_{rng.randint(1, 99)}"
    elif style < 0.75:
        base = f"{first.lower()}{last.lower()[:rng.randint(1, len(last))]}{rng.randint(1, 9999)}"
    else:
        base = f"{first[0].lower()}{last.lower()}{rng.choice(['', '_', '.'])}{rng.randint(10, 99)}"
    username = unique_id(seen_usernames, lambda: base if base not in seen_usernames else f"{base}{rng.randint(1, 999)}")
    if rng.random() < 0.03:
        city, state, zipcode, country = rng.choice(INTERNATIONAL)
    else:
        state = rng.choices(TAX_STATES, weights=TAX_WEIGHTS)[0]
        city, zipcode = rng.choice(US_CITIES[state])
        country = "US"
    row = dict(
        source_name=EBAY, source_customer_id=unique_id(seen_customer_ids, lambda: "EB" + digits(10)),
        username=username, first_name=first, last_name=last, city=city, state=state, zipcode=zipcode, country=country,
        batch_archived_path=batch_for(EBAY, first_order_at))
    # Sparse profiles: some buyers hide their name or address.
    if rng.random() < 0.04:
        row["first_name"] = row["last_name"] = None
    if rng.random() < 0.02:
        row["city"] = row["zipcode"] = None
    customers.append(row)
    return row


SHIP_COST = {"small": (4.2, 6.8), "medium": (8.5, 14.5), "large": (16.0, 32.0), "freight": (0.0, 0.0)}


def item_ship_cost(leaf):
    lo, hi = SHIP_COST[CATALOG[leaf]["ship"]]
    return rng.uniform(lo, hi)


orders, order_items = [], []
seen_order_ids = set()

for channel in SOURCES:
    channel_sales = sorted((s for s in sales if s["channel"] == channel), key=lambda s: s["ordered_at"])
    # Group sales into orders: ShopGoodwill buyers often combine several auction
    # wins into one shipment; multi-item orders are rarer elsewhere.
    combine_rate = {SGW: 0.16, EBAY: 0.07, AMZ: 0.04}[channel]
    groups = []
    for sale in channel_sales:
        last = groups[-1] if groups else None
        if (last and len(last) < 4 and rng.random() < combine_rate
                and sale["ordered_at"].date() == last[0]["ordered_at"].date()):
            last.append(sale)
        else:
            groups.append([sale])

    for group in groups:
        ordered_at = max(s["ordered_at"] for s in group)  # a combined order is placed at its last purchase
        customer = None
        if channel == EBAY:
            if customer_pool and rng.random() < 0.3:
                customer = rng.choice(customer_pool)
            else:
                customer = new_ebay_customer(ordered_at)
            customer_pool.append(customer)
            country, state = customer["country"], customer["state"]
        else:
            country, state = "US", rng.choices(TAX_STATES, weights=TAX_WEIGHTS)[0]

        if channel == AMZ:
            source_order_id = unique_id(seen_order_ids, lambda: f"{rng.choice(['111', '112', '113', '114'])}-{digits(7)}-{digits(7)}")
        elif channel == EBAY:
            source_order_id = unique_id(seen_order_ids, lambda: f"{rng.randint(10, 28)}-{digits(5)}-{digits(5)}")
        else:
            source_order_id = unique_id(seen_order_ids, lambda: str(rng.randint(30_000_000, 79_999_999)))

        lines, merchandise, media_items, all_freight = [], 0.0, 0, True
        for sale in group:
            spec = CATALOG[sale["leaf"]]
            price = sale["price"]
            discount = 0.0
            fixed_price = channel == AMZ or (channel == EBAY and sale["listing"]["ended_at"] == sale["ordered_at"])
            if fixed_price and rng.random() < (0.08 if channel == EBAY else 0.03):
                discount = money(price * rng.uniform(0.05, 0.2))  # markdown sale / promotion
            refund = 0.0
            if rng.random() < 0.022:  # returns and "not as described" claims
                net = price - discount
                refund = money(net if rng.random() < 0.75 else net * rng.uniform(0.15, 0.5))
            lines.append(dict(source_name=channel, source_order_id=source_order_id,
                              source_listing_id=sale["listing"]["source_listing_id"], quantity=1,
                              unit_price=price, discount_amount=discount, refund_amount=refund))
            merchandise += price - discount
            media_items += 1 if spec.get("media") else 0
            all_freight &= spec["ship"] == "freight"

        # Shipping: Goodwill's carrier cost vs. what the buyer was charged.
        costs = sorted((item_ship_cost(s["leaf"]) for s in group), reverse=True)
        carrier_cost = costs[0] + 0.45 * sum(costs[1:])  # combined shipment
        if channel == SGW:
            charge = 0.0 if all_freight else carrier_cost + 2.00  # pickup-only furniture vs. shipping + handling
        elif channel == EBAY:
            charge = 0.0 if rng.random() < 0.35 else carrier_cost + rng.uniform(0, 2.5)  # free-shipping listings
        else:
            charge = 3.99 * len(group) if media_items == len(group) else carrier_cost + rng.uniform(0.5, 3.0)
            if media_items == len(group):
                carrier_cost = rng.uniform(3.4, 5.6) * (1 + 0.4 * (len(group) - 1))  # USPS Media Mail
        charge, carrier_cost = money(charge), money(carrier_cost)

        rate = STATE_TAX[state][0] if country == "US" else 0.0
        tax = money((merchandise + charge) * rate)

        # Marketplace and payment fees.
        if channel == SGW:
            fee = 0.09 * (merchandise + charge) + 0.029 * (merchandise + charge + tax) + 0.30
        elif channel == EBAY:
            fee = 0.1325 * (merchandise + charge + tax) + 0.40
            if rng.random() < 0.3:
                fee += 0.03 * merchandise  # promoted listing
        else:
            fee = 0.15 * (merchandise + charge) + 1.80 * media_items  # referral + media closing fee
        fee = money(fee)

        full_refund = all(l["refund_amount"] >= money(l["unit_price"] - l["discount_amount"]) for l in lines)
        status = "REFUNDED" if full_refund else ("SHIPPED" if ordered_at > CUTOFF - timedelta(days=4) else "COMPLETED")
        orders.append(dict(
            source_name=channel, source_order_id=source_order_id,
            source_customer_id=customer["source_customer_id"] if customer else None,
            ordered_at=ordered_at, status=status,
            shipping_charge_amount=charge, shipping_cost_amount=carrier_cost, tax_amount=tax, operation_fee_amount=fee,
            batch_archived_path=batch_for(channel, ordered_at), _refunded=any(l["refund_amount"] > 0 for l in lines)))
        order_items.extend(lines)


# ---------------------------------------------------------------------------
# Reviews: eBay feedback (1 / 0 / -1) and Amazon seller feedback (1–5 stars).
# ShopGoodwill exports carry no review data. Scales are kept as each source
# reports them; comparing them is an open decision (DATABASE_SPEC §9).
# ---------------------------------------------------------------------------

reviews = []
seen_review_ids = set()
for order in orders:
    channel = order["source_name"]
    if channel == SGW or order["status"] == "SHIPPED":
        continue
    if channel == EBAY and rng.random() < 0.22:
        rating = rng.choices([1, 0, -1], weights=[60, 25, 15] if order["_refunded"] else [93, 4, 3])[0]
        text = rng.choice(EBAY_FEEDBACK[rating])
        review_id = unique_id(seen_review_ids, lambda: digits(13))
        reviewed_at = order["ordered_at"] + timedelta(days=rng.uniform(3, 14))
        customer_id = order["source_customer_id"]
    elif channel == AMZ and rng.random() < 0.04:
        rating = rng.choices([5, 4, 3, 2, 1], weights=[20, 20, 15, 15, 30] if order["_refunded"] else [78, 12, 4, 2, 4])[0]
        text = rng.choice(AMAZON_FEEDBACK[rating]) if rng.random() < 0.85 else None
        review_id = unique_id(seen_review_ids, lambda: "AFB" + "".join(rng.choices(string.ascii_uppercase + string.digits, k=11)))
        reviewed_at = order["ordered_at"] + timedelta(days=rng.uniform(5, 21))
        customer_id = None  # Amazon does not share buyer identity
    else:
        continue
    if reviewed_at >= CUTOFF:
        continue
    reviews.append(dict(source_name=channel, source_review_id=review_id, source_customer_id=customer_id,
                        source_order_id=order["source_order_id"], rating=rating, review_text=text,
                        reviewed_at=reviewed_at, batch_archived_path=batch_for(channel, reviewed_at)))


# ---------------------------------------------------------------------------
# Write CSVs
# ---------------------------------------------------------------------------

def write(name, columns, rows):
    path = OUT_DIR / f"{name}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            values = []
            for c in columns:
                v = row.get(c)
                if isinstance(v, datetime):
                    v = ts(v)
                elif isinstance(v, float):
                    v = f"{v:.2f}"
                values.append("" if v is None else v)
            writer.writerow(values)
    print(f"{path.name:<22} {len(rows):>7,} rows")


categories = []
for root in dict.fromkeys(k[0] for k in LEAVES):
    categories.append(dict(name=root, parent_name=None))
for root, child in LEAVES:
    categories.append(dict(name=child, parent_name=root))

for listing in listings:
    listing["batch_archived_path"] = batch_for(listing["source_name"], listing["listed_at"])

write("source", ["name"], [dict(name=s) for s in SOURCES])
write("category", ["name", "parent_name"], categories)
write("ingestion_batch", ["source_name", "file_name", "archived_path", "ingested_at", "period_start", "period_end"],
      sorted(batches.values(), key=lambda b: (b["period_start"], b["source_name"])))
write("product", ["sku_number", "product_name", "category_name", "parent_category_name"], products)
write("listing", ["source_name", "source_listing_id", "sku_number", "listed_at", "ended_at", "status", "batch_archived_path"],
      sorted(listings, key=lambda l: l["listed_at"]))
write("customer", ["source_name", "source_customer_id", "username", "first_name", "last_name", "city", "state", "zipcode",
                   "country", "batch_archived_path"], customers)
write("sales_order", ["source_name", "source_order_id", "source_customer_id", "ordered_at", "status", "shipping_charge_amount",
                      "shipping_cost_amount", "tax_amount", "operation_fee_amount", "batch_archived_path"],
      sorted(orders, key=lambda o: o["ordered_at"]))
write("order_item", ["source_name", "source_order_id", "source_listing_id", "quantity", "unit_price", "discount_amount",
                     "refund_amount"], order_items)
write("review", ["source_name", "source_review_id", "source_customer_id", "source_order_id", "rating", "review_text",
                 "reviewed_at", "batch_archived_path"], sorted(reviews, key=lambda r: r["reviewed_at"]))
