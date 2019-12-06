#!/usr/bin/env python
"""
Outputs contents of every inventory in a given Minecraft world folder.

Notes:
    - Only tested with Minecraft 1.12.2
    - Written for Python 2.7
    - minecraft:trapped_chest appears as minecraft:chest
    - <color>_shulker_box appears as shulker_box
    - Not included: villager armor, villager hands, aggressive mobs (skeletons, zombies, etc), ender_chest
"""

import locale, os, sys
import csv
import nbt
from nbt.world import WorldFolder

"""
List of valid entity IDs that have inventories
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

class Item(object):
    """
    Describes an item stack taking up one inventory space.
    """
    def __init__(self, full_name, slot, count, damage, lore):
        """
        Constructs a new Item object with the given minecraft ID, slot number (if applicable), item count (of the stack),
        damage (sometimes used to distinguish items such as logs), and lore.

        :param full_name: the full minecraft ID of the item, typically of the form package:item_name
        :param slot: the slot number the item resides in the inventory
        :param count: the item count of the item stack
        :param lore: the lore describing the item, if applicable
        """
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
        """
        Compares two Item objects for equivalency, which is defined as:
            1. Both Items have the same full_name
            2. Both Items have the same damage
            3. Both Items have the same lore

        :param other: the Item object to compare the calling Item object to.
        :returns: true if equivalent, false if not
        """
        return self.full_name == other.full_name and self.damage == other.damage and self.lore == other.lore

    def set_count(self, new_count):
        """
        Sets the count attribute of the calling Item object to new_count.

        :param new_count: the value to set the calling Item object's count attribute to.
        """
        self.count = new_count

class Inventory(object):
    """
    Describes an inventory existing in the world (chests, players, mobs, etc).
    """
    def __init__(self, full_name, x, y, z, items):
        """
        Constructs a new Inventory object with the given minecraft ID, coordinates, and Item objects (including equipped saddle/armor).

        :param full_name: the full minecraft ID of the inventory, typically of the form package:inventory_type.
            For player inventories, the full_name is the player's UUID.
        :param x: the x coordinate of the inventory's position
        :param y: the y coordinate of the inventory's position
        :param z: the z coordinate of the inventory's position
        :param items: a List of Item objects in the inventory
        """
        self.full_name  = full_name
        if full_name.startswith('minecraft:'):
            self.common_name = full_name[10:]
        else:
            self.common_name = full_name
        self.x = x
        self.y = y
        self.z = z
        self.items = items

def update_world_totals(new_item):
    """
    Updates the world_inv List to add new_item or to increase the count if an Item equivalent to new_item already exists in world_inv.

    :param new_item: the Item object to use to update the world_inv List
    """
    # TODO: Can definitely optimize this search if performance becomes an issue
    for item in world_inv:
        if new_item.equals(item):
            item.set_count(item.count + new_item.count)
            return
    world_inv.append(Item(new_item.full_name, None, new_item.count, new_item.damage, new_item.lore))

def items_from_nbt(nbtlist):
    """
    Creates a List of Items from the given NBT tags list and updates the world_inv List with each Item.

    :param nbtlist: list of NBT item tags
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
            """
            TODO (if problematic): Only looks at first lore Tag, ignores any others if applicable.
            This may cause issues for multiple-lored items.
            """
            lore = item['tag']['display']['Lore'][0].valuestr()
        except KeyError:
            lore = ""

        new_item = Item(full_name, slot, count, damage, lore)
        items.append(new_item)
        update_world_totals(new_item)
    return items

def player_inv(uuid, path):
    """
    Finds the location of a player and gets the contents of their inventory (and equipment).

    :param uuid: the UUID of the player
    :param path: the absolute path of the player's .dat file
    :returns: an Inventory object describing the player's inventory
    """

    nbtfile = nbt.nbt.NBTFile(path, 'rb')
    if not "bukkit" in nbtfile:
        return
    if not "lastPlayed" in nbtfile["bukkit"]:
        return
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
    return (Inventory(uuid, x, y, z, items))

def inventories_per_chunk(chunk):
    """
    Finds all non-player inventories in a given chunk  and gets their contents.

    :param chunk: a chunk's NBT data to scan for inventories
    :returns: a list of all Inventories in the chunk
    """

    inventories = []

    for entity in chunk['Entities']:
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

            """
            if full_name == 'minecraft:horse' or full_name == 'minecraft:mule' or full_name == 'minecraft:donkey':
                print(entity.pretty_tree())
            """
            # Note: Does not include lore if saddle/mount-armor ever receive lore
            try:
                armor_item = Item(entity['ArmorItem']['id'].value, -1, \
                        entity['ArmorItem']['Count'].value, \
                        entity['ArmorItem']['Damage'].value, "")
                items.append(armor_item)
                update_world_totals(armor_item)
            except KeyError:
                pass

            try:
                saddle_item = Item(entity['SaddleItem']['id'].value, -1, \
                        entity['SaddleItem']['Count'].value, \
                        entity['SaddleItem']['Damage'].value, "")
                items.append(saddle_item)
                update_world_totals(saddle_item)
            except KeyError:
                pass

            inventories.append(Inventory(full_name, x, y, z, items))

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

            inventories.append(Inventory(full_name, x, y, z, items))
    return inventories

def print_inv_contents(inventory, inv_f):
    """
    Writes all of inventory's data to f.

    :param inventory: the Inventory object to be written to inv_f
    :param inv_f: open file descriptor for writing inventory data
    """

    inv_writer = csv.writer(inv_f)

    for item in inventory.items:
        x_pos = '{0:.3g}'.format(inventory.x)
        y_pos = '{0:.3g}'.format(inventory.y)
        z_pos = '{0:.3g}'.format(inventory.z)
        inv_writer.writerow([\
                inventory.common_name, \
                x_pos, y_pos, z_pos, \
                item.common_name, item.lore, \
                item.damage, item.count, item.slot\
                ])

def print_world_contents(world_f):
    """
    Writes the collective contents of the world to world_f.

    :param world_f: open file descriptor for writing total world count data
    """

    world_writer = csv.writer(world_f)
    for item in world_inv:
        world_writer.writerow([item.common_name, item.lore, item.damage, item.count])

def main(world_folder):
    """
    Opens/closes file descriptors and goes through all chunks and player .dat files for inventory data.

    :param world_folder: file path to a Minecraft world data folder
    :returns: 0 if successful, 1 if a Keyboard Interrupt signal was received
    """
    world = WorldFolder(world_folder)

    inv_contents_f = open('inv_contents.csv', 'w')
    inv_writer = csv.writer(inv_contents_f)
    inv_writer.writerow(inv_content_headers)

    world_totals_f = open("world_contents.csv","w")
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
