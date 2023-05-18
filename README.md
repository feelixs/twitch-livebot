This project is source code for a Discord bot that can track an unlimited amount of Twitch channels, and send notifications when they start streaming.

It runs without the need for any separate database, and stores all settings in an integrated cache.py file inside a dict object. 

It's optimized for small amounts of servers, and is easy to setup and use!


# Setup
Clone the repo by either downloading & extracting the .zip or opening it in GitHub Desktop, then follow all the steps below.

**- TWITCH SETUP**

1) Login and register a new application on the [twitch console](https://dev.twitch.tv/console).  As far as I'm aware the app name, oauth url and catagory don't matter for the purposes of this bot, so you can use something like http://localhost or https://about.html for the required url.
2) Open 'cache.py' and copy and paste the given Client ID and Secret into TWITCH_ID and TWITCH_SECRET respectively.

**- DISCORD SETUP**

1) Create a new application on the [discord development portal ](https://discord.com/developers/applications)
2) Go to the 'bot' tab of your new application and choose 'Add Bot'.
3) Open 'cache.py' & copy the new discord bot token into DISCORD_TOKEN.
4) Enable 'Server Member Intent' in the developer portal's 'Bot' section.
5) In 'cache.py', edit the 'name' and 'desc' variables to your bot's username and discriminator (the number next to its username)
6) Now you can invite the new bot to your server. Go to   OAuth > Url Generator   on the developer portal and check off the 'bot' item. Then make sure to choose to choose the  following items before using the url to invite the bot:

    - bot
    - Administrator
    - applications.commands
   

**- PYTHON SETUP**

1) Download Python 3.7 - you'll need this specific version because later versions may not work with the specific version of the discord slash module this bot uses
2) Run the following commands in your python directory:
    - pip install discord.py==1.7.3
    - pip install discord-py-slash-command==3.0.3
    - pip install googletrans==3.1.0a0
    - pip install requests asyncpg tqdm
3) Run the files 'commands.py' and 'main.py'. You can either use an IDE like Pycharm or run them directly from command line. Note that both of these files have to be running at the same time for the bot to be fully functional.
4) Add the bot to your server AFTER commands.py is up and running.
5) Once both files are up and running, you can send a command like '!dt follow' in your discord server to let the bot process joining your server.

**- WHAT ARE THESE FILES?**

commands.py - Processes commands. In the output of this script, you should see servers joined/left, as well as all messages sent by the bot. 

main.py - Checks the live statuses of all joined servers' followed twitch users, and sends messages to the server-assigned channel when one goes live.

cache.py - All bot info & joined servers + their respective data will be stored here.

**- Troubleshooting**
-
Most issues I've come across arise from the bot not having enough permissions in your server. Make sure its invite link was created with the "Administrator" and "application.commands" permissions enabled on the discord developer website.  

Another issue you may face is with getting the slash commands to appear initially. The bot should automatically create them, but sometimes for whatever reason it doesn't. One way to force it to manually create them is by stopping commands.py, going into cache.py and pasting your server ID into the 'guild_ids' list and then rerunning commands.py

**- FAQ**
-
**Q) Why isn't my instance responding to commands?**

A) Usually this is because 1- commands.py isn't running and/or 2- you haven't given it permission to send to the channel you're in.

**Q) I keep seeing error messages in main.py. What's wrong with my bot?**

A) This bot uses Python async/await functionalities (required by the discord.py module) that even I don't fully understand. If you're getting random errors that are noticeably affecting your instance, I'd say just re-start both files (commands.py & main.py), usually this fixes whatever's wrong. You can force-stop Python files by pressing cntrl+C or your IDE's stop button.


**Q) How many servers can the bot join?**

A) I don't know the limit, but note that if your bot is in over 100 servers simultaneously your instance will need to be officially verified by Discord. 

****

If you face any other bugs or have questions please reach out through the [Discord Server](https://discord.com/invite/atwCY9d).
