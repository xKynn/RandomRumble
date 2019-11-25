import asyncio
import datetime
import enum
import json
import sqlite3
import pydest
import random
import time

from discord import Embed
from discord.ext import commands

class ItemType(enum.Enum):
    ARMOR = 2
    WEAPON = 3

class Rumble:
    def __init__(self, bot):
        self.bot = bot
        self.ses = bot.session
        self.refresh_headers = {'Content-Type': 'application/x-www-form-urlencoded',
                                'X-Api-Key': bot.config['key']}
        self.token_url = "https://www.bungie.net/platform/app/oauth/token/"
        self.easy_access = bot.easy_access
        self.strp_format = '%Y-%m-%dT%H:%M:%SZ'

        print(bot.pyd._manifest.manifest_files)
        conn = sqlite3.connect(bot.pyd._manifest.manifest_files['en'])
        c = conn.cursor()
        res = c.execute("SELECT json from DestinyInventoryBucketDefinition")
        bucket_defs = res.fetchall()
        relevant_buckets = ['Kinetic Weapons', 'Energy Weapons', 'Power Weapons', 'Helmet', 'Gauntlets',
                            'Chest Armor', 'Leg Armor', 'Class Armor']
        self.buckets = {}
        #print(bucket_defs[0])
        for bucket_str in bucket_defs:
            bucket = json.loads(bucket_str[0])
            if 'name' in bucket:
                print(bucket['name'])
            if 'name' in bucket['displayProperties'] and bucket['displayProperties']['name'] in relevant_buckets:
                self.buckets[bucket['hash']] = bucket['displayProperties']['name']
        print(self.buckets)


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
                   'client_id': self.bot.config['client_id'],
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
        print("member")
        user = await self._getinfo(uid)
        async with self.ses.get("https://www.bungie.net/Platform/Destiny2/-1/"
                                f"Profile/{user['member_id']}/LinkedProfiles",
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()
        if resp['Response']['profiles']:
            user['d2_mem_id'] = resp['Response']['profiles'][0]['membershipId']
            user['d2_mem_type'] = resp['Response']['profiles'][0]['membershipType']

    async def _get_latest_char(self, uid):
        print("Char")
        user = await self._getinfo(uid)
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}?components=Characters",
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()
        characters = []
        for id in resp['Response']['characters']['data']:
            characters.append((resp['Response']['characters']['data'][id],
                               datetime.datetime.strptime(resp['Response']['characters']['data'][id]['dateLastPlayed'],
                                                          self.strp_format)))
        last_char = characters[0]
        for char in characters[1:]:
            if char[1] > last_char[1]:
                last_char = char

        return last_char[0]

    async def _make_space(self, uid, char_id):
        print("Making Space")
        user = await self._getinfo(uid)
        each = {}
        buckets = {k: 0 for k in self.buckets.keys()}
        print(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}/Character/{char_id}?components=CharacterInventories")
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}/Character/{char_id}?components=CharacterInventories",
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()
        #print(type(list(self.buckets.keys())[0]))
        for item in resp['Response']['inventory']['data']['items']:
            #print(type(item['bucketHash']))
            if item['bucketHash'] not in self.buckets:
                continue
            buckets[item['bucketHash']] = buckets[item['bucketHash']] + 1
            if item['bucketHash'] in each:
                continue
            each[item['bucketHash']] = item

        print(buckets)
        need_space = [b_hash for b_hash in buckets if buckets[b_hash] == 9]
        print(need_space)
        for bucket in need_space:
            await self._transfer_item(uid, each[bucket]['itemHash'],
                                      each[bucket]['itemInstanceId'] if 'itemInstanceId' in each[bucket] else None,
                                      char_id, to_vault=1)
            await asyncio.sleep(0.3)

    async def _equip_items(self, uid, instance_ids, char_id):
        print("Equip")
        user = await self._getinfo(uid)
        async with self.ses.post(f"https://www.bungie.net/Platform/Destiny2/Actions/Items/EquipItems/",
                                headers={'X-Api-Key': self.bot.config['key'],
                                         'Authorization': f"Bearer {user['token']}"},
                                data=json.dumps({'characterId': char_id,
                                                 'itemIds': instance_ids,
                                                 'membershipType': user['d2_mem_type']})) as req:
            resp = await req.json()

    async def _save_loadout(self, uid, char_id):
        user = await self._getinfo(uid)
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}/Character/{char_id}?components=CharacterEquipment",
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()
        loadout = dict.fromkeys(self.buckets)
        for item in resp['Response']['characterEquipment']['data']['items']:
            if item['bucketHash'] in loadout_buckets:
                loadout_buckets[item['bucketHash']] = item

        user['saved_loadout'] = {'char_id': char_id,
                                 'loadout': loadout_buckets}

    async def _transfer_item(self, uid, ref_id, instance_id = None, char_id = None, to_vault = None):
        user = await self._getinfo(uid)
        data = json.dumps({"itemReferenceHash": ref_id,
                           "itemId": instance_id,
                           "characterId": char_id,
                           "transferToVault": 1 if to_vault else 0,
                           "membershipType": 3})
        print(data)
        async with self.ses.post(f"https://www.bungie.net/Platform/Destiny2/Actions/Items/TransferItem/",
                                headers={'X-Api-Key': self.bot.config['key'],
                                         'Authorization': f"Bearer {user['token']}"},
                                data=data) as req:
            resp = await req.json()
        print(resp)

    async def _restore(self, ctx, clear_loadout=True):
        user = await self._getinfo(ctx.author.id)
        if 'saved_loadout' in self.easy_access[ctx.author.id] and self.easy_access[ctx.author.id]['saved_loadout']:
            loadout = user['saved_loadout']
            item_ids = [x['itemInstanceId'] for x in loadout['loadout']]
            await self._equip_items(ctx.author.id, item_ids, loadout['char_id'])
            if clear_loadout:
                self.easy_access[ctx.author.id]['saved_loadout'].clear()
                self.easy_access
        else:
            await ctx.reply("No saved loadout.")

    @commands.command()
    async def restore(self, ctx):
        await self._restore(self, ctx)

    async def _return_to_vault(self, uid, char_id):
        user = self._getinfo(uid)
        if 'last_loadout' in user and user['last_loadout']:
            for bucket in user['last_loadout']:
                item = user['last_loadout'][bucket]
                await self._transfer_item(uid, item['itemHash'], item['itemInstanceId'],
                                          char_id, to_vault=True)
                await asyncio.sleep(0.3)

    @commands.command()
    async def randomize(self, ctx):
        user = await self._getinfo(ctx.author.id)
        if not user:
            return await ctx.reply("Please register first using the `register` commmand.")

        await self._get_member_data(ctx.author.id)
        char = await self._get_latest_char(ctx.author.id)
        if 'saved_loadout' not in user or not user['saved_loadout']:
            await self._save_loadout(uid, char['characterId'])
        if 'last_loadout' in user:
            await self._restore(ctx, clear_loadout=False)
            await self._return_to_vault(ctx.author.id, char['characterId'])
        else:
            await self._make_space(ctx.author.id, char['characterId'])
        each = {}
        buckets = {bucket: [] for bucket in self.buckets.keys()}
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}/?components=ProfileInventories",
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()

        for item in resp['Response']['profileInventory']['data']['items']:
            x = await self.bot.pyd.decode_hash(item['itemHash'], 'DestinyInventoryItemDefinition')
            if x['inventory']['bucketTypeHash'] not in self.buckets or \
                    (x['classType'] < 3 and x['classType'] != char['classType']):
                continue
            try:
                buckets[x['inventory']['bucketTypeHash']].append(item)
            except:
                print(x['displayProperties']['name'])
        print(buckets)
        for bucket in buckets:
            each[bucket] = random.choice(buckets[bucket])
        exotic_armor = False
        exotic_weapon = False
        for bucket in each:
            item = await self.bot.pyd.decode_hash(each[bucket]['itemHash'], 'DestinyInventoryItemDefinition')
            if item['inventory']['tierType'] == 6:
                if item['itemType'] == ItemType.ARMOR:
                    if not exotic_armor:
                        exotic_armor = True
                        continue
                if item['itemType'] == ItemType.WEAPON:
                    if not exotic_weapon:
                        exotic_weapon = True
                        continue
                while True:
                    roll = random.choice(buckets[bucket])
                    roll_item = await self.bot.pyd.decode_hash(roll['itemHash'],
                                                               'DestinyInventoryItemDefinition')
                    if roll_item['inventory']['tierType'] != 6:
                        each[bucket] = roll
                        break
        last_loadout = {}
        for bucket in each:
            last_loadout[bucket] = each[bucket]
            await self._transfer_item(ctx.author.id, each[bucket]['itemHash'],
                                      each[bucket]['itemInstanceId'] if 'itemInstanceId' in each[bucket] else None,
                                      char['characterId'])
            await asyncio.sleep(0.3)
        self.easy_access[ctx.author.id]['last_loadout'] = last_loadout
        await self._equip_items(ctx.author.id, [each[item]['itemInstanceId'] for item in each], char['characterId'])



def setup(bot):
    bot.add_cog(Rumble(bot))
