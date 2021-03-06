from discord.ext import commands
from .utils import checks
from .utils.dataIO import dataIO
from datetime import datetime as dt
from datetime import timedelta, timezone
import asyncio
import aiohttp
import discord
import os
import calendar
import pytz
import re
import collections

# numbs = collections.OrderedDict()
# ⤴ -> join
# ⤵ -> leave
numbs = {
    "next": "➡",
    "back": "⬅",
    "exit": "❌",
    "join": "⤴",
    "leave": "⤵"
}

gametype = {
    "PvE": "🇪",  # E
    "PvP": "🇵",  # P
}

pvp_activity = collections.OrderedDict()
pvp_activity["Casual - PvP"] = "⚒"
pvp_activity["Classé - PvP"] = "⚔"
pvp_activity["Entraînement"] = "🥇"
pvp_activity["McM - PvP"] = "🌍"
pvp_activity["Autre - PvP"] = "🇦"

pve_activity = collections.OrderedDict()
pve_activity["Donjon"] = "🇩"     # D
pve_activity["Raid"] = "🇷"       # R
pve_activity["Missions"] = "🇲"   # M
pve_activity["Farm"] = "🇫"       # F
pve_activity["Autre"] = "🇦"      # A

# Define timezones
paris = pytz.timezone('Europe/Paris')

lfg_messages = []

""" Cog basé fortement sur
    https://github.com/palmtree5/palmtree5-cogs/blob/master/eventmaker/eventmaker.py
    Le Cog a été modifié pour mieux collé à une utilisation
    pour les jeux en ligne."""


