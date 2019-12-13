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
import getopt
import time, datetime
from tqdm import tqdm
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

"""
List of items that are capable of degrading and DO NOT get worn-in
"""
degradeable_tools = [
        'minecraft:bow', 'minecraft:carrot_on_a_stick', 'minecraft:diamond_axe', 'minecraft:diamond_hoe',
        'minecraft:diamond_horse_armor', 'minecraft:diamond_pickaxe', 'minecraft:diamond_shovel',
        'minecraft:diamond_sword', 'minecraft:fishing_rod', 'minecraft:flint_and_steel', 'minecraft:golden_axe',
        'minecraft:golden_hoe', 'minecraft:golden_horse_armor', 'minecraft:golden_pickaxe',
        'minecraft:golden_shovel', 'minecraft:golden_sword', 'minecraft:iron_axe', 'minecraft:iron_hoe',
        'minecraft:iron_horse_armor', 'minecraft:iron_pickaxe', 'minecraft:iron_shovel', 'minecraft:iron_sword',
        'minecraft:shears', 'minecraft:shield', 'minecraft:stone_axe', 'minecraft:stone_hoe', 'minecraft:stone_pickaxe',
        'minecraft:stone_shovel', 'minecraft:stone_sword'
        ]

"""
List of items that are capable of degrading and DO get worn-in
"""
degradeable_armor = [
        'minecraft:chainmail_boots', 'minecraft:chainmail_chestplate', 'minecraft:chainmail_helmet',
        'minecraft:chainmail_leggings', 'minecraft:diamond_boots', 'minecraft:diamond_chestplate',
        'minecraft:diamond_helmet', 'minecraft:diamond_leggings', 'minecraft:golden_boots',
        'minecraft:golden_chestplate', 'minecraft:golden_helmet', 'minecraft:golden_leggings',
        'minecraft:iron_boots', 'minecraft:iron_chestplate', 'minecraft:iron_helmet',
        'minecraft:iron_leggings', 'minecraft:leather_boots', 'minecraft:leather_chestplate',
        'minecraft:leather_helmet', 'minecraft:leather_leggings'
        ]

inv_content_headers = ['Inventory Name', 'x', 'y', 'z', 'Item', 'Lore', 'Data/Damage', 'Count']
world_total_headers = ['Item', 'Lore', 'Data/Damage', 'World Count']

world_inv = []

class Item(object):
    """
    Describes an item stack taking up one inventory space.
    """
    def __init__(self, full_name, count, damage, lore):
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
        if (self.full_name in degradeable_tools):
            return self.full_name == other.full_name and self.lore == other.lore
        elif (self.full_name in degradeable_armor):
            return self.full_name == other.full_name
        else:
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
    world_inv.append(Item(new_item.full_name, new_item.count, new_item.damage, new_item.lore))

def items_from_nbt(nbtlist, verbose):
    """
    Creates a List of Items from the given NBT tags list and updates the world_inv List with each Item.

    :param nbtlist: list of NBT item tags
    :returns: list of Item objects found in the nbtlist if verbose, else an empty list
    """
    items = []
    for item in nbtlist:
        full_name = item['id'].value
        count = item['Count'].value
        damage = item['Damage'].value

        try:
            """
            TODO (if problematic): Only looks at first lore Tag, ignores any others if applicable.
            This may cause issues for multiple-lored items.
            """
            lore = item['tag']['display']['Lore'][0].valuestr()
        except KeyError:
            lore = ""

        new_item = Item(full_name, count, damage, lore)
        if (verbose):
            items.append(new_item)
        update_world_totals(new_item)
    if (verbose):
        return items
    else:
        return []

def player_inv(uuid, path, verbose):
    """
    Finds the location of a player and gets the contents of their inventory (and equipment).

    :param uuid: the UUID of the player
    :param path: the absolute path of the player's .dat file
    :returns: an Inventory object describing the player's inventory if verbose, else an empty list
    """

    nbtfile = nbt.nbt.NBTFile(path, 'rb')
    if not "bukkit" in nbtfile:
        return
    if not "lastPlayed" in nbtfile["bukkit"]:
        return
    try:
        items = items_from_nbt(nbtfile['Inventory'], verbose)
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

    if (verbose):
        return (Inventory(uuid, x, y, z, items))
    else:
        return []

