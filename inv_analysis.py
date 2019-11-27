#!/usr/bin/env python
"""
Find all world inventories and print contents.
"""

import locale, os, sys
import csv
import nbt
from nbt.world import WorldFolder

"""
List of valid entity IDs that have inventories

Not yet included: player inventory, player armor, player hands, villager armor, villager hands, ender_chest, horse/mule/donkey saddle/armor

Notes:
    - minecraft:trapped_chest appears as minecraft:chest
    - <color>_shulker_box appears as shulker_box
"""
valid_item_eids = [
        'minecraft:chest', 'minecraft:chest_minecart', 'minecraft:hopper_minecart',
        'minecraft:shulker_box', 'minecraft:furnace', 'minecraft:dispenser', 'minecraft:dropper',
        'minecraft:brewing_stand', 'minecraft:hopper'
        ]
valid_mob_eids = [
        'minecraft:villager', 'minecraft:zombie_villager', 'minecraft:horse', 'minecraft:donkey', 'minecraft:mule'
        ]

inv_content_headers = ['Entity Name', 'x', 'y', 'z', 'Item', 'Data/Damage', 'Count']
world_total_headers = ['Item', 'Data/Damage', 'World Count']

world_items = {}

class Position(object):
    def __init__(self, x,y,z):
        self.x = x
        self.y = y
        self.z = z

class Inventory(object):
    def __init__(self, eid, pos, items, saddle, armor):
        self.eid  = eid
        self.pos   = Position(*pos)
        self.items = items
        self.saddle = saddle
        self.armor = armor

def items_from_nbt(nbtlist):
    """
    :param nbtlist: list of nbt item tags
    :returns: dictionary of item names corresponding to a list of dictionaries of each type
                of the item containing its count and type corresponding to the item tags
                Example: items = {logs : {'0': <count>, '2': <count>}}
    """
    items = {}      # blockid --> dictionary of types
    for item in nbtlist:
        iid = item['id'].value

        # Integer before the "flattening"
        # Prefixed string after the "flattening"

        if iid.startswith('minecraft:'):
            iid = iid[10:]
        count = item['Count'].value
        damage = item['Damage'].value
        if iid not in items:
            items[iid] = {}
        if damage not in items[iid]:
            items[iid][damage] = 0
        if iid not in world_items:
            world_items[iid] = {}
        if damage not in world_items[iid]:
            world_items[iid][damage] = 0

        items[iid][damage] += count
        world_items[iid][damage] += count
    return items

def player_inv(uuid, path):
    nbtfile = nbt.nbt.NBTFile(path, 'rb')
    if not "bukkit" in nbtfile:
        return
    if not "lastPlayed" in nbtfile["bukkit"]:
        return
    #for item in nbtfile['Inventory']:
        #print(item['Slot'].value, item['id'].value, item['Count'].value, item['Damage'].value)
    try:
        items = items_from_nbt(nbtfile['Inventory'])
    except KeyError:
        items = {}

    try:
        pos = nbtfile['Pos']
        x = pos[0].value
        y = pos[1].value
        z = pos[2].value
    except KeyError:
        x = 0
        y = 0
        z = 0
    return (Inventory(uuid, (x,y,z), items, None, None))

