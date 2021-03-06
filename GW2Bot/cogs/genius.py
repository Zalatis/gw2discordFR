from .utils.chat_formatting import pagify
from discord.ext import commands
from tabulate import tabulate
from .utils.dataIO import dataIO
try:
    from bs4 import BeautifulSoup
    soupAvailable = True
except:
    soupAvailable = False
import discord
import aiohttp
import requests
import asyncio
import os


class Genius:

    def __init__(self, bot):
        self.bot = bot
        self.JSON = "data/Sitryk-Cogs/genius/settings.json"
        self.settings = dataIO.load_json(self.JSON)

    def save_settings(self):
        dataIO.save_json(self.JSON, self.settings)


    async def _update_event(self, method: str, ctx, data):
        self.bot.dispatch('genius_event', method, ctx, data)

    def _get_settings(self, ctx):
        server = ctx.message.server
        channel = ctx.message.channel
        if server.id not in self.settings:
            return DEFAULT
        else:
            return self.settings[server.id]

    def _data_check(self, ctx):
        server = ctx.message.server
        channel = ctx.message.channel
        if server.id not in self.settings:
            self.settings[server.id] = DEFAULT
            self.save_settings()

# Setting related commands

    @commands.group(pass_context=True)
    async def lyricset(self, ctx):
        """Change lyric related settings"""
        if ctx.invoked_subcommand is None:
            self._data_check(ctx)
            await self.bot.send_cmd_help(ctx)

    @lyricset.command(pass_context=True)
    async def channel(self, ctx, *, channel_name):
        """Set the channel for lyrics to be sent to
        Note: to reset default channel to DMs enter dms
        """
        self._data_check(ctx)
        server = ctx.message.server
        channel = discord.utils.find(lambda c: c.name.lower() == channel_name.lower(), server.channels)
        if channel:
            self.settings[server.id] = channel.id
        elif not channel and channel_name.lower() == "dms":
            self.settings[server.id] = None
        else:
            return
        self.save_settings()


    # @lyricset.command(pass_context=True, no_pm=True)
    # async def autolyrics(self, ctx):
    #     """Toggle the autolyrics feature"""
    #     self._data_check(ctx)
    #     server = ctx.message.server
    #     channel = ctx.message.channel
    #     AudioCog = self.bot.get_cog('Audio')
    #     if not AudioCog:
    #         self.settings[server.id]["AUTOLYRICS"] = False
    #         self.save_settings()
    #         await self.bot.say("You do not have the audio cog loaded.\n"
    #                            "Load the audio cog to enable this setting.")
    #         return
    #     else:
    #         self.settings[server.id]["AUTOLYRICS"] = not self.settings[server.id]["AUTOLYRICS"]
    #         self.save_settings()
    #         if self.settings[server.id]["AUTOLYRICS"]:
    #             await self.bot.say("I will now recommend lyrics depending on what is playing"
    #                                " from the audio cog")
    #         else:
    #             await self.bot.say("I will no longer recommend lyrics when audio is playing")