def inventories_per_chunk(chunk, verbose):
    """
    Finds all non-player inventories in a given chunk  and gets their contents.

    :param chunk: a chunk's NBT data to scan for inventories
    :returns: a list of all Inventories in the chunk, if verbose, otherwise an empty list
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
                    items = items_from_nbt(entity['Items'], verbose)
                except KeyError:
                    items = []
            else:
                try:
                    items = items_from_nbt(entity['Inventory'], verbose)
                except KeyError:
                    items = []

            # Note: Does not include lore if saddle/mount-armor ever receive lore
            try:
                armor_item = Item(entity['ArmorItem']['id'].value, \
                        entity['ArmorItem']['Count'].value, \
                        entity['ArmorItem']['Damage'].value, "")
                items.append(armor_item)
                update_world_totals(armor_item)
            except KeyError:
                pass

            try:
                saddle_item = Item(entity['SaddleItem']['id'].value, \
                        entity['SaddleItem']['Count'].value, \
                        entity['SaddleItem']['Damage'].value, "")
                items.append(saddle_item)
                update_world_totals(saddle_item)
            except KeyError:
                pass

            if (verbose):
                inventories.append(Inventory(full_name, x, y, z, items))

    for entity in chunk['TileEntities']:
        full_name = entity['id'].value

        if full_name in valid_item_names or full_name in valid_mob_names:
            x = entity['x'].value
            y = entity['y'].value
            z = entity['z'].value

            try:
                items = items_from_nbt(entity['Items'], verbose)
            except KeyError:
                items = []

            if (verbose):
                inventories.append(Inventory(full_name, x, y, z, items))
    if (verbose):
        return inventories
    else:
        return []

def print_inv_contents(inventory, inv_f):
    """
    Writes all of inventory's data to f.

    :param inventory: the Inventory object to be written to inv_f
    :param inv_f: open file descriptor for writing inventory data
    """

    inv_writer = csv.writer(inv_f)

    for item in inventory.items:
        x_pos = '{0:.3f}'.format(inventory.x).rstrip('0').rstrip('.')
        y_pos = '{0:.3f}'.format(inventory.y).rstrip('0').rstrip('.')
        z_pos = '{0:.3f}'.format(inventory.z).rstrip('0').rstrip('.')
        inv_writer.writerow([\
                inventory.common_name, \
                x_pos, y_pos, z_pos, \
                item.common_name, item.lore, \
                item.damage, item.count\
                ])

def print_world_contents(world_f):
    """
    Writes the collective contents of the world to world_f.

    :param world_f: open file descriptor for writing total world count data
    """

    world_writer = csv.writer(world_f)
    for item in world_inv:
        world_writer.writerow([item.common_name, item.lore, item.damage, item.count])

def usage():
    print('<run | python2.7> inv_analysis.py <-i | --world> <world folder> [-v | --verbose | -h | --help]')

"""
def test(test_f):
    test_items = []
    test_items.append(Item('minecraft:test_item', 1, 0, ''))
    test_inv = Inventory('minecraft:test', 1000000000, 250, 1000000000000000, test_items)
    print_inv_contents(test_inv, test_f)
    test_inv = Inventory('minecraft:test', 0, 250, 100.02, test_items)
    print_inv_contents(test_inv, test_f)
"""

def main(argv):
    """
    Opens/closes file descriptors and goes through all chunks and player .dat files for inventory data.

    :param argv: command line arguments
    """
    world_folder = None
    verbose = False
    try:
        opts, args = getopt.getopt(argv, 'hvi:', ['help', 'verbose', 'world='])
    except getopt.GetoptError as err:
        print(str(err))
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif opt in ('-i', '--world'):
            world_folder = arg
        elif opt in ('-v', '--verbose'):
            verbose = True
        else:
            assert False, 'unhandled option'

    # clean path name, eliminate trailing slashes:
    if (world_folder is None):
        usage()
        sys.exit(1)
    else:
        world_folder = os.path.normpath(world_folder)

    # if folder exists, pass to NBT module
    if (not os.path.exists(world_folder)):
        print("No such folder as " + world_folder)
        sys.exit(1)
    else:
        world = WorldFolder(world_folder)

    now = datetime.datetime.now()
    timestamp = str(now.strftime('%Y%m%d_%H-%M-%S'))

    if (verbose):
        inv_contents_f = open('inv_contents_' + timestamp + '.csv', 'w')
        inv_writer = csv.writer(inv_contents_f)
        inv_writer.writerow(inv_content_headers)

    world_totals_f = open('world_contents_' + timestamp + '.csv',"w")
    world_writer = csv.writer(world_totals_f)
    world_writer.writerow(world_total_headers)

    """
    test_f = open('testing_scin_' + timestamp + '.csv',"w")
    test(test_f)
    """

    try:
        # get non-player inventories
        print('Finding non-player inventories by chunk...')
        for chunk in tqdm(world.iter_nbt()):
            for inventory in inventories_per_chunk(chunk["Level"], verbose):
                print_inv_contents(inventory, inv_contents_f)
        # get player inventories
        for root, dirs, files in tqdm(os.walk(world_folder)):
            print('Searching for player files and collecting inventories in ' + root)
            for file in files:
                if file.endswith(".dat") and len(file) == 40:
                    uuid = file[0:36]
                    p_inv = player_inv(uuid, os.path.join(root, file), verbose)
                    if (verbose):
                        print_inv_contents(p_inv, inv_contents_f)        # print world totals
        print_world_contents(world_totals_f)
    except KeyboardInterrupt:
        if (verbose):
            inv_contents_f.close()
        world_totals_f.close()
        sys.exit(1)

    if (verbose):
        inv_contents_f.close()
    world_totals_f.close()

    sys.exit(0)

if __name__ == '__main__':
    args = sys.argv
    if ('python' in args[0]):
        args = args[2:]
    elif ('run' in args[0]):
        args = args[2:]
    else:
        args = args[1:]
    main(args)
