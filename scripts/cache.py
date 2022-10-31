DISCORD_TOKEN = ''  # discord token from discord developer portal
TWITCH_ID = ''  # twitch api ID
TWITCH_SECRET = ''  # twitch api secret
prefix = '!dt '  # not needed for v2.1.0+ because these versions use slash commands
name = ''  # your bot's username
desc = ''  # the number after your bot's username (without the #)

guild_ids = []
# if you're not seeing slash commands appear in your server after giving your bot all required permissions and
# running commands.py, copy & paste your server ID into guild_ids so it looks something like [762033092093018122]
# First make sure the bot has already processed joining your server, then stop commands.py, paste in your ID, and
# re-run commands.py and you should see the slash commands appear.

#  STORED DATA (don't edit this part):
data = {'servers': [{'id': '762033092093018122', 'name': "DiscoTwitch Bot", 'muted': [1, 4, 7], 'followed': [['hesmen', 'False', 0, '', 0]], 'live_message': '<user> is live!<br><link><br><role><br>**Title**<br><title><br>**Playing**<br><game><br>', 'role': '@everyone', 'settings': '{"d": [], "t": [], "r": [], "msg_roles": [[\'d\', \'everyone\']], "post_channels":[[\'d\', 0]]}', 'lang': 'en'}]}

#  id - the Discord server id
#  name - the Discord server name
#  muted - stores the notification settings for the server, the name 'muted' is outdatted but was never changed
#  post_channel - where the bot sends alerts. This is stored as a Discord channel id
#  followed - the list of followed Twitch users for the server as well as their boolean live status, titles, and more
#  live_message - message the bot sends when a followed user goes live
#  role - the server role that can interact with the bot. Default is @everyone
