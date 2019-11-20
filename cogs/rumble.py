import datetime
import json
import pydest
import time
from discord import Embed
from discord.ext import commands


class Rumble:
    def __init__(self, bot):
        self.bot = bot
        self.ses = bot.session
        self.refresh_headers = {'Content-Type': 'application/x-www-form-urlencoded',
                                'X-Api-Key': bot.config['key']}
        self.token_url = "https://www.bungie.net/platform/app/oauth/token/"
        self.easy_access = bot.easy_access
        self.strp_format = '%Y-%m-%dT%H:%M:%SZ'
        self.pyd = pydest(self.config['key'])


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
                   'refresh_token': users[id]['refresh_token'],
                   'client_id': 30852,
                   'client_secret': self.bot.config['secret']}
        async with self.ses.post(self.token_url,
                                 data = payload,
                                 headers = self.refresh_headers) as req:
            resp = await req.json()
        #print(resp)
        with open('users.json', 'r') as file:
            users = json.load(file)

        users[id]['token'] = resp['access_token']
        users[id]['expires_at'] = time.time() + resp['expires_in']
        users[id]['refresh_token'] = resp['refresh_token']
        users[id]['refresh_expires_at'] = time.time() + resp['refresh_expires_in']
        users[id]['member_id'] = resp['membership_id']

        with open('users.json', 'w') as file:
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
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()
        em = Embed(title=f"Name: {resp['Response']['steamDisplayName']}", color=self.bot.user_color)
        await ctx.send(embed=em)

    async def _get_member_data(self, uid):
        user = await self._getinfo(uid)
        async with self.ses.get("https://www.bungie.net/Platform/Destiny2/-1/"
                                f"Profile/{user['member_id']}/LinkedProfiles",
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()
        if resp['Response']['profiles']:
            user['d2_mem_id'] = resp['Response']['profiles'][0]['membershipId']
            user['d2_mem_type'] = resp['Response']['profiles'][0]['membershipType']

    async def _get_latest_char(self, uid):
        user = await self._getinfo(uid)
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}?components=Characters",
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()
        characters = []
        for id in resp['Response']['characters']['data']:
            characters.append((id, datetime.datetime.strptime(resp['Response']['characters']
                                                              ['data'][id]['dateLastPlayed'], self.strp_format)))
        last_char = characters[0]
        for char in characters[1:]:
            if char[1] > last_char[1]:
                last_char = char

        return last_char[0]

    async def _make_space(self, uid, char_id):
        user = await self._getinfo(uid)
        buckets = {}
        each = {}
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}/Character/{char_id}?components=CharacterInventories",
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()
        # for item in resp:
        #   if bucketId in each:
        #       continue
        #   if bucketId in [bucket1, bucket2]:
        #       buckets[bucket1] = bucketId
            

    @commands.command()
    async def randomize(self, ctx):
        if not ctx.author.id in self.easy_access:
            return await ctx.reply("Please register first using the `register` commmand.")


    async def _transfer_item(self, uid, ref_id, instance_id = None, char_id = None, to_vault = None):
        user = await self._getinfo(uid)
        data = {"itemReferenceHash": ref_id,
                "itemId": instance_id,
                "characterId": char_id,
                "transferToVault": 1 if to_vault else 0,
                "membershipType": 3}
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/Actions/Items/TransferItem/",
                                headers={'X-Api-Key': self.bot.config['key'],
                                         'Authentication': f"Bearer {user['token']}"},
                                data=data) as req:
            resp = await req.json()

def setup(bot):
    bot.add_cog(Rumble(bot))