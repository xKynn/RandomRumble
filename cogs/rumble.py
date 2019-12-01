import asyncio
import datetime
import enum
import json
import sqlite3
import random
import time

from discord import Embed
from discord.ext import commands

class ItemType(enum.Enum):
    ARMOR = 2
    WEAPON = 3

class Rumble(commands.Cog):
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
                            'Chest Armor', 'Leg Armor', 'Class Armor', 'Subclass']
        self.buckets = {}
        #print(bucket_defs[0])
        for bucket_str in bucket_defs:
            bucket = json.loads(bucket_str[0])
            if 'name' in bucket['displayProperties'] and bucket['displayProperties']['name'] in relevant_buckets:
                self.buckets[bucket['hash']] = bucket['displayProperties']['name']
        self.maps = [("Altar of Flame", 1), ("Bannerfall", 1), ("The Burnout", 1), ("The Citadel", 1),
                     ("Convergence", 1), ("The Dead Cliffs", 1), ("Distant Shore", 2), ("Emperor's Respite", 2),
                     ("Endless Vale", 2), ("Equinox", 2), ("Eternity", 2), ("Firebase Echo", 2), ("The Fortress", 3),
                     ("Fragment", 3), ("Gambler's Ruin", 3), ("Javelin-4", 3), ("Legion's Gulch", 3),
                     ("Meltdown", 3), ("Midtown", 4), ("Pacifica", 4), ("Radiant Cliffs", 4), ("Retribution", 4),
                     ("Solitude", 4), ("Twilight Gap", 4), ("Vostok", 5), ("Widow's Court", 5), ("Wormhaven", 5)]


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
                                 data=payload,
                                 headers=self.refresh_headers) as req:
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
                   url=f"https://{self.bot.config['register_hostname']}/register?uid={ctx.author.id}")
        try:
            await ctx.author.send(embed=em)
            await ctx.send("Check your DM for a registration link.")
        except:
            await ctx.error("Please enable DMs from server members to receive the registration link.")

    @commands.command()
    async def map(self, ctx):
        """ Pick a random crucible map. """
        m = random.choice(self.maps)
        em = Embed(title="🗺️ Map", description=f"{m[0]}, Page {m[1]}")
        await ctx.send(embed=em)

    @commands.command(alts=["test", ])
    async def usernametest(self, ctx):
        """ A simple test command to check if registration worked. """
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
        #print(resp)
        try:
            if resp['Response']['profiles']:
                user['d2_mem_id'] = resp['Response']['profiles'][0]['membershipId']
                user['d2_mem_type'] = resp['Response']['profiles'][0]['membershipType']
                return True
        except:
            pass
        return False

    async def _get_latest_char(self, uid):
        print("Char")
        user = await self._getinfo(uid)
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}/?components=Characters",
                                headers={'X-Api-Key': self.bot.config['key']}) as req:
            resp = await req.json()
        characters = []
        for _id in resp['Response']['characters']['data']:
            characters.append((resp['Response']['characters']['data'][_id],
                               datetime.datetime.strptime(resp['Response']['characters']['data'][_id]['dateLastPlayed'],
                                                          self.strp_format)))
        last_char = characters[0]
        for char in characters[1:]:
            if char[1] > last_char[1]:
                last_char = char

        return last_char[0]

    async def _get_char_items(self, user, char_id):
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}/Character/{char_id}/?components=CharacterInventories",
                                headers={'X-Api-Key': self.bot.config['key'],
                                         'Authorization': f"Bearer {user['token']}"}) as req:
            resp = await req.json()
        return resp['Response']['inventory']['data']['items']

    async def _make_space(self, uid, char_id):
        print("Making Space")
        user = await self._getinfo(uid)
        each = {}
        buckets = {k: 0 for k in self.buckets.keys()}
        print(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                               f"Profile/{user['d2_mem_id']}/Character/{char_id}/?components=CharacterInventories")
        char_items = await self._get_char_items(user, char_id)
        #print(resp)
        for item in char_items:
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
            await asyncio.sleep(0.2)
        if not 'space_items' in self.easy_access[str(uid)]:
            self.easy_access[str(uid)]['space_items'] = {}
        if not self.easy_access[str(uid)]['space_items']:
            self.easy_access[str(uid)]['space_items']['char_id'] = char_id
            self.easy_access[str(uid)]['space_items']['items'] = []

        self.easy_access[str(uid)]['space_items']['items'].extend([each[bucket] for bucket in need_space])
        return char_items


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
        print("Saving loadout")
        user = await self._getinfo(uid)
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}/Character/{char_id}/?components=CharacterEquipment",
                                headers={'X-Api-Key': self.bot.config['key'],
                                         'Authorization': f"Bearer {user['token']}"}) as req:
            resp = await req.json()
        loadout_buckets = dict.fromkeys(self.buckets)
        for item in resp['Response']['equipment']['data']['items']:
            if item['bucketHash'] in loadout_buckets:
                loadout_buckets[item['bucketHash']] = item

        self.easy_access[str(uid)]['saved_loadout'] = {'char_id': char_id,
                                 'loadout': loadout_buckets}

    async def _transfer_item(self, uid, ref_id, instance_id = None, char_id = None, to_vault = None):
        user = await self._getinfo(uid)
        data = json.dumps({"itemReferenceHash": ref_id,
                           "itemId": instance_id,
                           "characterId": char_id,
                           "transferToVault": 1 if to_vault else 0,
                           "membershipType": 3})
        #print(data)
        async with self.ses.post(f"https://www.bungie.net/Platform/Destiny2/Actions/Items/TransferItem/",
                                headers={'X-Api-Key': self.bot.config['key'],
                                         'Authorization': f"Bearer {user['token']}"},
                                data=data) as req:
            resp = await req.json()
        #print(resp)

    async def _restore(self, ctx, clear_loadout=True):
        user = await self._getinfo(ctx.author.id)
        #print(user)
        if 'saved_loadout' in self.easy_access[str(ctx.author.id)] and self.easy_access[str(ctx.author.id)]['saved_loadout']:
            loadout = user['saved_loadout']
            item_ids = [loadout['loadout'][x]['itemInstanceId'] for x in loadout['loadout']]
            await self._equip_items(ctx.author.id, item_ids, loadout['char_id'])
            await self._return_to_vault(ctx.author.id, loadout['char_id'])
            await self._return_to_char(ctx.author.id)
            if clear_loadout:
                try:
                    self.easy_access[str(ctx.author.id)]['saved_loadout'].clear()
                    self.easy_access[str(ctx.author.id)]['last_loadout'].clear()
                    self.easy_access[str(ctx.author.id)]['space_items'].clear()
                except (KeyError, AttributeError) as e:
                    pass
        else:
            await ctx.reply("No saved loadout.")

    @commands.command()
    async def restore(self, ctx):
        """ Restore character inventory and state to one before your first randomize. """
        await ctx.trigger_typing()
        await self._restore(ctx)
        await ctx.reply("Done! :thumbsup:")

    @commands.command()
    async def clear(self, ctx):
        """
        Clear all stored character specific info on Randy.
        This allows you to switch character while maintaining inventory management.
        """
        await ctx.trigger_typing()
        user = await self._getinfo(ctx.author.id)
        if not user:
            return await ctx.reply("Please register first using the `register` commmand.")
        try:
            self.easy_access[str(ctx.author.id)]['saved_loadout'].clear()
            self.easy_access[str(ctx.author.id)]['last_loadout'].clear()
            self.easy_access[str(ctx.author.id)]['space_items'].clear()
        except (KeyError, AttributeError) as e:
            pass
        await ctx.reply("Cleared! You can now switch characters. :thumbsup:")


    async def _return_to_char(self, uid):
        user = await self._getinfo(uid)
        if 'space_items' in user:
            items = user['space_items']['items']
            char_id = user['space_items']['char_id']
            for item in items:
                await self._transfer_item(uid, item['itemHash'], item['itemInstanceId'],
                                          char_id)
                await asyncio.sleep(0.2)

    async def _return_to_vault(self, uid, char_id):
        user = await self._getinfo(uid)
        if 'last_loadout' in user and user['last_loadout']:
            for bucket in user['last_loadout']:
                item = user['last_loadout'][bucket]
                await self._transfer_item(uid, item['itemHash'], item['itemInstanceId'],
                                          char_id, to_vault=True)
                await asyncio.sleep(0.2)

    async def _get_item_and_perks(self, uid, ref_id, instance_id):
        user = await self._getinfo(uid)
        item_data = await self.bot.pyd.decode_hash(ref_id, 'DestinyInventoryItemDefinition')
        item = {'name': f"Subclass: {item_data['displayProperties']['name']}"
                        if self.buckets[item_data['inventory']['bucketTypeHash']] == "Sublcass"
                        else item_data['displayProperties']['name'],
                'traits': [],
                'subclass': True if self.buckets[item_data['inventory']['bucketTypeHash']] == 'Subclass' else False}
        if not item['subclass']:
            async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/Profile"
                                    f"/{user['d2_mem_id']}/Item/{instance_id}/?components=ItemSockets",
                                    headers={'X-Api-Key': self.bot.config['key']}) as req:
                resp = await req.json()

            for sock in resp['Response']['sockets']['data']['sockets']:
                if sock['isVisible'] and 'plugHash' in sock:
                    trait_data = await self.bot.pyd.decode_hash(sock['plugHash'],
                                                                'DestinyInventoryItemDefinition')
                    if trait_data['itemTypeDisplayName'] in ['Scope', 'Barrel', 'Magazine', 'Trait', 'Intrinsic']:
                        item['traits'].append(trait_data['displayProperties']['name'])
        else:
            item['traits'].append(f"*Tree*: {random.choice(['Top', 'Middle', 'Bottom'])}")
            item['traits'].append(f"*Grenade*: {random.choice(['Left', 'Middle', 'Right'])}")
            item['traits'].append(f"*Class Ability*: {random.choice(['Top', 'Bottom'])}")
            item['traits'].append(f"*Jump*: {random.choice(['Left', 'Middle', 'Right'])}")

        return item

    @commands.command()
    async def randomize(self, ctx):
        """
        Randomize items on your last logged in character.
        Randy will smartly return any pulled items from vault on subsequent randomize commands.
        """
        await ctx.trigger_typing()
        _id = ctx.author.id
        user = await self._getinfo(_id)
        if user is False:
            return await ctx.reply("Please register first using the `register` commmand.")

        mem = await self._get_member_data(_id)
        if not mem:
            return await ctx.reply("No linked accounts found or D2 API is currently unintentionally underperforming.")
        char = await self._get_latest_char(_id)
        if 'saved_loadout' not in user or not user['saved_loadout']:
            await self._save_loadout(_id, char['characterId'])
        if 'last_loadout' in user and user['last_loadout']:
            await self._restore(ctx, clear_loadout=False)
            ch_items = await self._get_char_items(user, char['characterId'])
        else:
            ch_items = await self._make_space(_id, char['characterId'])
        each = {}
        buckets = {bucket: [] for bucket in self.buckets.keys()}
        print("Buckets", buckets)
        async with self.ses.get(f"https://www.bungie.net/Platform/Destiny2/{user['d2_mem_type']}/"
                                f"Profile/{user['d2_mem_id']}/?components="
                                "ProfileInventories",
                                headers={'X-Api-Key': self.bot.config['key'],
                                         'Authorization': f"Bearer {user['token']}"}) as req:
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
                pass
        for item in ch_items:
            x = await self.bot.pyd.decode_hash(item['itemHash'], 'DestinyInventoryItemDefinition')
            if x['inventory']['bucketTypeHash'] not in self.buckets or \
                    (x['classType'] < 3 and x['classType'] != char['classType']):
                continue
            try:
                buckets[x['inventory']['bucketTypeHash']].append(item)
            except:
                print(x['displayProperties']['name'])
                pass
        print(buckets.keys())
        if self.easy_access[str(ctx.author.id)]['saved_loadout']:
            for bucket in self.easy_access[str(ctx.author.id)]['saved_loadout']['loadout']:
                buckets[bucket].append(
                    self.easy_access[str(ctx.author.id)]['saved_loadout']['loadout'][bucket])
        for bucket in buckets:
            if len(buckets[bucket]) < 2:
                continue
            each[bucket] = random.choice(buckets[bucket])
        exotic_armor = False
        exotic_weapon = False
        print(each)
        for bucket in each:
            print("Bucket ", self.buckets[bucket])
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
            if each[bucket]['location'] < 2:
                continue
            last_loadout[bucket] = each[bucket]
            await self._transfer_item(_id, each[bucket]['itemHash'],
                                      each[bucket]['itemInstanceId'] if 'itemInstanceId' in each[bucket] else None,
                                      char['characterId'])
            await asyncio.sleep(0.2)
        self.easy_access[str(_id)]['last_loadout'] = last_loadout
        await self._equip_items(_id, [each[item]['itemInstanceId'] for item in each], char['characterId'])

        em = Embed(title=f"🎲 New Loadout For {ctx.author.display_name}!",
                   description="`@Randy restore` to restore your original inventory. "
                               "\n`@Randy clear` before switching characters.")
        em.set_thumbnail(url=f"https://bungie.net{char['emblemPath']}")
        for bucket in each:
            item_data = await self._get_item_and_perks(_id, each[bucket]['itemHash'], each[bucket]['itemInstanceId'])
            #print(item_data)
            em.add_field(name=item_data['name'], value=' **|**\n'.join(item_data['traits']) if item_data['traits']
                                                                  else "N/A")

        await ctx.send(embed=em)

def setup(bot):
    bot.add_cog(Rumble(bot))
