from bot.filefunction import get_json_data
from bot.mongodb import get_database, get_database_data
import discord
import bot.filefunction as botfile
import asyncio
from discord.ext import commands
from cogs.admin_config import get_guild_delete_timer


class Basic(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, ctx):
        # listen to every messages t    hat us ers type
        get_guild_delete_timer()
        if ctx.author == self.client.user:
            return
        timers = get_json_data('data', 'timer.json')
        delete_time = timers.get(str(ctx.guild.id), 30)
        print(get_guild_delete_timer())
        collection = get_database('triggers')[1]
        id_filter = {'_id': ctx.guild.id}

        cursor = get_database_data(collection, id_filter)
        trigger_response = {}

        if cursor:
            trigger_response = dict(cursor)

        msg = ctx.content.strip()
        if not msg.startswith(self.client.command_prefix):
            if msg in trigger_response.keys():
                embed = get_embed(msg, trigger_response[msg])
                await ctx.channel.send(embed=embed)
            else:
                trigger = botfile.get_clean_trigger_from(msg, trigger_response)

                if msg in trigger_response.keys(
                ) or botfile.is_user_response_valid(msg, trigger_response):

                    embed = get_embed(name=trigger,
                                      value=trigger_response[trigger])
                    await ctx.channel.send(
                        embed=embed, delete_after=get_guild_delete_timer())
                elif ctx.content == 'raise-exception':
                    raise discord.DiscordException


def get_embed(name='title', value='hey', color=discord.Colour.gold()):
    embed = discord.Embed(colour=color)
    embed.add_field(name=name, value=value)
    return embed


def setup(client):
    client.add_cog(Basic(client))