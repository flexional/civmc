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
Not yet included: total item count file

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

inv_content_headers = ['Entity Name', 'Entity Type', 'x', 'y', 'z', 'Item', 'Data/Damage', 'Count']
item_total_headers = ['Item', 'Data/Damage', 'World Count']

class Position(object):
    def __init__(self, x,y,z):
        self.x = x
        self.y = y
        self.z = z

class Inventory(object):
    def __init__(self, eid, pos, items, saddle, armor):
        self.eid  = eid[10:]
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

        if type(iid) == str and iid.startswith('minecraft:'):
            iid = iid[10:]
        count = item['Count'].value
        damage = item['Damage'].value
        if iid not in items:
            items[iid] = {}
        if damage not in items[iid]:
            items[iid][damage] = 0
        items[iid][damage] += count
    return items

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

            inventories.append(Inventory(eid, (x,y,z), items, saddle, armor))

    for entity in chunk['TileEntities']:
        eid = entity['id'].value
        #if eid != 'minecraft:villager' and eid != 'minecraft:cow' and eid != 'minecraft:chicken':
        #    print(entity.pretty_tree())
        if eid in valid_item_eids or eid in valid_mob_eids:
            x = entity['x'].value
            y = entity['y'].value
            z = entity['z'].value

            try:
                items = items_from_nbt(entity['Items'])
            except KeyError:
                items = {}

            inventories.append(Inventory(eid, (x,y,z), items, saddle, armor))
    return inventories

def print_results(inventories, f):
    """
    Write all inventories' type, coordinates, item name, item type, and item count to f.

    :param inventories: list of Inventory objects
    :param f: open file descriptor for writing inventory data to
    """

    csv_writer = csv.writer(f)

    # TODO: Probably could increase performance of this twice-nested loop
    for inventory in inventories:
        for iid, types in inventory.items.items():
            for type, count in types.items():
                csv_writer.writerow([inventory.eid, '{0:.3g}'.format(inventory.pos.x), '{0:.3g}'.format(inventory.pos.y), '{0:.3g}'.format(inventory.pos.z), iid, type, count])

def main(world_folder):
    """
    :param world_folder: file path to a minecraft world data folder
    :returns: 0 if successful, 1 if a Keyboard Interrupt signal was received
    """
    world = WorldFolder(world_folder)
    #item_totals_f = open("item_totals.txt","a+")
    inv_contents_f = open('inv_contents.csv', 'w')
    header_writer = csv.writer(inv_contents_f)
    header_writer.writerow(inv_content_headers)

    try:
        for chunk in world.iter_nbt():
            print_results(inventories_per_chunk(chunk["Level"]), inv_contents_f)
    except KeyboardInterrupt:
        inv_contents_f.close()
        return 1

    inv_contents_f.close()
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
