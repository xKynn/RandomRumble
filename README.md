# Randy the Random Rumble Robot
A Random Rumble discord bot for destiny 2.
Mini Flask webapp as interface to pair up discord info with bungie auth code.

How to use:
1. [Invite to discord](https://discordapp.com/api/oauth2/authorize?client_id=644787087064825856&permissions=18432&scope=bot).
2. `@Randy register`
3. `@Randy randomize`
4. `@Randy map` if you want.
5. `@Randy restore`

Commands:
1. `randomize`
   - Randomize items on your last logged in character.
   - Randy will smartly return any pulled items from vault on subsequent randomize commands.
2. `restore`
   - Restore character inventory and state to one before your first randomize.
3. `clear`
   - Clear all stored character specific info on Randy.
   - This allows you to switch character while maintaining inventory management.

Want to host your own instance?
1. Clone and satisfy requirements.
2. Make your ouath enabled app for bungie [here](https://www.bungie.net/en/Application).
3. Make your discord app and add a bot account for it [here](https://discordapp.com/developers/applications/).
4. Change arguments for `run` in `app.py`. If you want https redirect to work from Bungie you will need a domain and cert.
5. `config.json`
   - token : discord bot token
   - secret : bungie client secret
   - key : bungie api key
   - client_id : bungie client id
   - register_hostname : URL to use in discord for register links