class EventMaker():
    """Est un tool pour créer des events pour
    des jeux en ligne et ainsi facilité les rappels
    lors d'un event important en fonction des goûts de
    chacun. Seuls les modos, admins et propriétaire du serveur
    en question peuvent en créer les rappels ce font de base
    dans le canal par défaut du serveur ainsi qu'en message
    privé à chaque personne qui le rejoint"""
    def __init__(self, bot):
        self.bot = bot
        self.events = dataIO.load_json(
            os.path.join("data", "eventmaker", "events.json"))
        self.settings = dataIO.load_json(
            os.path.join("data", "eventmaker", "settings.json"))

    async def select_menu(self, ctx, emoji_dict: dict,
                          text: str, timeout: int=30):
        emb = discord.Embed(title=text,
                            color=discord.Colour(0xf1c40f))
        # for name in emoji_dict:
        #     emb.add_field(
        #         name=emoji_dict[name], value=name)
        bot_msg = await self.bot.send_message(ctx.message.channel, embed=emb)
        await self.bot.add_reaction(bot_msg, "⬅")
        await self.bot.add_reaction(bot_msg, "❌")
        await self.bot.add_reaction(bot_msg, "➡")
        react = await self.bot.wait_for_reaction(
            message=bot_msg, user=ctx.message.author, timeout=timeout,
            emoji=["➡", "⬅", "❌"]
        )
        return bot_msg
        # for name in emoji_dict:
        #     await self.bot.add_reaction(bot_msg, emoji_dict[name])
        # react = await self.bot.wait_for_reaction(
        #     message=bot_msg, user=ctx.message.author, timeout=timeout,
        #     emoji=emoji_dict.values()
        # )
        # if react is None:
        #     for name in emoji_dict:
        #         await self.bot.remove_reaction(bot_msg, emoji_dict[name], self.bot.user)
        #     return None
        # reacts = {v: k for k, v in emoji_dict.items()}
        # return reacts[react.reaction.emoji]

    async def games_menu(self, ctx, event_list: list,
                         message: discord.Message=None,
                         page=0, timeout: int=30):
        """Logique de contrôle de menu pour cela prise de
           https://github.com/Lunar-Dust/Dusty-Cogs/blob/master/menu/menu.py """
        emb = event_list[page]
        emb_dict = emb.to_dict()
        if not message:
            message =\
                await self.bot.send_message(ctx.message.channel, embed=emb)
            await self.bot.add_reaction(message, "⬅")
            await self.bot.add_reaction(message, "⤴")
            await self.bot.add_reaction(message, "❌")
            await self.bot.add_reaction(message, "⤵")
            await self.bot.add_reaction(message, "➡")
        else:
            message = await self.bot.edit_message(message, embed=emb)
        react = await self.bot.wait_for_reaction(
            message=message, user=ctx.message.author, timeout=timeout,
            emoji=["➡", "⬅", "❌", "⤴", "⤵"]
        )
        if react is None:
            await self.bot.remove_reaction(message, "⬅", self.bot.user)
            await self.bot.remove_reaction(message, "⤴", self.bot.user)
            await self.bot.remove_reaction(message, "❌", self.bot.user)
            await self.bot.remove_reaction(message, "⤵", self.bot.user)
            await self.bot.remove_reaction(message, "➡", self.bot.user)
            await self.bot.delete_message(message)
            return None
        reacts = {v: k for k, v in numbs.items()}
        react_user = react.user
        react = reacts[react.reaction.emoji]
        if react == "next":
            next_page = 0
            if page == len(event_list) - 1:
                next_page = 0  # Loop around to the first item
            else:
                next_page = page + 1
            return await self.games_menu(ctx, event_list, message=message,
                                         page=next_page, timeout=timeout)
        elif react == "back":
            next_page = 0
            if page == 0:
                next_page = len(event_list) - 1  # Loop around to the last item
            else:
                next_page = page - 1
            return await self.games_menu(ctx, event_list, message=message,
                                         page=next_page, timeout=timeout)
        elif react == "join":
            await self.bot.say("Vous avez rejoint l'event!")
            test_server = ctx.message.server
            id_field = next(item for item in emb_dict['fields'] if item["name"] == "ID")
            curr_id = int(id_field['value'])
            # for key, value, in emb_dict.items():
            #     print (key, value)
            await self.addplayer(ctx, react_user, curr_id, ctx.message.channel)
            await self.list_games(ctx)
            # return await event_list(ctx)
            return await\
                self.bot.delete_message(message)
        elif react == "leave":
            await self.bot.say("Vous avez quitté l'event.")
            test_server = ctx.message.server
            id_field = next(item for item in emb_dict['fields'] if item["name"] == "ID")
            curr_id = int(id_field['value'])
            await self.removeplayer(ctx, react_user, curr_id, message.channel)
            await self.list_games(ctx)
            # return await event_list(ctx)
            return await\
                self.bot.delete_message(message)
        else:
            return await\
                self.bot.delete_message(message)

    async def event_menu(self, ctx, event_emb: discord.Embed,
                         player_str: str,
                         channel,
                         message: discord.Message=None):
        """Logique de contrôle du menu source:
           https://github.com/Lunar-Dust/Dusty-Cogs/blob/master/menu/menu.py """
        emb = event_emb
        emb_dict = emb.to_dict()
        id_field = next(item for item in emb_dict['fields'] if item["name"] == "ID")
        curr_id = int(id_field['value'])
        if not message:
            message =\
                await self.bot.send_message(channel, embed=emb)
            await self.bot.add_reaction(message, "⤴")
            await self.bot.add_reaction(message, "⤵")
        else:
            message = await self.bot.edit_message(message, embed=emb)
        await asyncio.sleep(1)
        react = await self.bot.wait_for_reaction(
            message=message,
            emoji=["⤴", "⤵"]
        )
        # if react is None:
        #     await self.bot.remove_reaction(message, "⤴", self.bot.user)
        #     await self.bot.remove_reaction(message, "❌", self.bot.user)
        #     await self.bot.remove_reaction(message, "⤵", self.bot.user)
        #     await self.bot.delete_message(message)
        #     return None
        await self.bot.remove_reaction(message, react.reaction.emoji, react.user)
        reacts = {v: k for k, v in numbs.items()}
        react_user = react.user
        print(react_user)
        react = reacts[react.reaction.emoji]
        print(react_user)
        if react == "join":
            await self.addplayer(ctx, react_user, curr_id, channel)
            emb.remove_field(3)  # Remove players
            player_name = react_user.name + " "
            if player_str == "Pas de participants":
                player_str = ""
            player_str = player_str + player_name
            emb.add_field(
                name="Participants", value=player_str)
            # await self.list_games(ctx)
            return await self.event_menu(ctx, emb, player_str, channel, message=message)
        #     return await\
        #         self.bot.delete_message(message)
        elif react == "leave":
            await self.removeplayer(ctx, react_user, curr_id, channel)
            emb.remove_field(3)  # Remove players
            player_name = react_user.name + " "
            player_str = player_str.replace(player_name, "")
            if player_str == "":
                player_str = "Pas de participants"
            emb.add_field(
                name="Participants", value=player_str)
            # await self.list_games(ctx)
            return await self.event_menu(ctx, emb, player_str, channel, message=message)
        #     return await\
        #         self.bot.delete_message(message)
        # else:
        #     return await\
        #         self.bot.delete_message(message)

    @commands.command(pass_context=True)
    async def event_add(self, ctx):
        """Planifie un event futur"""
        author = ctx.message.author
        server = ctx.message.server
        await self.bot.delete_message(ctx.message)
        allowed_roles = []
        server_owner = server.owner
        if server.id in self.settings:
            if self.settings[server.id]["role"] is not None:
                specified_role =\
                    [r for r in server.roles if r.id == self.settings[server.id]["role"]][0]
                allowed_roles.append(specified_role)
                allowed_roles.append(self.bot.settings.get_server_mod(server))
                allowed_roles.append(self.bot.settings.get_server_admin(server))

        if len(allowed_roles) > 0 and author != server_owner:
            for role in author.roles:
                if role in allowed_roles:
                    break
            else:
                await self.bot.say("Vous n'avez pas la permission de créer des events!")
                return

        creation_time = dt.utcnow()
        creation_time = calendar.timegm(creation_time.utctimetuple())
        #################################
        # Obtient le nom de l'event #
        #################################
        bot_msg = await self.bot.say("Entrez un nom pour l'event: ")
        rsp_msg = await self.bot.wait_for_message(author=author, timeout=30)
        if rsp_msg is None:
            await self.bot.say("Aucun nom fourni!")
            return
        game_name = rsp_msg.content
        await self.bot.delete_message(bot_msg)
        await self.bot.delete_message(rsp_msg)
        ###########################
        # Obtient la description  #
        ###########################
        # bot_msg = None
        # rsp_msg = None
        bot_msg = await self.bot.say("Entrez une description pour l'event: ")
        rsp_msg = await self.bot.wait_for_message(author=author, timeout=30)
        if rsp_msg is None:
            await self.bot.say("Aucune description fournie!")
            return
        if len(rsp_msg.content) > 750:
            await self.bot.say("Votre description est trop longue!")
            return
        else:
            desc = rsp_msg.content
        await self.bot.delete_message(bot_msg)
        await self.bot.delete_message(rsp_msg)
        #############################################
        # Sélectionne le type d'activité de l'event #
        #############################################
        # bot_msg = None
        # rsp_msg = None
        menu_str = "Sélectionne un type d'event"
        #  react = self.select_menu(ctx, gametype, menu_str, timeout=30)
        emb = discord.Embed(title=menu_str,
                            color=discord.Colour(0xf1c40f))
        for name in gametype:
            emb.add_field(
                name=gametype[name], value=name)
        bot_msg = await self.bot.send_message(ctx.message.channel, embed=emb)
        for name in gametype:
            await self.bot.add_reaction(bot_msg, gametype[name])
        react = await self.bot.wait_for_reaction(
            message=bot_msg, user=ctx.message.author, timeout=30,
            emoji=gametype.values()
        )
        if react is None:
            # for name in gametype:
            #     await self.bot.remove_reaction(bot_msg, gametype[name], self.bot.user)
            await self.bot.delete_message(bot_msg)
            await self.bot.say("Aucun type d'event sélectionné!")
            return None
        reacts = {v: k for k, v in gametype.items()}
        activity_group = reacts[react.reaction.emoji]
        # await self.bot.remove_reaction(bot_msg, gametype[activity_group], react.user)
        await self.bot.delete_message(bot_msg)
        await self.bot.say(reacts[react.reaction.emoji])
        ###################################
        # Sélectionne le genre d'activité #
        ###################################
        # bot_msg = None
        # rsp_msg = None
        menu_str = "Sélectionne le genre d'activité"
        if activity_group == "PvE":
            emb = discord.Embed(title=menu_str,
                                color=discord.Colour(0x1f8b4c))
            activity_group_dict = pve_activity
        else:
            emb = discord.Embed(title=menu_str,
                                color=discord.Colour(0x992d22))
            activity_group_dict = pvp_activity
        for name in activity_group_dict:
            emb.add_field(
                name=activity_group_dict[name], value=name, inline=False)
        bot_msg = await self.bot.send_message(ctx.message.channel, embed=emb)
        for name in activity_group_dict:
            await self.bot.add_reaction(bot_msg, activity_group_dict[name])
        react = await self.bot.wait_for_reaction(
            message=bot_msg, user=ctx.message.author, timeout=30,
            emoji=activity_group_dict.values()
        )
        if react is None:
            await self.bot.delete_message(bot_msg)
            await self.bot.say("Aucun genre d'activité sélectionné!")
            return None
        reacts = {v: k for k, v in activity_group_dict.items()}
        activity_type = reacts[react.reaction.emoji]
        await self.bot.delete_message(bot_msg)
        await self.bot.say(activity_type)
        #############################################
        # Obtient la date et l'heure de l'event #
        #############################################
        # bot_msg = None
        # rsp_msg = None
        bot_msg = await self.bot.say(
            "Entrez l'heure et la date (Format: HH:MM le JJ/MM) ")
        rsp_msg = await self.bot.wait_for_message(author=author, timeout=45)
        if rsp_msg is None:
            await self.bot.delete_message(bot_msg)
            bot_msg = await self.bot.say("Pas de date donnée")
            await asyncio.sleep(10)
            await self.bot.delete_message(bot_msg)
            return
        start_time = self.game_time(rsp_msg)
        if start_time is None:
            await self.bot.delete_message(bot_msg)
            bot_msg = await self.bot.say("Quelque chose s'est mal passé lors de l'analyse de la date donnée")
            await asyncio.sleep(10)
            await self.bot.delete_message(bot_msg)
            await self.bot.delete_message(rsp_msg)
            return
        if start_time < creation_time:
            await self.bot.delete_message(bot_msg)
            bot_msg = await self.bot.say("Vous avez entrée une date dans le passé")
            await asyncio.sleep(10)
            await self.bot.delete_message(bot_msg)
            await self.bot.delete_message(rsp_msg)
            return
        await self.bot.delete_message(bot_msg)
        await self.bot.delete_message(rsp_msg)

        new_event = {
            "id": self.settings[server.id]["next_id"],
            "creator": author.id,
            "create_time": creation_time,  # calendar.timegm(creation_time.utctimetuple()),
            "event_name": game_name,
            "activity": activity_type,
            "event_start_time": start_time,
            "description": desc,
            "alert": False,
            "has_started": False,
            "participants": [author.id]
        }
        self.settings[server.id]["next_id"] += 1
        self.events[server.id].append(new_event)
        dataIO.save_json(os.path.join(
            "data", "eventmaker", "settings.json"), self.settings)
        dataIO.save_json(
            os.path.join("data", "eventmaker", "events.json"), self.events)
        emb = discord.Embed(title=new_event["event_name"],
                            description=new_event["description"],
                            color=discord.Colour(0x206694))
        # emb.add_field(name="Créé par",
        #               value=discord.utils.get(
        #                   self.bot.get_all_members(),
        #                   id=new_event["creator"]))
        # emb.add_field(name="Créé par",
        #               value=author.name)
        emb.set_footer(
            text="Créé le: " + dt.fromtimestamp(
                new_event["create_time"], paris).strftime("%d/%m/%Y %R") +
                        " par " + author.name)
        emb.add_field(
            name="Activité: ", value=new_event["activity"])
        emb.add_field(
            name="Début de l'event: ", value=dt.fromtimestamp(
                new_event["event_start_time"], paris).strftime("le %d/%m à %R"))
        emb.add_field(name="ID", value=str(new_event["id"]))
        await self.bot.say(embed=emb)
        await self.list_games(ctx)

    @commands.command(pass_context=True)
    async def event_join(self, ctx, event_id: int):
        """Rejoint l'event"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if ctx.message.author.id not in event["participants"]:
                        event["participants"].append(ctx.message.author.id)
                        await self.bot.say("Vous vous êtes inscrit à l'event!")
                        dataIO.save_json(
                            os.path.join("data", "eventmaker", "events.json"),
                            self.events)
                    else:
                        await self.bot.say("Vous avez déjà rejoint cet event!")
                else:
                    await self.bot.say("Cet event a déjà commencé!")
                break
        else:
            await self.bot.say("Il semblerait que cet event n'existe pas!" +
                               "Peut-être a-t-il été annulé ou jamais créé?")

    async def addplayer(self, ctx, user, event_id: int, channel):
        """Ajoute un joueur à l'event donné"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if user.id not in event["participants"]:
                        event["participants"].append(user.id)
                        # await self.bot.say("Joined the event!")
                        dataIO.save_json(
                            os.path.join("data", "eventmaker", "events.json"),
                            self.events)
                    else:
                        # await self.bot.say("Vous avez déjà rejoint cet event")
                        await self.bot.send_message(channel, "Vous avez déjà rejoint cet event!")
                else:
                    # await self.bot.say("Cet event a déjà commencé!")
                    await self.bot.send_message(channel, "Cet event a déjà commencé!")
                break
        else:
            # await self.bot.say("Il semblerait que cet event n'existe pas!" +
            #                    "Peut-être a-t-il été annulé ou jamais créé?")
            await self.bot.send_message(channel, "Il semblerait que cet event n'existe pas!" +
                                        "Peut-être a-t-il été annulé ou jamais créé?")

    @commands.command(pass_context=True)
    async def event_leave(self, ctx, event_id: int):
        """Quitte l'event spécifié"""
        server = ctx.message.server
        author = ctx.message.author
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if author.id in event["participants"]:
                        event["participants"].remove(author.id)
                        await self.bot.say("Vous avez quitté cet event!")
                        dataIO.save_json(
                            os.path.join("data", "eventmaker", "events.json"),
                            self.events)
                    else:
                        await self.bot.say(
                            "Vous n'êtes pas inscrit à cet event!")
                else:
                    await self.bot.say("Cet event a déjà commencé!")
                break

    async def removeplayer(self, ctx, user, event_id: int, channel):
        """Quitte l'event spécifié pour le joueur"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if user.id in event["participants"]:
                        event["participants"].remove(user.id)
                        # await self.bot.say("Vous avez été retiré de l'event!")
                        await self.bot.send_message(channel, "Vous avez été retiré de l'event!")
                        dataIO.save_json(
                            os.path.join("data", "eventmaker", "events.json"),
                            self.events)
                    else:
                        # await self.bot.say(
                        #    "Vous n'êtes pas inscrit à cet event")
                        await self.bot.send_message(channel,
                                                    "Vous n'êtes pas inscrit à cet event.")
                else:
                    # await self.bot.say("Cet event a déjà commencé.")
                    await self.bot.send_message(channel, "Cet event a déjà commencé.")
                break
        else:
            # await self.bot.say("It appears as if that event does not exist!" +
            #                    "Perhaps it was cancelled or never created?")
            await self.bot.send_message(channel, "Il semblerait que cet event n'existe pas!" +
                                        "Peut-être a-t-il été annulé ou jamais créé?")

    @commands.command(pass_context=True)
    async def event_list(self, ctx, *, timezone: str="Europe/Paris"):
        """Liste les events qui n'ont pas commencé"""
        server = ctx.message.server
        events = []
        for event in self.events[server.id]:
            if not event["has_started"]:
                pt_str = dt.fromtimestamp(
                    event["create_time"], paris).strftime("%d/%m à %R")
                emb = discord.Embed(title=event["event_name"],
                                    description=event["description"],
                                    color=discord.Colour(0x206694))
                # emb.add_field(name="Créé par",
                #               value=(discord.utils.get(
                #                   self.bot.get_all_members(),
                #                   id=event["creator"])).name)
                emb.add_field(
                    name="Activité: ", value=event["activity"])
                # emb.set_footer(
                #     text="Créé le " + dt.fromtimestamp(
                #         event["create_time"], paris).strftime("%d/%m/%Y %R"))
                emb.set_footer(
                    text="Créé le: " + pt_str)
                emb.add_field(
                    name="Début de l'event: ", value=dt.fromtimestamp(
                        event["event_start_time"], paris).strftime("le %d/%m à %R"))
                emb.add_field(name="ID", value=str(event["id"]))
                player_str = ""
                for user in event["participants"]:
                    target = (discord.utils.get(
                        self.bot.get_all_members(), id=user)).name
                    player_str += target + " "
                # emb.add_field(
                #     name="Participants", value=str(
                #         len(event["participants"])))
                if player_str == "":
                    player_str = "Pas de participants"
                emb.add_field(
                    name="Participants", value=player_str)
                # emb.add_field(
                #     name="Heure de début", value=dt.fromtimestamp(
                #         event["event_start_time"], paris).strftime("%d/%m/%Y %R"))
                events.append(emb)
        if len(events) == 0:
            await self.bot.say("Aucun event disponible.")
        else:
            await self.games_menu(ctx, events, page=0, timeout=30)

    @commands.command(pass_context=True)
    async def who(self, ctx, event_id: int):
        """Liste tous les participants de l'event"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    for user in event["participants"]:
                        user_obj = discord.utils.get(
                            self.bot.get_all_members(), id=user)
                        await self.bot.say("{}#{}".format(
                            user_obj.name, user_obj.discriminator))
                else:
                    await self.bot.say("Cet événement a déjà commencé!")
                break

    @commands.command(pass_context=True)
    async def event_cancel(self, ctx, event_id: int):
        """Annule l'event spécifié"""
        server = ctx.message.server
        if event_id < self.settings[server.id]["next_id"]:
            to_remove =\
                [event for event in self.events[server.id] if event["id"] == event_id]
            if len(to_remove) == 0:
                await self.bot.say("Aucun event a annulé.")
            else:
                self.events[server.id].remove(to_remove[0])
                dataIO.save_json(
                    os.path.join("data", "eventmaker", "events.json"),
                    self.events)
                await self.bot.say("Event supprimé")
        else:
            await self.bot.say("Je ne peux pas supprimer un événement qui " +
                               "n'a pas encore été créé!")

    def game_time(self, msg: discord.Message):
        """Calcul de l'heure"""
        # start_time = calendar.timegm(cur_time.utctimetuple())
        content = msg.content
        # MET = timezone(timedelta(hours=+2))
        try:
            t, tzone, d = content.split(" ")
            hour, minute = t.split(":")
            day, month = d.split("/")
            # Définit un fuseau horaire
            tzone = tzone.lower()
            if re.match("le", tzone) is not None:
                tzone = paris
            else:
                raise ValueError('Fuseau horaire incorrect ou non pris en charge')
            #  start_time = dt(2018, int(month), int(day), int(hour), int(minute), tzinfo=tzone)
            start_time = dt(2018, int(month), int(day), int(hour), int(minute))
            start_time = tzone.localize(start_time)
            start_time = calendar.timegm(start_time.utctimetuple())
        except ValueError:
            return None  # problème avec l'entrée de l'utilisateur
        return start_time

    @commands.group(pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def event_setup(self, ctx):
        """Paramètres de l'event"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @event_setup.command(pass_context=True, name="channel")
    @checks.admin_or_permissions(manage_server=True)
    async def game_set_channel(self, ctx, channel: discord.Channel):
        """Définit le canal utilisé pour afficher des rappels."""
        server = ctx.message.server
        self.settings[server.id]["channel"] = channel.id
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"),
                         self.settings)
        await self.bot.say("Canal défini sur {}".format(channel.mention))

    @event_setup.command(pass_context=True, name="defaut_channel")
    @checks.admin_or_permissions(manage_server=True)
    async def game_set_defaut_channel(self, ctx, channel: discord.Channel):
        """Définit le canal d'affichage par défaut
        Par défaut, le canal par défaut du serveur est utilisé"""
        server = ctx.message.server
        self.settings[server.id]["defaut_channel"] = channel.id
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"),
                         self.settings)
        await self.bot.say("Canal défini sur {}".format(channel.mention))

    @event_setup.command(pass_context=True, name="role")
    @checks.admin_or_permissions(manage_server=True)
    async def game_set_role(self, ctx, *, role: str=None):
        """Définit le rôle nécessaire pour créer des events
        Par défaut tout le monde peut en créer"""
        server = ctx.message.server
        if role is not None:
            role_obj = [r for r in server.roles if r.name == role][0]
            self.settings[server.id]["role"] = role_obj.id
            dataIO.save_json(
                os.path.join("data", "eventmaker", "settings.json"),
                self.settings)
            await self.bot.say("Rôle défini sur {}".format(role))
        else:
            self.settings[server.id]["role"] = None
            dataIO.save_json(
                os.path.join("data", "eventmaker", "settings.json"),
                self.settings)
            await self.bot.say("Rôle désactivé!")

    async def post_event(self, ctx, event, channel):
        emb = discord.Embed(title=event["event_name"],
                            description=event["description"],
                            color=discord.Colour(0x206694))
        emb.add_field(
            name="Activité: ", value=event["activity"])
        pt_str = dt.fromtimestamp(
            event["create_time"], paris).strftime("le %d/%m à %R")
        emb.add_field(
            name="Début de l'event: ", value=dt.fromtimestamp(
                event["event_start_time"], paris).strftime("le %d/%m à %R"))
        emb.set_footer(
            text="Créé le: " +
            dt.fromtimestamp(
                event["create_time"], paris).strftime(
                    "%d/%m/%Y à %R"))
        emb.add_field(name="ID", value=str(event["id"]))
        player_str = ""
        for user in event["participants"]:
            target = discord.utils.get(
                self.bot.get_all_members(), id=user)
            player_str += target.name + " "
        if player_str == "":
            player_str = "Pas de participants"
        emb.add_field(
            name="Participants", value=player_str)
        # await self.bot.send_message(channel, embed=emb)
        await self.event_menu(ctx, emb, player_str, channel)

    async def list_games(self, ctx):
        """ Liste les events dans un canal particulié """
        server = ctx.message.server
        # lfg_messages = []
        if "defaut_channel" not in self.settings[server.id]:
            return await self.bot.say("Terminé")
        await self.bot.wait_until_ready()
        print (server)
        channel = discord.utils.get(self.bot.get_all_channels(),
                                    id=self.settings[server.id]["defaut_channel"])
        await self.bot.say("Terminé")
        asyncio.gather(*lfg_messages).cancel()
        await self.bot.purge_from(channel)
        # asyncio.gather(*asyncio.Task.all_tasks(), loop=lfg_loop).cancel()
        for server in list(self.events.keys()):
            for event in self.events[server]:
                if not event["has_started"]:
                    # lfg_loop.create_task(await self.bot.say("C'est un event"))
                    # lfg_message = self.bot.send_message(channel, "C'est un event")
                    lfg_message = self.post_event(ctx, event, channel)
                    # self.bot.loop.create_task(self.bot.send_message(channel, "C'est un event"))
                    self.bot.loop.create_task(lfg_message)
                    # lfg_message = lfg_loop.create_task(await self.bot.say("C'est un event"))
                    lfg_messages.append(lfg_message)

    async def check_games(self):
        """Event loop"""
        CHECK_DELAY = 60
        await self.bot.wait_until_ready()
        while self == self.bot.get_cog("EventMaker"):
            cur_time = dt.utcnow()
            cur_time = calendar.timegm(cur_time.utctimetuple())
            save = False
            for server in list(self.events.keys()):
                channel = discord.utils.get(self.bot.get_all_channels(),
                                            id=self.settings[server]["channel"])
                for event in self.events[server]:
                    if cur_time >= event["event_start_time"]\
                            and not event["has_started"]:
                        emb = discord.Embed(title=event["event_name"],
                                            description=event["description"],
                                            color=discord.Colour(0x206694))
                        # emb.add_field(name="Créé par",
                        #               value=(discord.utils.get(
                        #                   self.bot.get_all_members(),
                        #                   id=event["creator"])).name)
                        emb.add_field(
                            name="Activité: ", value=event["activity"])
                        pt_str = dt.fromtimestamp(
                            event["create_time"], paris).strftime("%R %d/%m")
                        emb.add_field(
                            name="Début de l'event: ", value=dt.fromtimestamp(
                            event["event_start_time"], paris).strftime("le %d/%m à %R"))
                        emb.set_footer(
                            text="Créé le: " +
                            dt.fromtimestamp(
                                event["create_time"], paris).strftime(
                                    "%d/%m/%Y à %R"))
                        emb.add_field(name="ID", value=str(event["id"]))
                        # emb.add_field(
                        #     name="Compteur de participants", value=str(
                        #         len(event["participants"])))
                        player_str = ""
                        player_mention_str = "Un event commence! Participants: "
                        for user in event["participants"]:
                            target = discord.utils.get(
                                self.bot.get_all_members(), id=user)
                            player_str += target.name + " "
                            player_mention_str += target.mention + " "
                        # emb.add_field(
                        #     name="Compteur de participants", value=str(
                        #         len(event["participants"])))
                        if player_mention_str == "Un event commence! Participants: ":
                            player_mention_str = "L'event commence, mais aucun participants"
                        if player_str == "":
                            player_str = "Pas de participants"
                        emb.add_field(
                            name="Participants", value=player_str)
                        try:
                            await self.bot.send_message(channel, player_mention_str)
                            await self.bot.send_message(channel, embed=emb)
                        except discord.Forbidden:
                            pass  # Pas la permission d'envoyer des messages
                        for user in event["participants"]:
                            target = discord.utils.get(
                                self.bot.get_all_members(), id=user)
                            await self.bot.send_message(target, embed=emb)
                        event["has_started"] = True
                        save = True
            if save:
                dataIO.save_json(
                    os.path.join("data", "eventmaker", "events.json"),
                    self.events)
            await asyncio.sleep(CHECK_DELAY)

    async def server_join(self, server):
        if server.id not in self.settings:
            self.settings[server.id] = {
                "role": None,
                "next_id": 1,
                "channel": server.id
            }
        if server.id not in self.events:
            self.events[server.id] = []
        dataIO.save_json(os.path.join("data", "eventmaker", "events.json"), self.events)
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"), self.settings)

    async def server_leave(self, server):
        """Clean cache et storage"""
        if server.id in self.events:
            self.events.pop(server.id)
        if server.id in self.settings:
            self.settings.pop(server.id)
        dataIO.save_json(os.path.join("data", "eventmaker", "events.json"), self.events)
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"), self.settings)

    async def confirm_server_setup(self):
        """Assure que le bot a les params
        par défaut sur le serveur"""
        for server in list(self.bot.servers):
            if server.id not in self.settings:
                self.settings[server.id] = {
                    "role": None,
                    "next_id": 1,
                    "channel": server.id
                }
                if server.id not in self.events:
                    self.events[server.id] = []
        dataIO.save_json(os.path.join("data", "eventmaker", "events.json"), self.events)
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"), self.settings)


def check_folder():
    if not os.path.isdir(os.path.join("data", "eventmaker")):
        print("Creating the eventmaker directory in data")
        os.mkdir(os.path.join("data", "eventmaker"))


def check_file():
    if not dataIO.is_valid_json(os.path.join("data", "eventmaker", "events.json")):
        dataIO.save_json(os.path.join("data", "eventmaker", "events.json"), {})
    if not dataIO.is_valid_json(os.path.join("data", "eventmaker", "settings.json")):
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"), {})


def setup(bot):
    check_folder()
    check_file()
    n = EventMaker(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(n.check_games())
    loop.create_task(n.confirm_server_setup())
    lfg_loop = asyncio.get_event_loop()
    bot.add_listener(n.server_join, "on_server_join")
    bot.add_listener(n.server_leave, "on_server_remove")
    bot.add_cog(n)
