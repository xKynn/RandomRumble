import aiohttp
import os
import pydest
import sys
import json

from app import run
from discord.ext import commands
from multiprocessing import Process
from pathlib import Path
from utils.custom_context import RandyContext

class Randy(commands.Bot):
    def __init__(self, *args, **kwargs):
        self.description = 'To be continued'

        # Configs & token
        with open('config.json') as f:
            self.config = json.load(f)


        super().__init__(command_prefix=commands.when_mentioned, description=self.description,
                         pm_help=None, *args, **kwargs)

        # Startup extensions (none yet)
        self.startup_ext = [x.stem for x in Path('cogs').glob('*.py')]

        # aiohttp session
        self.session = aiohttp.ClientSession(loop=self.loop)

        # Make room for the help command
        self.remove_command('help')

        # Embed color
        self.user_color = 0x781D1D
        self.pyd = pydest.Pydest(self.config['key'])
        self.fapp_proc = Process(target=run)
        self.easy_access = {}


    def run(self):
        try:
            self.fapp_proc.start()
            super().run(self.config['token'])
        finally:
            self.fapp_proc.terminate()
            self.loop.close()

    async def report(self, msg):
        await self.owner.send(f"Error, context: `{msg}`")

    async def on_message(self, message):
        if message.author.id == self.user.id:
            return
        await self.wait_until_ready()
        ctx = await self.get_context(message, cls=RandyContext)
        await self.invoke(ctx)

    async def on_ready(self):
        await self.pyd.update_manifest(language='en')
        for ext in self.startup_ext:
            try:
                self.load_extension(f'cogs.{ext}')
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print(f'Failed to load extension: {ext}\n{e}')
                print(exc_type, fname, exc_tb.tb_lineno)
            else:
                print(f'Loaded extension: {ext}')

        self.ses = aiohttp.ClientSession()
        c = await self.application_info()
        self.owner = c.owner
        print(f'Client logged in.\n'
              f'{self.user.name}\n'
              f'{self.user.id}\n'
              '--------------------------')