# Base commands start

    @commands.command(pass_context=True)
    async def lyrics(self, ctx, *, recherche: str):
        """Used to fetch lyrics from a search recherche
        Usage: [p]lyrics white ferrari
               [p]lyrics syrup sandwiches

        Tip: You can use '[p]lyrics now playing' to
        search for what's currently playing in audio
        """

        server = ctx.message.server
        author = ctx.message.author
        self._data_check(ctx)

        AudioCog = self.bot.get_cog('Audio')
        if AudioCog:
            if recherche in ("now playing", "audio", "current", "--p") and AudioCog.isplaying(server):
                recherche = AudioCog._get_queue_nowplaying(server).title

        data = await genius_search(recherche)

        if len(data) < 1:
            desc = "Pas de resultats pour {}".format(recherche)
            e = discord.Embed(description=desc, colour=discord.Colour.dark_red())
            await self.bot.say(embed=e)
            return


        items = ""
        for item in data:
            items += "**{}.** {} - {}\n\n".format(item,
                                                  data[item]['title'],
                                                  data[item]['artist']['name']
                                                  )

        authdesc = "Genius"
        footdesc = "Resultats pour la recherche: {}".format(recherche)

        choices = discord.Embed(description= items,
                                colour= discord.Color.green()
                                )
        choices.set_author(name=authdesc, icon_url=geniusicon)
        choices.set_footer(text=footdesc)

        try:
            sent = await self.bot.say(embed=choices)
        except discord.errors.Forbidden:
            await self.bot.say("I need the `Embed Messages` Permission")
            return


        def check(msg):
            content = msg.content
            if content.isdigit() and int(content) in range(0, len(items)+1):
                return msg

        choice = await self.bot.wait_for_message(timeout= 20, author= author,
                                                 check= check, channel= sent.channel)

        if choice is None or choice.content == '0':
            e = discord.Embed(description= "Cancelled", colour= discord.Colour.dark_red())
            await self.bot.edit_message(sent, embed=e)
            del(e)
            return
        else:
            choice = int(choice.content)

            destination = self.bot.get_channel(self._get_settings(ctx)["CHANNEL"])
            if destination is None:
                destination = author

            song = data[choice]['url']
            lyrics = await lyrics_from_path(song)
            lyrics = pagify(lyrics)


            t = data[choice]['title']
            a = data[choice]['artist']['name']

            e = discord.Embed(colour=16776960) # Aesthetics
            e.set_author(name="Requested lyrics for {} - {}".format(t, a), icon_url=loadgif)
            await self.bot.edit_message(sent, embed=e)
            del(e)

            e = discord.Embed(colour=discord.Colour.green()) # Aesthetics
            e.set_author(name="Here are the lyrics for {} - {}".format(t, a), icon_url=greentick)
            await self.bot.send_message(destination, embed=e)
            del(e)

            for page in lyrics: # Send the lyrics
                await self.bot.send_message(destination, page)

            e = discord.Embed(colour=discord.Colour.green()) # Aesthetics
            e.set_author(name="Sent lyrics for {} - {}".format(t, a), icon_url=greentick)
            await self.bot.edit_message(sent, embed=e)
            del(e)

    @commands.command(pass_context=True)
    async def genius(self, ctx, *, recherche: str):
        """Cherche les paroles d'une musique (ne marche pas en mp)
        Exemple: !genius Childish Gambino
                 !genius Kendrick Lamar
        """
        channel = ctx.message.channel
        server = ctx.message.server
        author = ctx.message.author
        self._data_check(ctx)

        bool_convert = {True: 'Yes',
                        False: 'No'
                        }

        AudioCog = self.bot.get_cog('Audio')
        if AudioCog:
            if recherche in ("now playing", "audio", "playing", "current") and AudioCog.isplaying(server):
                recherche = AudioCog._get_queue_nowplaying(server).title

        data = await genius_search(recherche)
        embeds = []

        song_selection = ""
        for item in data:

            stats = data[item]['stats']
            artist = data[item]['artist']

            iq = artist['iq']
            views = stats['views']
            artist_name = artist['name']
            song_type = data[item]['type'].title()
            title = data[item]['full title']
            hot = bool_convert[stats['hot']]
            verified = bool_convert[artist['verified']]


            # text = ("**Primary Artist:**  {}\n"
            #         "**Title:**                    {}\n" # I know this is super ugly but it deals with embed spacing issues
            #         "**IQ:**                         {}\n"
            #         "**Verified:**              {}\n"
            #         "**Views:**                  {}\n"
            #         "**Hot:**                       {}\n"
            #         "**Type:**                    {}".format(artist_name, title, iq, verified, views, hot, song_type))

            e = discord.Embed(colour=discord.Colour.green())
            e.add_field(name="Titre", value=title, inline=True)
            e.add_field(name="Artiste Principal", value=artist_name, inline=True)
            e.add_field(name="Vues", value=views, inline=True)
            e.add_field(name="Format", value=song_type, inline=True)
            e.set_thumbnail(url=data[item]['song art'])
            e.set_footer(text="Page {} - Recherche: {}".format(item, recherche))
            embeds.append(e)

        await self.genius_menu(ctx, recherche_list=embeds, extra_data=data)

