from asyncio.events import TimerHandle
import time
from bot.mongodb import load_original_data_to
from bot.filefunction import get_absolute_file_path, get_server_data_file_name, update_local_server_file
import json
import logging
import os
import re
# import bson.json_util
import discord

# from json2html import *
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import database
from pymongo import collection

from bot import filefunction as botfile
from bot import github_api as gh
#my modules imports
from bot import mongodb
from cogs import auto_responder, server_info, basic, admin_config

#load .env
load_dotenv()

#constants
TOKEN = os.getenv('DISCORD_TOKEN_D')
DEFAULT_PREFIX = '?'

#decorator client
client = commands.Bot(command_prefix=DEFAULT_PREFIX, case_insensitive=True)


def client_update():
    # update live the code to get last data
    servers = client.guilds

    if not servers:
        print('no server yet')
        return

    server_ids = {}
    names = []

    server_id_file = 'clients-server-id.json'
    folder = 'data'
    users_file = 'clients-server-name-id.txt'

    if not os.path.exists(users_file):
        open(f'{get_absolute_file_path(folder, users_file)}', 'w')

    if not os.path.exists(server_id_file):
        open(f'{get_absolute_file_path(folder, server_id_file)}', 'w')

    timer = {}

    for server in servers:
        name = f'{server.name}-{server.id}'
        names.append(name)
        server_ids[server.name] = server.id
        timer[server.id] = 30

    if not os.path.exists(get_absolute_file_path('data', 'timer.json')):
        print('not in')
        json.dump(timer,
                  open(os.path.join(os.getcwd(), folder, 'timer.json'), 'w'),
                  indent=4)

    #update timer for servers
    updated_timers = json.load(
        open(get_absolute_file_path('data', 'timer.json')))
    for server in servers:
        if str(server.id) not in updated_timers.keys():
            updated_timers[server.id] = 30

    json.dump(updated_timers,
              open(os.path.join(os.getcwd(), folder, 'timer.json'), 'w'),
              indent=4)

    json.dump(
        server_ids,
        open(get_absolute_file_path(folder, server_id_file), 'w'),
        indent=4,
    )

    with open(f'{get_absolute_file_path(folder, users_file)}', 'w+') as f:
        for name in names:
            if name not in f.readlines():
                f.write(name + '\n')
        ids = json.load(
            open(get_absolute_file_path('data', 'clients-server-id.json')))

    collections = []

    for id in server_ids.values():
        filter_id = {'_id': int(id)}

        guildname = client.get_guild(id).name

        coll = mongodb.get_database_data(COLLECTION, filter_id)

        if coll:
            if coll['server name'] != guildname:
                update_database_data(filter_id, guildname, 'server name')

            collections.append(mongodb.get_database_data(
                COLLECTION, filter_id))

    for collection in collections:

        if collection:

            server_name, server_id = collection['server name'], collection[
                '_id']
            filename = get_server_data_file_name(server_name, server_id)
            if not os.path.exists(get_absolute_file_path(folder, filename)):
                open(f'{get_absolute_file_path(folder, filename)}', 'w')
            else:
                update_local_server_file(
                    collection, get_absolute_file_path(folder, filename))
            json.dump(collection,
                      open(get_absolute_file_path(
                          folder,
                          filename,
                      ), 'w'),
                      indent=4)
            try:
                gh.create_file_in_github_repo(f'data/{filename}', collection)
            except:
                print('File exists')
                continue
    #check local files has the same id if yes delete the older one
    delete_older_duplicate_file(folder)


def update_database_data(filter_id, value, key):

    temp_data = mongodb.get_database_data(COLLECTION, filter_id)
    COLLECTION.delete_one(filter_id)
    temp_data[key] = value
    COLLECTION.insert_one(temp_data)