def inventories_per_chunk(chunk):
    """
    Find inventories and get contents in a given chunk.

    :param chunk: a chunk's NBT data to scan for inventories
    :returns: a list of all inventories in the chunk
    """

    inventories = []
    saddle = None
    armor = None

    for entity in chunk['Entities']:
        # TODO: clean up real_eid vs eid, super hacky.  Bad code.
        eid = entity['id'].value
        if eid in valid_item_eids or eid in valid_mob_eids:
            pos = entity['Pos']
            x = pos[0].value
            y = pos[1].value
            z = pos[2].value

            # Special cases: these are listed as Entities but are formatted as TileEntities
            if eid == 'minecraft:hopper_minecart' or eid == 'minecraft:chest_minecart' \
                    or eid == 'minecraft:mule' or eid == 'minecraft:donkey':
                try:
                    items = items_from_nbt(entity['Items'])
                except KeyError:
                    items = {}
            else:
                try:
                    items = items_from_nbt(entity['Inventory'])
                except KeyError:
                    items = {}

            if eid == 'minecraft:horse':
                try:
                    armor = [entity['ArmorItem']['id'], entity['ArmorItem']['Count'], entity['ArmorItem']['Damage']]
                except KeyError:
                    armor = None

            if eid == 'minecraft:horse' or eid == 'minecraft:mule':
                try:
                    saddle = [entity['SaddleItem']['id'], entity['SaddleItem']['Count'], entity['SaddleItem']['Damage']]
                except KeyError:
                    saddle = None

            if eid.startswith('minecraft:'):
                eid = eid[10:]
            inventories.append(Inventory(eid, (x,y,z), items, saddle, armor))

    for entity in chunk['TileEntities']:
        eid = entity['id'].value
        if eid in valid_item_eids or eid in valid_mob_eids:
            x = entity['x'].value
            y = entity['y'].value
            z = entity['z'].value

            try:
                items = items_from_nbt(entity['Items'])
            except KeyError:
                items = {}

            if eid.startswith('minecraft:'):
                eid = eid[10:]
            inventories.append(Inventory(eid, (x,y,z), items, saddle, armor))
    return inventories

def print_inv_contents(inventory, inv_f):
    """
    Write all inventory type, coordinates, item name, item type, and item count to f.

    :param inventories: list of Inventory objects
    :param inv_f: open file descriptor for writing inventory data to
    """

    inv_writer = csv.writer(inv_f)

    for iid, types in inventory.items.items():
        for type, count in types.items():
            inv_writer.writerow([\
                    inventory.eid, \
                    '{0:.3g}'.format(inventory.pos.x), \
                    '{0:.3g}'.format(inventory.pos.y), \
                    '{0:.3g}'.format(inventory.pos.z), \
                    iid, type, count\
                    ])

def print_world_contents(world_f):
    """
    :param world_f: open file descriptor for writing total world count data to
    """

    world_writer = csv.writer(world_f)
    for iid, types in world_items.items():
        for type, count in types.items():
            world_writer.writerow([iid, type, count])

def main(world_folder):
    """
    :param world_folder: file path to a minecraft world data folder
    :returns: 0 if successful, 1 if a Keyboard Interrupt signal was received
    """
    world = WorldFolder(world_folder)
    world_totals_f = open("item_totals.csv","w")
    inv_contents_f = open('inv_contents.csv', 'w')
    inv_writer = csv.writer(inv_contents_f)
    inv_writer.writerow(inv_content_headers)

    if (not os.path.exists('item_totals.txt')):
        world_writer = csv.writer(world_totals_f)
        world_writer.writerow(world_total_headers)

    try:
        # get non-player inventories
        for chunk in world.iter_nbt():
            for inventory in inventories_per_chunk(chunk["Level"]):
                print_inv_contents(inventory, inv_contents_f)
        # get player inventories
        for root, dirs, files in os.walk(world_folder):
            for file in files:
                if file.endswith(".dat") and len(file) == 40:
                    uuid = file[0:36]
                    print_inv_contents(player_inv(uuid, os.path.join(root, file)), inv_contents_f)
        print_world_contents(world_totals_f)
    except KeyboardInterrupt:
        inv_contents_f.close()
        world_totals_f.close()
        return 1

    inv_contents_f.close()
    world_totals_f.close()

    return 0

if __name__ == '__main__':
    if (len(sys.argv) == 1):
        print("No world folder specified!")
        sys.exit(1)
    world_folder = sys.argv[1]
    # clean path name, eliminate trailing slashes:
    world_folder = os.path.normpath(world_folder)
    if (not os.path.exists(world_folder)):
        print("No such folder as " + world_folder)
        sys.exit(1)

    main(world_folder)
