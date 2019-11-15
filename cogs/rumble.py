import json
import time
from discord import Embed
from discord.ext import commands


class Rumble:
    def __init__(self, bot):
        self.bot = bot
        self.ses = bot.session
        self.refresh_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        self.token_url = "https://www.bungie.net/platform/app/oauth/token/"
        self.easy_access = bot.easy_access


    async def _getinfo(self, id):
        id = str(id)
        if id in self.easy_access:
            if time.time() + 60 < int(self.easy_access[id]['expires_at']):
                return self.easy_access[id]
        else:
            with open('users.json') as file:
                users = json.load(file)
            if not id in users:
                return False
            if time.time() + 60 < int(users[id]['expires_at']):
                self.easy_access[id] = users[id]
                return users[id]
        res = await self._refresh_access_token(id)
        self.easy_access[id] = res
        return res

    async def _refresh_access_token(self, id):
        id = str(id)
        print("Refreshing token")
        with open('users.json') as file:
            users = json.load(file)
        if not id in users:
            return
        payload = {'grant_type': 'refresh_token',
                   'refresh_token': users['refresh_token'],
                   'client_id': 30852,
                   'client_secret': self.bot.config['secret']}
        async with self.ses.post(self.token_url,
                                 data = json.dumps(payload),
                                 headers = self.refresh_headers) as req:
            resp = await req.json()

        with open('users.json', 'rw') as file:
            users = json.load(file)
            users[id]['token'] = resp['access_token']
            users[id]['expires_at'] = time.time() + resp['expires_in']
            users[id]['refresh_token'] = resp['refresh_token']
            users[id]['refresh_expires_at'] = time.time() + resp['refresh_expires_in']
            users[id]['member_id'] = resp['membership_id']
            json.dump(users, file)
        self.easy_access[id] = users[id]
        return users[id]

    @commands.command()
    async def register(self, ctx):
        """ Pair your Discord with your Destiny 2 account. """
        em = Embed(title="Register here", color=self.bot.user_color,
                   url=f"http://127.0.0.1:5000/register?uid={ctx.author.id}")
        await ctx.send(embed=em)

    @commands.command(alts=["test",])
    async def usernametest(self, ctx):
        user = await self._getinfo(ctx.author.id)
        async with self.ses.get(f"https://www.bungie.net/Platform/User/GetBungieNetUserById/{user['member_id']}",
                                headers={'X-Api-Key': self.bot.config['key'],
                                         'Authorization': f'Bearer {user["token"]}'}) as req:
            resp = await req.json()
        em = Embed(title=f"Name: {resp['Response']['steamDisplayName']}", color=self.bot.user_color)
        await ctx.send(embed=em)

def setup(bot):
    bot.add_cog(Rumble(bot))