def delete_older_duplicate_file(folder):
    stats = {}
    duplicates = []
    only_json = list(
        filter(
            lambda f: f.endswith('.json') and '-' in f and any(i.isdigit()
                                                               for i in f),
            os.listdir(os.path.join(os.getcwd(), folder))))

    for i in range(len(only_json) - 1):
        item = only_json[i]
        next_item = only_json[i + 1]

        id_ = re.search(r'-{1}([\d]+).json', item).group(1)
        id_next = re.search(r'-{1}([\d]+).json', next_item).group(1)

        if id_ == id_next:
            duplicates.append(item)
            duplicates.append(next_item)

    for duplicate in duplicates:
        creation_time = os.stat(
            os.path.join(get_absolute_file_path(folder, duplicate))).st_ctime
        stats[duplicate] = creation_time

    if (len(stats) > 1):
        minimum = min(stats.items(), key=lambda x: x[1])
        os.remove(os.path.join(os.getcwd(), folder, minimum[0]))


@client.event
async def on_guild_update(before, after):

    old_name = before.name
    new_name = after.name
    guild_id = after.id

    filter_id = {'_id': int(guild_id)}
    temp_data = mongodb.get_database_data(COLLECTION, filter_id)

    # update data when server name changes
    if old_name != new_name:

        # remove old data once from mongodb database filtered by id
        COLLECTION.delete_one({'_id': guild_id})
        old_file_name = botfile.get_server_data_file_name(old_name, guild_id)

        # load old json data file from my github repo

        # update old server name to the new one
        temp_data['server name'] = new_name

        old_path = botfile.get_absolute_file_path('data', old_file_name)
        # remove old local file
        os.remove(old_path)
        # delete from github repo

        gh.github_delete_file(f'data/{old_file_name}',
                              f'delete file: {old_file_name}')

        # create a new local file with the new name and dump the json data in it
        new_file_name = f'{botfile.get_server_data_file_name(new_name, guild_id)}'

        new_path = botfile.get_absolute_file_path('data', new_file_name)
        json.dump(
            temp_data,
            open(new_path, 'w'),
            sort_keys=True,
            indent=4,
        )

        sorted_data = json.load(open(new_path))
        #insert the data into the database
        COLLECTION.insert_one(sorted_data)

        # create the new file name in github repository
        gh.create_file_in_github_repo(f'data/{new_file_name}', temp_data)

        #update code
        client_update()


@client.event
async def on_ready():
    print('Bot is Ready')

    client_update()


@client.event
async def on_member_remove(member):
    await member.guild.system_channel.send(
        f'**{member}** has left the server :frowning:')


@client.event
async def on_member_join(member):

    await member.guild.system_channel.send(
        f'**{member}** has join the server :smile:')


@client.event
async def on_guild_join(guild):
    # when the bot join a server (guild)
    file_name = botfile.get_server_data_file_name(guild.name, guild.id)
    file_path = botfile.get_absolute_file_path('data', file_name)
    data = {'_id': int(guild.id), 'server name': guild.name}

    if not os.path.exists(file_path):

        # create local file with the data
        json.dump(
            data,
            open(file_path, 'w'),
            sort_keys=True,
            indent=4,
        )
    if not COLLECTION.find_one({'_id': int(guild.id)}):
        # insert the data to database and create a file in the github repo
        COLLECTION.insert_one(data)
        load_original_data_to(COLLECTION, f'{guild.name}-{guild.id}.json')

    client_update()


@client.event
async def on_guild_remove(guild):
    # when bot get's removed
    filename = get_server_data_file_name(guild.name, guild.id)
    try:
        os.remove(get_absolute_file_path('data', filename))
        gh.github_delete_file(f'data/{filename}', f'delete file: {filename}')
    except:
        print("can't delete file")
    print("Bot has been removed")


@client.event
async def on_member_join(member):
    pass
    # greet people when they join the server
    # await member.create_dm()
    # await member.dm_channel.send(
    #     f'Hi {member.name}, welcome to my Discord server!')


def load_cogs(path, folder):
    cogs = [i[:-3] for i in os.listdir(path) if i.endswith('.py')]
    for cog in cogs:

        client.load_extension(f'{folder}.{cog}')


def get_collection():
    return COLLECTION


CLIENT, COLLECTION = mongodb.get_database('triggers')

logging.basicConfig(filename='err.log', filemode='w', level=logging.INFO)

load_cogs(os.path.join(os.getcwd(), 'cogs'), 'cogs')

client.run(TOKEN)
CLIENT.close()