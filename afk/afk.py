import discord
from redbot.core import Config, commands, checks
try:
    from slashtags import menu
except ModuleNotFoundError:
    from redbot.core.utils.menus import menu, DEFAULT_CONTROLS

from typing import Optional, Literal
import datetime
import re

IMAGE_LINKS = re.compile(r"(http[s]?:\/\/[^\"\']*\.(?:png|jpg|jpeg|gif|png))")


class Afk(commands.Cog):
    """Le Afk cog.
    
    Originally called Away but changed to avoid conflicts with the Away cog
    Check out the original [here](https://github.com/aikaterna/aikaterna-cogs)
    """
    default_global_settings = {"ign_servers": []}
    default_guild_settings = {"TEXT_ONLY": False, "BLACKLISTED_MEMBERS": []}
    default_user_settings = {
        "MESSAGE": False,
        "IDLE_MESSAGE": False,
        "DND_MESSAGE": False,
        "OFFLINE_MESSAGE": False,
        "GAME_MESSAGE": {},
        "STREAMING_MESSAGE": False,
        "LISTENING_MESSAGE": False,
        "PINGS": [],
        "TIME": 0
    }

    async def red_delete_data_for_user(
        self, *, requester: Literal["discord", "owner", "user", "user_strict"], user_id: int,
    ):
        await self.config.user_from_id(user_id).clear()

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 718395193090375700, force_registration=True) #Changed Identifier
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.config.register_user(**self.default_user_settings)

    def _draw_play(self, song):
        song_start_time = song.start
        total_time = song.duration
        current_time = datetime.datetime.utcnow()
        elapsed_time = current_time - song_start_time
        sections = 12
        loc_time = round((elapsed_time / total_time) * sections)  # 10 sections

        bar_char = "\N{BOX DRAWINGS HEAVY HORIZONTAL}"
        seek_char = "\N{RADIO BUTTON}"
        play_char = "\N{BLACK RIGHT-POINTING TRIANGLE}"
        msg = "\n" + play_char + " "

        for i in range(sections):
            if i == loc_time:
                msg += seek_char
            else:
                msg += bar_char

        msg += " `{:.7}`/`{:.7}`".format(str(elapsed_time), str(total_time))
        return msg

    async def add_ping(self, message: discord.Message, author):
        """
            Adds a user to the list of pings
        """
        user_config = self.config.user(author)
        async with user_config.PINGS() as pingslist:
            pingslist.append({
                "whopinged": message.author.mention,
                "msgurl": message.jump_url,
                "channel": message.channel.mention,
                "timestamp": f"<t:{round(datetime.datetime.now().timestamp())}:R>",
                "messagecontent": message.content[0:500],
                "pageno": len(pingslist) + 1
            })

    async def remove_ping(self, author):
        """
            Adds a user to the list of pings
        """
        user_config = self.config.user(author)
        await user_config.PINGS.clear()

    async def pingmenu(self,ctx,author):
        """
            Returns a menu of the people who pinged you
        """
        user_config = self.config.user(author)
        menulist = []
        async with user_config.PINGS() as pingslist:
            for ping in pingslist:
                embed=discord.Embed(title=f"Pings you recieved while you were away {author.name}.",color=author.colour,description=f""":arrow_right: {ping["whopinged"]} [pinged you in]({ping['msgurl']}) {ping["channel"]} {ping["timestamp"]}.\n**Message Content:** {ping["messagecontent"]}""")
                embed.set_footer(text=f"Page no: {(ping['pageno'])}/{len(pingslist)}")
                menulist.append(embed)

        await menu(ctx, menulist, timeout=60)
            

    async def make_embed_message(self, author, message, state=None):
        """
            Makes the embed reply
        """
        avatar = author.avatar_url_as()  # This will return default avatar if no avatar is present
        color = author.color
        
        if message:
            link = IMAGE_LINKS.search(message)
            if link:
                message = message.replace(link.group(0), " ")
            message = message

        if state == "away":
            em = discord.Embed(description=f"{author.mention} is currently away since <t:{await self.config.user(author).TIME()}:R>.\n\n**Message:**\n{message}", color=color)
            em.set_thumbnail(url=avatar)
        return em

    async def find_user_mention(self, message):
        """
            Replaces user mentions with their username
        """
        for word in message.split():
            match = re.search(r"<@!?([0-9]+)>", word)
            if match:
                user = await self.bot.fetch_user(int(match.group(1)))
                message = re.sub(match.re, "@" + user.name, message)
        return message

    async def make_text_message(self, author, message, state=None):
        """
            Makes the message to display if embeds aren't available
        """
        message = await self.find_user_mention(message)
        

        if state == "away":
            msg = f"{author.display_name} is currently away since <t:{await self.config.user(author).TIME()}:R>."
        msg = msg + f" \n\n**Message:**\n`{message}`"
        return msg

    async def is_mod_or_admin(self, member: discord.Member):
        guild = member.guild
        if member == guild.owner:
            return True
        if await self.bot.is_owner(member):
            return True
        if await self.bot.is_admin(member):
            return True
        if await self.bot.is_mod(member):
            return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        guild = message.guild
        
        if not guild or not message.mentions or message.author.bot:
            return
        if not message.channel.permissions_for(guild.me).send_messages:
            return

        blocked_guilds = await self.config.ign_servers()
        guild_config = await self.config.guild(guild).all()
        
        for author in message.mentions:
            if (guild.id in blocked_guilds and not await self.is_mod_or_admin(author)) or author.id in guild_config["BLACKLISTED_MEMBERS"]:
                continue
            user_data = await self.config.user(author).all()
            embed_links = message.channel.permissions_for(guild.me).embed_links

            away_msg = user_data["MESSAGE"]
            # Convert possible `delete_after` of < 5s of before PR#212
            if isinstance(away_msg, list) and away_msg[1] is not None and away_msg[1] < 5:
                await self.config.user(author).MESSAGE.set((away_msg[0], 5))
                away_msg = away_msg[0], 5
            if away_msg:
                if type(away_msg) in [tuple, list]:
                    # This is just to keep backwards compatibility
                    away_msg, delete_after = away_msg
                else:
                    delete_after = None
                if embed_links and not guild_config["TEXT_ONLY"]:
                    em = await self.make_embed_message(author, away_msg, "away")
                    await self.add_ping(message, author)
                    await message.channel.send(embed=em, delete_after=delete_after, reference=message, mention_author=False)
                elif (embed_links and guild_config["TEXT_ONLY"]) or not embed_links:
                    msg = await self.make_text_message(author, away_msg, "away")
                    await self.add_ping(message, author)
                    await message.channel.send(msg, delete_after=delete_after, reference=message, mention_author=False)
                continue
    @commands.command(name="away", aliases=["afk"])
    @commands.guild_only()
    async def away_(self, ctx, delete_after: Optional[int] = None, *, message: str = None):
        """
        Tell the bot you're away or back.

        `delete_after` Optional seconds to delete the automatic reply. Must be minimum 5 seconds
        `message` The custom message to display when you're mentioned
        """
        if delete_after is not None and delete_after < 5:
            return await ctx.send("Please set a time longer than 5 seconds for the `delete_after` argument")

        author = ctx.message.author
        user_config = await self.config.user(author).all()
        mess = await self.config.user(author).MESSAGE()
                
        if mess:
            await self.config.user(author).MESSAGE.set(False)
            await self.config.user(author).TIME.set(0)
            msg = "Welcome back. Your AFK has been reset."
            await ctx.send(msg)
            if len(user_config["PINGS"]) != 0:
                await self.pingmenu(ctx,author)
                await self.remove_ping(author)
            else:
                pass
        else:
            if message is None:
                await self.config.user(author).MESSAGE.set((" ", delete_after))
            else:
                await self.config.user(author).MESSAGE.set((message, delete_after))
            await self.config.user(author).TIME.set(round(datetime.datetime.now().timestamp()))
            msg = "You are now away. Users who ping you will now be notified. Run the command again to reset AFK."
            await ctx.send(msg)

    @commands.command(name="toggleaway")
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def _ignore(self, ctx, member: discord.Member=None):
        """
        Toggle away messages on the whole server or a specific guild member.

        Mods, Admins and Bot Owner are immune to this.
        """
        guild = ctx.message.guild
        if member:
            bl_mems = await self.config.guild(guild).BLACKLISTED_MEMBERS()
            if member.id not in bl_mems:
                bl_mems.append(member.id)
                await self.config.guild(guild).BLACKLISTED_MEMBERS.set(bl_mems)
                msg = f"Away messages will not appear when {member.display_name} is mentioned in this guild."
                await ctx.send(msg)
            elif member.id in bl_mems:
                bl_mems.remove(member.id)
                await self.config.guild(guild).BLACKLISTED_MEMBERS.set(bl_mems)
                msg = f"Away messages will appear when {member.display_name} is mentioned in this guild."
                await ctx.send(msg)
            return
        if guild.id in (await self.config.ign_servers()):
            guilds = await self.config.ign_servers()
            guilds.remove(guild.id)
            await self.config.ign_servers.set(guilds)
            message = "Not ignoring this guild anymore."
        else:
            guilds = await self.config.ign_servers()
            guilds.append(guild.id)
            await self.config.ign_servers.set(guilds)
            message = "Ignoring this guild."
        await ctx.send(message)

    @commands.command(aliases=["afktextonly"])
    @commands.guild_only()
    @checks.admin_or_permissions(administrator=True)
    async def awaytextonly(self, ctx):
        """
        Toggle forcing the guild's away messages to be text only.

        This overrides the embed_links check this cog uses for message sending.
        """
        text_only = await self.config.guild(ctx.guild).TEXT_ONLY()
        if text_only:
            message = "Away messages will now be embedded or text only based on the bot's permissions for embed links."
        else:
            message = (
                "Away messages are now forced to be text only, regardless of the bot's permissions for embed links."
            )
        await self.config.guild(ctx.guild).TEXT_ONLY.set(not text_only)
        await ctx.send(message)