# Lunars menu control

    async def genius_menu(self, ctx, recherche_list: list, extra_data: dict,
                          message: discord.Message=None,
                          page=0, timeout: int=30):
        """
        Viens de
        https://github.com/Lunar-Dust/Dusty-Cogs/blob/master/menu/menu.py
        """

        key = page+1
        title = extra_data[key]['title']
        artist = extra_data[key]['artist']['name']
        author = ctx.message.author
        channel = ctx.message.channel
        server = ctx.message.server

        recherche = recherche_list[page]

        if not message:
            message = await self.bot.send_message(channel, embed=recherche)
            await self.bot.add_reaction(message, "⬅")
            await self.bot.add_reaction(message, "🎶")
            await self.bot.add_reaction(message, "❌")
            #await self.bot.add_reaction(message, "▶")
            await self.bot.add_reaction(message, "➡")
        else:
            message = await self.bot.edit_message(message, embed=recherche)

        react = await self.bot.wait_for_reaction(message=message,
                                                 user=ctx.message.author,
                                                 timeout=timeout,
                                                 emoji=["➡", "⬅", "❌", "🎶", "▶"]
                                                 )
        if react is None:
            try:
                try:
                    await self.bot.clear_reactions(message)
                except:
                    await self.bot.remove_reaction(message, "⬅", self.bot.user)
                    await self.bot.remove_reaction(message, "🎶", self.bot.user)
                    await self.bot.remove_reaction(message, "❌", self.bot.user)
                    #await self.bot.remove_reaction(message, "▶", self.bot.user)
                    await self.bot.remove_reaction(message, "➡", self.bot.user)
            except:
                pass
            return None

        reacts = {v: k for k, v in numbs.items()}
        react = reacts[react.reaction.emoji]

        if react == "next":
            page += 1
            next_page = page % len(recherche_list)
            try:
                await self.bot.remove_reaction(message, "➡", author)
            except:
                pass

            return await self.genius_menu(ctx, recherche_list, extra_data, message=message,
                                          page=next_page, timeout=timeout)

        elif react == "back":
            page -= 1
            next_page = page % len(recherche_list)
            try:
                await self.bot.remove_reaction(message, "⬅", author)
            except:
                pass

            return await self.genius_menu(ctx, recherche_list, extra_data, message=message,
                                          page=next_page, timeout=timeout)

        elif react == "request lyrics":
            try:
                try:
                    await self.bot.clear_reactions(message)
                except:
                    await self.bot.remove_reaction(message, "⬅", self.bot.user)
                    await self.bot.remove_reaction(message, "🎶", self.bot.user)
                    await self.bot.remove_reaction(message, "❌", self.bot.user)
                    await self.bot.remove_reaction(message, "▶", self.bot.user)
                    await self.bot.remove_reaction(message, "➡", self.bot.user)
            except:
                pass

            e = discord.Embed(colour=16776960)
            e.set_author(name="Recherche des lyrics pour {} - {}".format(artist, title), icon_url=loadgif)
            await self.bot.edit_message(message, embed= e)

            destination = self.bot.get_channel(self._get_settings(ctx)["CHANNEL"])
            if destination is None:
                destination = author

            lyrics = await lyrics_from_path(extra_data[page+1]['url'])
            lyrics = pagify(lyrics)
            for p in lyrics:
                await self.bot.send_message(destination, p)

            e = discord.Embed(colour=discord.Colour.green())
            e.set_author(name="Envoi des lyrics pour {} - {}".format(artist, title), icon_url=greentick)
            await self.bot.edit_message(message, embed=e)

        # elif react == "queue in audio":
        #     AudioCog = self.bot.get_cog('Audio')
        #     if not AudioCog:
        #         e = discord.Embed(description="ERROR: Audio module not loaded", colour=discord.Colour.red())
        #         await self.bot.edit_message(message, embed=e)
        #         await self.bot.delete_message(message)
        #         return

        #     search = extra_data[page+1]['full title']

        #     e = discord.Embed(colour=16776960)
        #     e.set_author(name="Searching youtube for {}".format(search), icon_url=loadgif)
        #     await self.bot.edit_message(message, embed= e)


        #     try:
        #         await self.bot.remove_reaction(message, "▶", author)
        #     except:
        #         pass
        #     try:
        #         try:
        #             await self.bot.clear_reactions(message)
        #         except:
        #             await self.bot.remove_reaction(message, "⬅", self.bot.user)
        #             await self.bot.remove_reaction(message, "🎶", self.bot.user)
        #             await self.bot.remove_reaction(message, "❌", self.bot.user)
        #             await self.bot.remove_reaction(message, "▶", self.bot.user)
        #             await self.bot.remove_reaction(message, "➡", self.bot.user)
        #     except:
        #         pass
        #     await ctx.invoke(AudioCog.play, ctx=ctx, url_or_search_terms=search)

        #     e = discord.Embed(colour=16776960)
        #     e.set_author(name="Queued <youtube title> {}".format(search), icon_url=loadgif)
        #     await self.bot.edit_message(message, embed= e)

        else:
            return await self.bot.delete_message(message)



