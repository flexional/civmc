# civmc
This repository is intended for code pertaining to small tools/scripts developed to support server admins of civ servers.  These tools were specifically developed and tailored for the multiplayer civ server civrealms.com.


## inv_analysis.py
This tool scans a Minecraft world data folder for ALL existing inventories (chests, players, mountable-mobs, etc) with the exception of aggressive mobs & Villagers.  It outputs two files:
1. inv_contents.csv: contains a list of all individual inventories' items including inventory ID, item ID, slot, damage, count, and lore.
2. item_totals.csv: contains a list of all unique items (item ID, damage, and lore determine uniqueness) found in the world and their aggregate world count.
