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

Not yet included: player armor/hands, villager armor, villager hands, ender_chest, horse/mule/donkey saddle/armor

Notes:
    - minecraft:trapped_chest appears as minecraft:chest
    - <color>_shulker_box appears as shulker_box
"""
valid_item_names = [
        'minecraft:chest', 'minecraft:chest_minecart', 'minecraft:hopper_minecart',
        'minecraft:shulker_box', 'minecraft:furnace', 'minecraft:dispenser', 'minecraft:dropper',
        'minecraft:brewing_stand', 'minecraft:hopper'
        ]
valid_mob_names = [
        'minecraft:villager', 'minecraft:zombie_villager', 'minecraft:horse', 'minecraft:donkey', 'minecraft:mule'
        ]

inv_content_headers = ['Inventory Name', 'x', 'y', 'z', 'Item', 'Lore', 'Data/Damage', 'Count', 'Slot']
world_total_headers = ['Item', 'Lore', 'Data/Damage', 'World Count']

world_inv = []

class Position(object):
    def __init__(self, x,y,z):
        self.x = x
        self.y = y
        self.z = z

class Item(object):
    def __init__(self, full_name, slot, count, damage, lore):
        self.full_name = full_name
        if full_name.startswith('minecraft:'):
            self.common_name = full_name[10:]
        else:
            self.common_name = full_name
        self.slot = slot
        self.count = count
        self.damage = damage
        self.lore = lore

    def equals(self, other):
        return self.full_name == other.full_name and self.damage == other.damage and self.lore == other.lore

    def set_count(self, new_count):
        self.count = new_count

class Inventory(object):
    def __init__(self, full_name, pos, items, saddle, armor):
        self.full_name  = full_name
        if full_name.startswith('minecraft:'):
            self.common_name = full_name[10:]
        else:
            self.common_name = full_name
        self.pos   = Position(*pos)
        self.items = items
        self.saddle = saddle
        self.armor = armor

def update_world_totals(new_item):
    for item in world_inv:
        if new_item.equals(item):
            item.set_count(item.count + new_item.count)
            return
    world_inv.append(Item(new_item.full_name, None, new_item.count, new_item.damage, new_item.lore))

def items_from_nbt(nbtlist):
    """
    :param nbtlist: list of nbt item tags
    :returns: list of Item objects found in the nbtlist
    """
    items = []
    for item in nbtlist:
        full_name = item['id'].value
        count = item['Count'].value
        damage = item['Damage'].value

        try:
            slot = item['Slot'].value
        except KeyError:
            slot = ""

        try:
            lore = item['tag']['display']['Lore'][0].valuestr()
        except KeyError:
            lore = ""

        new_item = Item(full_name, slot, count, damage, lore)
        items.append(new_item)
        update_world_totals(new_item)
    return items

def player_inv(uuid, path):
    nbtfile = nbt.nbt.NBTFile(path, 'rb')
    if not "bukkit" in nbtfile:
        return
    if not "lastPlayed" in nbtfile["bukkit"]:
        return
    #print(nbtfile['Inventory'].pretty_tree())
    try:
        items = items_from_nbt(nbtfile['Inventory'])
    except KeyError:
        items = []

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

    for entity in chunk['Entities']:
        # TODO: clean up real_eid vs eid, super hacky.  Bad code.
        full_name = entity['id'].value
        if full_name in valid_item_names or full_name in valid_mob_names:
            pos = entity['Pos']
            x = pos[0].value
            y = pos[1].value
            z = pos[2].value

            # Special cases: these are listed as Entities but are formatted as TileEntities
            if full_name == 'minecraft:hopper_minecart' or full_name == 'minecraft:chest_minecart' \
                    or full_name == 'minecraft:mule' or full_name == 'minecraft:donkey':
                try:
                    items = items_from_nbt(entity['Items'])
                except KeyError:
                    items = []
            else:
                try:
                    items = items_from_nbt(entity['Inventory'])
                except KeyError:
                    items = []

            # TODO: Horse/mule armor/saddle
            if full_name == 'minecraft:horse':
                try:
                    armor = [entity['ArmorItem']['id'], entity['ArmorItem']['Count'], entity['ArmorItem']['Damage']]
                except KeyError:
                    armor = None
            else:
                armor = None

            if full_name == 'minecraft:horse' or full_name == 'minecraft:mule':
                try:
                    saddle = [entity['SaddleItem']['id'], entity['SaddleItem']['Count'], entity['SaddleItem']['Damage']]
                except KeyError:
                    saddle = None
            else:
                saddle = None

            inventories.append(Inventory(full_name, (x,y,z), items, saddle, armor))

    for entity in chunk['TileEntities']:
        full_name = entity['id'].value

        if full_name in valid_item_names or full_name in valid_mob_names:
            x = entity['x'].value
            y = entity['y'].value
            z = entity['z'].value

            try:
                items = items_from_nbt(entity['Items'])
            except KeyError:
                items = []

            inventories.append(Inventory(full_name, (x,y,z), items, None, None))
    return inventories

def print_inv_contents(inventory, inv_f):
    """
    Write all inventory type, coordinates, item name, item type, and item count to f.

    :param inventories: list of Inventory objects
    :param inv_f: open file descriptor for writing inventory data to
    """

    inv_writer = csv.writer(inv_f)

    for item in inventory.items:
        x_pos = '{0:.3g}'.format(inventory.pos.x)
        y_pos = '{0:.3g}'.format(inventory.pos.y)
        z_pos = '{0:.3g}'.format(inventory.pos.z)
        inv_writer.writerow([\
                inventory.common_name, \
                x_pos, y_pos, z_pos, \
                item.common_name, item.lore, \
                item.damage, item.count, item.slot\
                ])

def print_world_contents(world_f):
    """
    :param world_f: open file descriptor for writing total world count data to
    """

    world_writer = csv.writer(world_f)
    for item in world_inv:
        world_writer.writerow([item.common_name, item.lore, item.damage, item.count])

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
        # print world totals
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