# Constants

numbs = {
"next": "➡",
"request lyrics" : "🎶",
"queue in audio" : "▶",
"back": "⬅",
"exit": "❌"
        }

DEFAULT = {"CHANNEL": None,
           "AUTOLYRICS": False}

loadgif = "https://i.pinimg.com/originals/58/4b/60/584b607f5c2ff075429dc0e7b8d142ef.gif"
greentick = "https://vignette.wikia.nocookie.net/universal-crusade/images/5/5a/Checkmark.png"
geniusicon = "https://images.genius.com/8ed669cadd956443e29c70361ec4f372.1000x1000x1.png"

headers = {'Authorization': 'Bearer Dbe3uX9k-zs0OHK-ExjIMdsAVpIMuY-DQI0NEe8TGITQsnqn4TvSbOqOIuIfxZzf'}
api_url = "https://api.genius.com"


# Genius related functions

async def lyrics_from_path(path):
    """Gets the lyrics from a song path"""

    with requests.get(path) as page:
        html = BeautifulSoup(page.text, "html.parser")
        [h.extract() for h in html('script')]
        lyrics = html.find("div", class_="lyrics").get_text()
        return lyrics




async def genius_search(recherche:str):
    """Get the data from the genius api"""

    search_url = api_url + "/search"
    data = {'q': recherche}
    json = None
    async with aiohttp.get(search_url, data=data, headers=headers) as r:
        json = await r.json()

    the_dict = {}
    for index, hit in enumerate(json['response']['hits']):

        try:
            iq = str(hit['result']['primary_artist']['iq'])
        except KeyError:
            iq = "0"
        try:
            views = str(hit['result']['stats']['pageviews'])
        except KeyError:
            views = "0"


        the_dict[index+1] = {
                            'type' : hit['type'],
                            'api path' : hit['result']['api_path'],
                            'annotations' : hit['result']['annotation_count'],
                            'title' : hit['result']['title'],
                            'full title' : hit['result']['full_title'],
                            'header image' : hit['result']['header_image_url'],
                            'url' : hit['result']['url'],
                            'song art' : hit['result']['song_art_image_thumbnail_url'],
                            'artist' : {'name' : hit['result']['primary_artist']['name'],
                                        'url' : hit['result']['primary_artist']['url'],
                                        'iq' : iq,
                                        'meme verified' : hit['result']['primary_artist']['is_meme_verified'],
                                        'verified' : hit['result']['primary_artist']['is_verified'],
                                        'profile picture' : hit['result']['primary_artist']['image_url']
                                        },
                            'stats' : {
                                       'hot' : hit['result']['stats']['hot'],
                                       'views' : views
                                        }
                            }
    return the_dict

# Cog setup

def check_folders():
    path = "data/Sitryk-Cogs/genius"
    if not os.path.exists(path):
        print("Creating {} folder...".format(path))
        os.makedirs(path)

def check_files():

    f = "data/Sitryk-Cogs/genius/settings.json"
    if not dataIO.is_valid_json(f):
        print("Creating default settings.json...")
        dataIO.save_json(f, {})


def setup(bot):
    if soupAvailable:
        check_folders()
        check_files()
        n = Genius(bot)
        bot.add_cog(n)
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")
