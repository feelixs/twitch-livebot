import cache as CACHE
import datetime
import time
import ast
import asyncio
import discord
import concurrent.futures._base as cfb
from discord_slash import SlashCommand, manage_components, ComponentContext, ButtonStyle
import importlib
import requests
import traceback
from discord.ext import tasks, commands
from discord.ext.commands.errors import CommandNotFound
import googletrans


IGNORE_TWITCH_USERS = []  # users in this list can't be followed

translator = googletrans.Translator()
try:
    guild_ids = CACHE.guild_ids
except:
    guild_ids = []
DISCORD_TOKEN = CACHE.DISCORD_TOKEN
TWITCH_ID = CACHE.TWITCH_ID
TWITCH_SECRET = CACHE.TWITCH_SECRET
CACHE_HEADER = "DISCORD_TOKEN = \'" + DISCORD_TOKEN + "\'\nTWITCH_ID = \'" + TWITCH_ID + \
               "\'\nTWITCH_SECRET = \'" + TWITCH_SECRET + "\'\nprefix = \'" + CACHE.prefix \
               + "\'\nname = \'" + CACHE.name + "\'\ndesc = \'" + CACHE.desc + "\'\ndata = "

intent = discord.Intents.default()
intent.members = True
AFK_TIMEOUT = 60  # seconds to wait after responding to slash command before removing components aka buttons/menus. None for infinite
MISC_SLEEP_TIMEOUT = 30  # seconds to sleep before deleting misc message or None to skip sleep and never delete
CLIENT = commands.Bot(command_prefix=CACHE.prefix, intents=intent)
SLASH = SlashCommand(CLIENT, sync_commands=True)
CLIENT.remove_command('help')


class NoAttr(Exception):
    pass


class NoServerFound(Exception):
    pass


delete_queue, edit_queue = [], []


async def queue_delete(msg, timeout=0, server=None, channel=None):
    global delete_queue
    await asyncio.sleep(timeout)
    delete_queue.append([msg, server, channel])


async def queue_edit(msg, content=None, embed=None, components=None, timeout=0):
    global edit_queue
    await asyncio.sleep(timeout)
    if CLIENT.is_ws_ratelimited():
        print('ratelimited!')
    await msg.edit(content=content, embed=embed, components=components)


async def client_send(ctx, msg="", components=None, form=None, embed=True, timeout=None, dembed=None):
    """Sends messages to Discord context. Makes messages embedded if embed == 1. If form != None, translate"""
    """IF timeout!=None USE ASYNCIO.CREATE_TASK, NOT AWAIT because asyncio.sleep() will pause script with await"""
    if components is None:
        components = []
    try:
        if form is None:
            msg = str(msg)
        else:
            if isinstance(form, str):
                form = tuple([form])
            elif isinstance(form, list):
                form = tuple(form)
            try:
                msg = translate(str(msg), ctx).format(*form)
            except:
                msg = str(msg)
        if dembed is None:
            if embed:
                m = await ctx.send("```" + msg + "```", components=components)
            else:
                m = await ctx.send(msg, components=components)
        else:
            m = await ctx.send(components=components, embed=dembed)
        if timeout is not None:
            await queue_delete(m, timeout)
        return m
    except:
        print(ctx, traceback.format_exc())
        return None


def str_to_list(st):
    """Turns a list that's stored as a str back into a list"""
    li = []
    word = ""
    st = str(st)
    for i in range(len(st)):
        if st[i] != '\'' and st[i] != "[" and st[i] != "]" and st[i] != " ":
            if st[i] == ',':
                li.append(word)
                word = ""
            else:
                word += st[i]
    if word != "":
        li.append(word)
    return li


def translate(st, ctx):
    try:
        lang = cache.binary_search_object_by_id(ctx.guild.id).lang
        if lang != 'en':
            return translator.translate(st, dest=lang).text
        else:
            return st
    except NoServerFound:
        pass
    except:
        print(traceback.format_exc())
    return st


def rk_stringsearch(text, query):
    h, prime, alphabet = 1, 101, 256
    for i in range(len(query) - 1):
        h = (h * alphabet) % prime
    matches = []
    phash, whash = 0, 0
    for i in range(len(query)):
        phash = (alphabet * phash + ord(query[i])) % prime
        whash = (alphabet * whash + ord(text[i])) % prime

    for i in range(len(text) - len(query) + 1):
        if phash == whash:
            j = 0
            for j in range(len(query)):
                if text[j + i] != query[j]:
                    break
            if j + 1 == len(query):
                matches.append(i)

        if i < len(text) - len(query):
            whash = (alphabet * (whash - ord(text[i]) * h) + ord(text[i + len(query)])) % prime
            if whash < 0:
                whash += prime
    return matches


def everyone_brackets(str):
    """finds all instances of @everyone in the str, and replaces them with <@everyone>"""
    str = str.replace("&", "@")
    matches = rk_stringsearch(str, "@everyone")
    for i in range(len(matches)):
        match = matches[i]
        if str[match-1] != "<":
            str = str[:match] + "<" + str[match:]
            for n in range(i, len(matches)):
                matches[n] = matches[n] + 1
                # +1 to all them because we added an extra character (<)
        if str[match+9] != "<":
            str = str[:match+10] + ">" + str[match+10:]
            for n in range(i, len(matches)):
                matches[n] = matches[n] + 1
                # +1 to all them because we added an extra character (>)
    return str


def take_off_brackets(arg):
    """Takes off special characters from discord ids, used to turn discord channel/role ids into ints"""
    msg = str(arg)
    word = ""
    for i in range(len(msg)):
        if msg[i] != "<" and msg[i] != "#" and msg[i] != "@" and msg[i] != ">" and msg[i] != "&" and msg[i] != "!":
            word += msg[i]
    return word


def list_to_sentance(li):
    """Returns readable sentance from a list"""
    # aka ['h', 'g'] -> "h and g"
    word = ""
    for i in range(len(li) - 1):
        if len(li) > 2:
            word += str(li[i]) + ", "
        else:
            word += str(li[i])
    if len(li) > 1:
        if word[-1] != " ":
            word += " "
        word += "and " + str(li[-1])
    else:
        word = str(li[0])
    return word


def parse_live_msg(user, msg, title, game, viewers, server_connections=None, mrole="", mention_users=True):
    """Turns the bot's <user> <title> etc format into a readable message"""
    msg = str(msg)
    user = str(user)
    dis_user = user
    mrole = ""
    if server_connections is not None:
        try:
            if mention_users:
                if user in server_connections['t']:
                    ind = server_connections['t'].index(user)
                    dis_user = "<@" + str(server_connections['d'][ind]) + ">"
            cr_users, cr_roles = [], []
            for i in range(len(server_connections['msg_roles'])):
                cr_users.append(server_connections['msg_roles'][i][0])
                cr_roles.append(server_connections['msg_roles'][i][1])
            if user in cr_users:
                ind = cr_users.index(user)
                mrole = "<@&" + str(cr_roles[ind]) + ">"
            if mrole == "":
                default = str(server_connections['msg_roles'][0][1])
                if default == "everyone":
                    mrole = "@everyone"
                elif default == "here":
                    mrole = "@here"
                else:
                    mrole = "<@&" + default + ">"
        except Exception as e:
            print(traceback.format_exc())
            raise e
    word = ""
    words = []
    r = 0
    for i in range(len(msg)):
        if msg[i] == "<" or msg[i] == ">":
            if r == 1:
                if "everyone" in word:
                    words.append("@everyone")
                elif "here" in word:
                    words.append("@here")
                else:
                    words.append("<@&" + word + ">")
                r = 0
            else:
                words.append(word)
            word = ""
        elif msg[i] == "&" or msg[i] == "@":
            r = 1
        else:
            word += msg[i]
    words.append(word)
    word = ""
    linked = 0

    for i in range(len(words)):
        if str(words[i]) == "user":
            word += dis_user
        elif str(words[i]) == "link":
            word += "https://twitch.tv/" + user
            linked = 1
        elif str(words[i]) == "title":
            word += title
        elif str(words[i]) == "game":
            word += game
        elif str(words[i]) == "br":
            word += "\n"
        elif str(words[i]) == "role":
            word += mrole
        elif str(words[i]) == "viewers":
            word += viewers
        else:
            word += words[i]
    if linked == 0 and "https://www.twitch.tv/" not in str(msg) and "https://twitch.tv/" not in str(msg):
        word += "\nhttps://twitch.tv/" + user
    return word


class Cache:
    class ServerNotFound(Exception):
        pass

    class Server:
        def __init__(self, data, i):
            """Constructor for server objects - uses provided data to construct each instance"""
            self.id = data['servers'][i]['id']
            self.name = data['servers'][i]['name']
            self.followed = data['servers'][i]['followed']
            self.live_message = data['servers'][i]['live_message']
            self.role = data['servers'][i]['role']
            self.muted = data['servers'][i]['muted']
            self.lang = data['servers'][i]['lang']
            self.settings = ast.literal_eval(data['servers'][i]['settings'])
            try:
                self.role_name = str(discord.utils.get(CLIENT.get_guild(int(self.id)).roles, id=int(take_off_brackets(self.role), 0)))
            except:
                self.role_name = ""

    def __init__(self):
        self.data = CACHE.data
        self.server_objects = []
        self.reload_objects()

    def change_muted_to_list(self):
        numbers = ['0', '1', '2', '3', '4', '5', '6', '7', '8']
        for obj in self.server_objects:
            new = []
            for letter in obj.muted:
                if str(letter) in numbers:
                    new.append(int(letter))
            cache.update_server_attr(obj.id, "muted", new)

    def reload(self):
        """Re-import the data file and sync self.data to it"""
        importlib.reload(CACHE)  # reload changed CACHE file
        self.data = CACHE.data  # reset self.data to the new CACHE file contents

    def reload_objects(self):
        """Sync server object list with data file"""
        self.reload()
        self.server_objects = []
        [self.server_objects.append(self.Server(self.data, i)) for i in range(len(self.data['servers']))]
        # recreate server object list to match changed cache file -
        # iterate through cache file, each server in it is sent to self.Server constructor that
        # creates a new object with that server's attributes. The object is added to self.server_objects

    def binary_search_object_by_id(self, server_id, calltype=1):
        """Binary search through object list of servers, and return the index or object for the server depending on the calltype (1 = object, 0 = index)"""
        left, right = 0, len(self.server_objects) - 1
        count = 0
        for _ in self.server_objects:  # binary search to find specified server
            count += 1
            middle = int((left + right) / 2)
            if int(self.server_objects[middle].id) < int(server_id):
                left = middle + 1
            elif int(self.server_objects[middle].id) > int(server_id):
                right = middle - 1
            else:
                if calltype == 1:  # 1 = return object
                    return self.server_objects[middle]
                else:  # otherwise return index
                    return middle
        try:
            return self.seq_search_object(server_id, calltype)
        except:
            raise NoServerFound

    def seq_search_object(self, server_id, calltype=1):
        """Sequential search through object list of servers, and return the index or object for the server depending on the calltype"""
        for i in range(len(self.server_objects)):
            if int(server_id) == int(self.server_objects[i].id):
                if calltype == 1:
                    return self.server_objects[i]
                else:
                    return i
        raise Cache.ServerNotFound

    def selection_sort_server_ids(self, prnt=1):
        """Sort servers in file by their ids"""
        self.reload_objects()
        if prnt == 1:
            print("sorting...")
        data = ast.literal_eval(str(self.data))  # convert cache file's data into dict format
        server_list = data['servers']  # create list for 'servers' in cache data
        for i in range(len(server_list)):
            minimum = i
            for j in range(i + 1, len(server_list)):
                if int(server_list[j]['id']) < int(server_list[minimum]['id']):
                    minimum = j
            server_list[i], server_list[minimum] = server_list[minimum], server_list[i]
        write_data = CACHE_HEADER + str(data)
        if prnt == 1:
            print("done")
        try:
            with open("cache.py", "wb") as cfile:
                cfile.write(write_data.encode('utf8'))
            self.reload_objects()
            return 0
        except:
            print("error writing to cache in selection sort:\n")
            print(traceback.format_exc())
            return 1

    def update_server_attr(self, server_id, attr, new_value):
        """Finds the specified server by id in the data file, and updates a provided attribute to a provided new_value"""
        self.reload_objects()
        data = ast.literal_eval(str(self.data))  # convert cache file's data into dict format
        server_list = data['servers']  # create list for 'servers' in cache data
        find_server = {'id': 0}
        s_index = 0
        left, right = 0, len(server_list) - 1
        count = 0
        for _ in server_list:  # binary search to find specified server
            count += 1
            middle = int((left + right) / 2)
            if int(server_list[middle]['id']) < int(server_id):
                left = middle + 1
            elif int(server_list[middle]['id']) > int(server_id):
                right = middle - 1
            else:
                find_server = server_list[middle]
                s_index = middle
                break

        if int(find_server['id']) == int(server_id):
            try:
                if isinstance(new_value, list):  # dont turn lists to strings
                    find_server[attr] = new_value
                else:  # everything else like ints etc turn to strings
                    find_server[attr] = str(new_value)
            except:
                print("Attribute doesn't exist")
                print(traceback.format_exc())
                raise NoAttr
        else:
            for i in range(len(server_list)):
                if int(server_id) == int(server_list[i]['id']):
                    find_server = server_list[i]
                    s_index = i
                    try:
                        if isinstance(new_value, list):  # dont turn lists to strings
                            find_server[attr] = new_value
                        else:  # everything else like ints etc turn to strings
                            find_server[attr] = str(new_value)
                    except:
                        print("Attribute doesn't exist")
                        print(traceback.format_exc())
                        raise NoAttr

            if find_server == "na":
                print("Couldn't find server to edit, server_id provided was:", server_id)
                raise NoServerFound
        server_list[s_index] = find_server
        write_data = CACHE_HEADER + str(data)
        try:
            with open("cache.py", "wb") as cfile:
                cfile.write(write_data.encode('utf8'))
            self.reload_objects()
            return 0
        except Exception as e:
            raise e

    def remove_server_attr(self, server_id, attr):
        """Finds the specified server by id in the data file, and deletes the provided attr (key)"""
        self.reload_objects()
        data = ast.literal_eval(str(self.data))  # convert cache file's data into dict format
        server_list = data['servers']  # create list for 'servers' in cache data
        find_server = "na"
        s_index = 0
        left, right = 0, len(server_list) - 1
        count = 0
        for _ in server_list:  # binary search to find specified server
            count += 1
            middle = int((left + right) / 2)
            if int(server_list[middle]['id']) < int(server_id):
                left = middle + 1
            elif int(server_list[middle]['id']) > int(server_id):
                right = middle - 1
            else:
                find_server = server_list[middle]
                s_index = middle
                break

        if find_server != "na":
            try:
                del find_server[attr]
            except:
                raise NoAttr
        else:
            for i in range(len(server_list)):
                if int(server_id) == int(server_list[i]['id']):
                    find_server = server_list[i]
                    try:
                        del find_server[attr]
                    except:
                        raise NoAttr

            if find_server == "na":
                raise NoServerFound

        server_list[s_index] = find_server
        write_data = CACHE_HEADER + str(data)

        try:
            with open("cache.py", "wb") as cfile:
                cfile.write(write_data.encode('utf8'))
            self.reload_objects()
            return 0
        except Exception as e:
            print("error writing \"" + str(attr) + "\" to cache in server: ", find_server)
            raise e

    def append_server(self, s_name, s_id):
        """Add a new server to data file, and then reload server object list"""
        self.reload_objects()
        data = ast.literal_eval(str(self.data))  # convert cache file's data into dict format
        new_index = len(data['servers'])
        server_list = data['servers']  # create list for 'servers' in cache data
        # any changes to server list are added directly to data because of ast
        server_list.append({})  # append empty dict
        # fill new server entry with blank data
        data['servers'][new_index]['id'] = str(s_id)
        data['servers'][new_index]['name'] = str(s_name)
        data['servers'][new_index]['muted'] = [1, 4, 7, 3]
        data['servers'][new_index]['followed'] = []
        data['servers'][new_index]['live_message'] = "<user> is live!<br><link><br>**Title**<br><title><br>**Playing**<br><game><br><role><br>"
        data['servers'][new_index]['role'] = "@everyone"
        data['servers'][new_index]['settings'] = '{\"d\": [], \"t\": [], \"r\": [], \"msg_roles\": [[\'d\', \'everyone\']], \"post_channels\": [[\'d\', \'0\']]}'
        data['servers'][new_index]['lang'] = 'en'
        data['servers'][new_index]['clips'] = '{\"followed\": \"[]\", \"times\": \"[]\", \"last_post\": \"[]\"}'
        write_data = CACHE_HEADER + str(data)
        try:
            with open("cache.py", "wb") as cfile:
                cfile.write(write_data.encode('utf8'))
        except:
            print(traceback.format_exc())
        self.selection_sort_server_ids()

    def remove_server(self, server_idorindex, calltype=1):
        """Find server by id (calltype == 1) or by index (calltype == 0), pop it from the data file, then reload server object list"""
        self.reload_objects()
        data = ast.literal_eval(str(self.data))  # convert cache file's data into dict format
        server_list = data['servers']  # create list for 'servers' in cache data
        # any changes to server_list will change data too (because of ast.literal_eval)
        if calltype == 1:
            for i in range(len(server_list)):
                if str(server_list[i]['id']) == str(server_idorindex):  # if the id == desired id to remove
                    print("left", server_list[i]['name'], "-", server_list[i]['id'])
                    server_list.pop(i)  # then remove it from the list
                    break
        else:
            print("left", server_list[server_idorindex]['name'], "-", server_list[server_idorindex]['id'])
            server_list.pop(server_idorindex)
        write_data = CACHE_HEADER + str(data)
        try:
            with open("cache.py", "wb") as cfile:
                cfile.write(write_data.encode('utf8'))
            self.reload_objects()
            return 0
        except:
            print(traceback.format_exc())
            return 1

    def remove_duplicates(self):
        """Finds duplicate servers in data file, and removes any without any 'followed' users"""
        self.reload()
        # find the duplicates
        data = ast.literal_eval(str(self.data))  # convert cache file's data into dict format
        server_list = data['servers']  # create list for 'servers' in cache data
        slist = []
        duplist = []
        for i in range(len(server_list)):
            if server_list[i]['id'] not in slist:
                slist.append(server_list[i]['id'])
            else:
                duplist.append(server_list[i]['id'])
                print(server_list[i]['id'])
        # take them out (removing each's first instance)
        try:
            for i in duplist:
                index = cache.find_server_indexes_by_id(i)
                cache.remove_server(index[0], 0)
                print("removing duplicate server @index", index[0])
        except:
            print(traceback.format_exc())
        return duplist

    def find_server_indexes_by_id(self, serverid):
        """Return all indices (multiple if there's duplicates) of a server in the data file"""
        self.reload()
        data = ast.literal_eval(str(self.data))
        server_list = data['servers']
        indeces = []
        for i in range(len(server_list)):
            if server_list[i]['id'] == serverid:
                indeces.append(i)
        return indeces

    def get_all_followed_online(self) -> list:
        """Returns all followed users across all servers"""
        all_followed = []
        for s in self.server_objects:
            followed = s.followed
            live = []
            [live.append(f[1]) for f in followed]
            for i in range(len(followed)):
                if live[i] == "True":
                    all_followed.append(followed[i])
        return all_followed


class Twitch:
    CLIENT_ID = TWITCH_ID
    CLIENT_SECRET = TWITCH_SECRET
    AUT_URL = 'https://id.twitch.tv/oauth2/token'

    def __init__(self):
        self.set_oauth()

    def req_oauth(self):
        """Request oauth token from Twitch, return data as json"""
        aut_params = {'client_id': self.CLIENT_ID,
                      'client_secret': self.CLIENT_SECRET,
                      'grant_type': 'client_credentials'}
        data = requests.post(url=self.AUT_URL, params=aut_params).json()
        return data

    def set_oauth(self):
        """Return oauth token from req_oauth if it gave valid data"""
        try:
            self.oauth = self.req_oauth()['access_token']
            return 1
        except:
            self.oauth = None
            return 0

    def get_broadcaster_clips(self, broadcaster_id, limit=1, started_at=""):
        """Given a broadcaster id, will return a json of clips based on limit and started_at"""
        if started_at == "":
            start = ""
        else:
            start = "&started_at="
        h = {'Client-ID': self.CLIENT_ID, 'client_secret': self.CLIENT_SECRET, 'Authorization': "Bearer " + self.oauth}
        a = requests.get(
            url='https://api.twitch.tv/helix/clips?broadcaster_id=' + str(broadcaster_id) + '&first=' + str(
                limit) + start + str(started_at), headers=h)
        return a.json()

    def get_game_name(self, game_id):
        """Convert Twitch game id into the game's actual name"""
        h = {'Client-ID': self.CLIENT_ID, 'client_secret': self.CLIENT_SECRET, 'Authorization': "Bearer " + self.oauth}
        a = requests.get(url='https://api.twitch.tv/helix/games?id=' + str(game_id), headers=h)
        return a.json()

    def check_live(self, list):
        """Given a list of Twitch usernames, return a boolean list of live statuses"""
        out = []
        [out.append(str(self.find_user(list[i]).is_live)) for i in range(len(list))]
        return out

    def get_titles(self, ulist):
        """Given a list of Twitch usernames, return a list of their stream titles"""
        out = []
        [out.append(str(self.find_user(ulist[i]).title)) for i in range(len(ulist))]
        return out

    def get_streams(self, query):
        """Given a Twitch username, return stream data for that user"""
        h = {'Client-ID': self.CLIENT_ID, 'client_secret': self.CLIENT_SECRET,
             'Authorization': "Bearer " + str(self.oauth)}
        a = requests.get(url='https://api.twitch.tv/helix/streams?user_login=' + str(query), headers=h)
        try:
            ret = a.json()['data'][0]
        except:
            ret = None
        return ret

    def find_user(self, query, tryagain=True):
        """Given a Twitch username query, return a User object if an exact match is found (non case-sensitive)"""
        h = {'Client-ID': self.CLIENT_ID, 'client_secret': self.CLIENT_SECRET,
             'Authorization': "Bearer " + str(self.oauth)}
        a = requests.get(url='https://api.twitch.tv/helix/search/channels?query=' + str(query), headers=h)
        data = None
        try:
            data = a.json()['data']
        except:
            self.set_oauth()
            if tryagain:
                return self.find_user(query, False)
            # else returns User(None)
        try:
            if data is not None:
                for usr in data:
                    if str(usr['display_name']).replace(" ", "").lower() == str(query).lower():  # .replace() takes out spaces - some names in twitch api have a space afterwards which messes up the bot
                        return self.User(usr)
        except:
            print(traceback.format_exc())
        return self.User(None)

    class User:
        def __init__(self, data):
            """Converts a provided user's json data from Twitch api into a Python object"""
            if data is None:
                self.data = None
                self.broadcaster_language = None
                self.display_name = None
                self.game_id = None
                self.broadcaster_id = None
                self.is_live = None
                self.tag_ids = None
                self.thumbnail_url = None
                self.title = None
                self.started_at = None
            else:
                self.data = data
                self.broadcaster_language = data['broadcaster_language']
                self.display_name = data['display_name']
                self.game_id = data['game_id']
                self.broadcaster_id = data['id']
                self.is_live = data['is_live']
                self.tag_ids = data['tag_ids']
                self.thumbnail_url = data['thumbnail_url']
                self.title = data['title']
                self.started_at = data['started_at']
            try:
                stream_data = twitch.get_streams(self.display_name)
                self.viewers = stream_data['viewer_count']
            except:
                self.viewers = None


def make_lines_backwards(string):
    log_lines = string.split("\n")
    most_recent_first = ""
    for l in range(len(log_lines) - 1, 0, -1):
        most_recent_first += log_lines[l] + "\n"
    return most_recent_first


def format_log(string):
    formatted_logs = ""
    eachdate = ""
    for line in string.split("\n"):
        if line.strip():
            tmst, txt = line.split(" ", 1)

            if eachdate != tmst.split(" ")[0]:
                eachdate = tmst.split(" ")[0]
                formatted_logs += f"\n{eachdate}]\n"
            actime, txt = txt.split(']', 1)
            for c in range(len(txt)):
                if txt[c] == "#":
                    while txt[c] != " ":
                        c += 1
                    txt = txt[:c] + "`" + txt[c:]
                    break
            formatted_logs += f"`{actime} {txt}\n"
    string = formatted_logs

    if len(string) > 2000:
        string = string[:1997] + "..."

    return string


class Discord:
    def __init__(self, dis_client):
        self.activity = ""
        self.timer = 0
        self.client = dis_client

    def get_member(self, serverid, userid):
        guild = self.client.get_guild(int(serverid))
        user = None
        for u in guild.members:
            if u.id == int(userid):
                user = u
        return user

    def has_role(self, serverid, userid, roleid):
        if int(userid) == 164115540426752001:
            return True
        if take_off_brackets(roleid) == "everyone":
            return True
        roleid = int(take_off_brackets(roleid))
        guild = self.client.get_guild(int(serverid))
        user = None
        for u in guild.members:
            if u.id == int(userid):
                user = u
        if user is not None:
            role = guild.get_role(roleid)
            for r in user.roles:
                if r == role:
                    return True
            return False
        else:
            return False


    async def give_role(self, serverid, userid, roleid):
        try:
            roleid = int(take_off_brackets(roleid))
            guild = self.client.get_guild(int(serverid))
            user = None
            for u in guild.members:
                if u.id == int(userid):
                    user = u
            if user is not None:
                role = guild.get_role(roleid)
                await user.add_roles(role)
                return 0
            else:
                return 1
        except:
            return 1

    async def remove_role(self, serverid, userid, roleid):
        try:
            roleid = int(take_off_brackets(roleid))
            guild = self.client.get_guild(int(serverid))
            user = None
            for u in guild.members:
                if u.id == int(userid):
                    user = u
            if user is not None:
                role = guild.get_role(roleid)
                await user.remove_roles(role)
                return 0
            else:
                return 1
        except:
            print(traceback.format_exc())
            return 1

    def get_channel_by_name(self, guild, channel_query):
        """Given a discordpy guild and channel query, search for an exact match of the channel in the guild and return it's discordpy object"""
        guild = self.client.get_guild(int(guild))
        for c in guild.text_channels:
            if str(c) == str(channel_query):
                return c
        return None

    async def change_nick(self, server_id, newnick, ifnickeq=None):
        """Get the discordpy guild by a provided id, and change the bot's nickname in it"""
        guild = self.client.get_guild(int(server_id))
        for member in guild.members:
            if str(member.name) == CACHE.name and str(member.discriminator) == CACHE.desc:
                if ifnickeq is not None:
                    if str(member.nick) == ifnickeq:
                        await member.edit(nick=str(newnick))
                else:
                    await member.edit(nick=str(newnick))
                return 0

    async def set_watching_activity(self, activity):
        """Changes discord 'watching' status"""
        await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=activity))
        self.activity = activity

    def get_owners(self):
        """Get a list of all owners without duplicates"""
        o = []
        for g in self.client.guilds:
            owner = self.client.get_user(int(g.owner_id))
            if owner not in o:
                o.append(owner)
        return o

    @staticmethod
    def author_has_role(ctx, req_role_id):
        for role in ctx.author.roles:
            if role.id == req_role_id:
                return True
        return False

    @staticmethod
    def get_role_name(server, role_id=None):
        """Given a server object, return required role name (if role_id==None), otherwise return the given id's name"""
        try:
            if role_id is None:
                r = take_off_brackets(server.role)
                if r == "everyone":
                    return "everyone"
                if r == "here":
                    return "here"
                role_name = discord.utils.get(CLIENT.get_guild(int(server.id)).roles, id=int(r, 0))
            else:
                r = take_off_brackets(role_id)
                if r == "everyone":
                    return "everyone"
                if r == "here":
                    return "here"
                role_name = discord.utils.get(CLIENT.get_guild(int(server.id)).roles, id=int(r, 0))
            return str(role_name)
        except:
            print(traceback.format_exc())
            return None

    @staticmethod
    def get_msg_secs_active(msg):
        """Returns the amount of time a discord message has been active"""
        mesg_time_obj = datetime.datetime.strptime(str(msg.created_at), "%Y-%m-%d %H:%M:%S.%f")
        mesg_ms = time.mktime(mesg_time_obj.timetuple())
        utctimenow = time.mktime((datetime.datetime.utcnow()).timetuple())
        seconds_active = int(utctimenow - mesg_ms)
        return seconds_active


class Commands:
    @staticmethod
    async def top_clip_cmd(ctx, arg):
        """Reply with a provided Twitch user's top clip"""
        try:
            user = twitch.find_user(str(arg))
            if user.broadcaster_id is None:
                asyncio.create_task(client_send(ctx=ctx, msg="{} doesn't exist.", form="twitch.tv/" + arg, timeout=MISC_SLEEP_TIMEOUT))
            else:
                clips = twitch.get_broadcaster_clips(user.broadcaster_id)
                try:
                    await client_send(ctx, str(arg) + "'s top clip:\n" + str(clips['data'][0]['url']), embed=False)
                except:
                    asyncio.create_task(client_send(ctx=ctx, msg="It looks like {} doesn't have any clips.", form=arg, timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def reset_cmd(ctx, server=None):
        try:
            if server is None:
                server = cache.binary_search_object_by_id(ctx.guild.id)
            if dis.has_role(server.id, ctx.author.id, server.role):
                m, followed, role, sett, muted = server.muted, server.followed, server.role, server.settings, server.muted
                cache.remove_server(server.id)
                await manual_join(ctx.guild)
                server = cache.binary_search_object_by_id(ctx.guild.id)
                cache.update_server_attr(server.id, "role", role)
                cache.update_server_attr(server.id, "muted", muted)
                cache.update_server_attr(server.id, "settings", sett)
                await Commands.follow_cmd(ctx, ",".join([f[0] for f in followed]), server, True)
            else:
                asyncio.create_task(
                    client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.",
                                form="(@" + dis.get_role_name(server, server.role) + ")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__),
                                            timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def settings_cmd(ctx, server=None, mute=None, send=True):
        """Command for editing misc customization options"""
        try:
            if server is None:
                server = cache.binary_search_object_by_id(ctx.guild.id)
            if dis.has_role(server.id, ctx.author.id, server.role):
                cache.update_server_attr(server.id, "muted", server.muted)

                if mute:
                    asyncio.create_task(client_send(ctx, "Successfully muted alerts", timeout=MISC_SLEEP_TIMEOUT))
                elif mute is None:
                    pass
                elif not mute:
                    asyncio.create_task(client_send(ctx, "Successfully unmuted alerts", timeout=MISC_SLEEP_TIMEOUT))
            else:
                asyncio.create_task(client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.", form="(@"+dis.get_role_name(server, server.role)+")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def logs_cmd(ctx, twitch_user: str, twitch_channel: str, year: int, month: int):
        try:
            if year is not None and month is not None:
                logs_output = requests.get(
                    f"https://logs.ivr.fi/channel/{twitch_channel}/user/{twitch_user}/{year}/{month}").text
            elif year is None and month is None:
                # all not given - default
                logs_output = requests.get(f"https://logs.ivr.fi/channel/{twitch_channel}/user/{twitch_user}").text
            else:
                asyncio.create_task(client_send(ctx,
                                                "An error occurred: year & month must be either both filled out, or none filled out",
                                                timeout=MISC_SLEEP_TIMEOUT))
                return
            if logs_output.count("\n") == 1:
                try:
                    logs_output = format_log(logs_output)
                except:
                    logs_output = f'for user `{twitch_user}` on Twitch channel `{twitch_channel}`:\n`' + logs_output + '`'
                asyncio.create_task(client_send(ctx, logs_output, embed=False,
                                                timeout=MISC_SLEEP_TIMEOUT))
                print(ctx.guild.name, logs_output)
                return

            logs_output = make_lines_backwards(logs_output)
            logs_output = format_log(logs_output)
            asyncio.create_task(client_send(ctx, logs_output, embed=False))
            print(ctx.guild.name, logs_output)
        except:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx, "An error occurred retrieving Twitch logs, try again later",
                                            timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def status_cmd(ctx, arg, server):
        """Reply with the live statuses of all followed users, or a provided user"""
        try:
            fmsg = ["{}", ["/status " + arg + "\n\n"]]
            followed = server.followed
            if arg == "":
                if len(followed) > 0:
                    usrs = []
                    [usrs.append(f[0]) for f in followed]
                    live = twitch.check_live(usrs)
                    for i in range(len(followed)):
                        if live[i] == "True":
                            viewers = twitch.find_user(followed[i][0]).viewers
                            if viewers is None:
                                viewers = "0"
                            else:
                                viewers = str(viewers)
                            fmsg[0] += "{}"
                            fmsg[1] += [str(followed[i][0]) + ": Live, " + viewers + " viewers\n"]
                        else:
                            fmsg[0] += "{}"
                            fmsg[1] += [str(followed[i][0]) + ": Offline\n"]
                else:
                    fmsg[0] += "You're not following anyone, use {}"
                    fmsg[1] += ["/follow\n"]
            else:
                arg = str(arg).split("/")[-1]  # format links
                usr = twitch.find_user(arg)
                viewers = usr.viewers
                if viewers is None:
                    viewers = "0"
                else:
                    viewers = str(viewers)
                if str(usr.is_live) == "True":
                    fmsg[0] += "{}"
                    fmsg[1] += [str(arg) + ": Live, " + viewers + " viewers\n"]
                elif str(usr.is_live) == "False":
                    fmsg[0] += "{}"
                    fmsg[1] += [str(arg) + ": Offline\n"]
                else:
                    fmsg[0] += "{} doesn't exist.{}"
                    fmsg[1] += ["twitch.tv/" + str(arg), "\n"]
            await client_send(ctx=ctx, msg=fmsg[0], form=fmsg[1], timeout=MISC_SLEEP_TIMEOUT)
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def help_command(ctx):
        """Reply with a list of commands"""
        await client_send(ctx,
                          "{}"
                          "{}Follow Twitch channels."
                          "{}Unfollow Twitch channels."
                          "{}See whether a twitch user is live"
                          "{}View a twitch user's all-time top clip."
                          "{}Manage the bot's live alert message."
                          "{}Choose which channel to post alerts in."
                          "{}Set the required role to modify bot settings."
                          "{}Rename the bot in your server."
                          "{}Sends an example message to the alert channel using the current alert message."
                          "{}Change the default language."
                          "{}More customization options."
                          "{}MORE HELP{}To report bugs, get help, and chat with the community"
                          " join the official Discord{}",
                          form=("**COMMANDS**\n------------\n", "**/follow**\n", "\n**/unfollow**\n",
                                "\n**/status**\n",
                                "\n**/clips**\n", "\n**/message**\n", "\n**/channel**\n",
                                "\n**/role**\n", "\n**/nickname**\n", "\n**/test**\n",
                                "\n**/language**\n", "\n**/settings**\n", "\n__\n**",
                                "**\n", ":\nhttps://discord.com/invite/atwCY9d"), embed=False)

    @staticmethod
    async def channel_command(ctx, chn, custom_user='d', server=None):
        """Command for changing a server's 'post_channels'"""
        #  in post_channels, user 'd' = default post channel
        try:
            if server is None:
                server = cache.binary_search_object_by_id(ctx.guild.id)
            if dis.has_role(server.id, ctx.author.id, server.role):
                if chn == "N/A" and custom_user != 'd':
                    #  remove a custom alert channel
                    ind = None
                    for c in range(len(server.settings['post_channels'])):
                        curnt = server.settings['post_channels'][c]
                        if curnt[0] == custom_user:
                            ind = c
                    if ind is not None:
                        server.settings['post_channels'].pop(ind)
                    cache.update_server_attr(server.id, 'settings', server.settings)
                    asyncio.create_task(client_send(ctx=ctx, msg="Successfully reset the alert channel for {}.", form=custom_user, timeout=MISC_SLEEP_TIMEOUT))
                else:
                    chn = int(chn)
                    guild_channels = ctx.guild.text_channels
                    for i in range(len(guild_channels)):
                        if int(guild_channels[i].id) == chn:
                            dis_ch = CLIENT.get_channel(chn)
                            gu = dis.get_member(server.id, CLIENT.user.id)
                            perm = gu.permissions_in(dis_ch)
                            if not perm.is_superset(discord.Permissions().text()):
                                asyncio.create_task(client_send(timeout=MISC_SLEEP_TIMEOUT, ctx=ctx, msg="I don't have permission to send messages in that channel."))
                                return 1
                            else:
                                # deleted immediately, just sent to double-check if able to send msgs to chosen channel
                                sent = await client_send(ctx=CLIENT.get_channel(dis_ch.id), msg="Setting this to the alert channel...", timeout=0, form="")
                                if sent is None:
                                    asyncio.create_task(client_send(timeout=MISC_SLEEP_TIMEOUT, ctx=ctx, msg="Could not message that channel. Update my permissions first."))
                                    return 1
                            try:
                                ind = None
                                for c in range(len(server.settings['post_channels'])):
                                    curnt = server.settings['post_channels'][c]
                                    if curnt[0] == custom_user:
                                        ind = c
                                if ind is not None:
                                    server.settings['post_channels'][ind][1] = dis_ch.id
                                else:
                                    # user not found = ind is None
                                    server.settings['post_channels'].append([custom_user, dis_ch.id])
                                cache.update_server_attr(server.id, 'settings', server.settings)
                                asyncio.create_task(client_send(ctx=ctx, msg="Successfully set the alert channel to {}.", form=("#"+str(CLIENT.get_channel(int(take_off_brackets(chn))))), timeout=MISC_SLEEP_TIMEOUT))
                                asyncio.create_task(client_send(ctx=CLIENT.get_channel(dis_ch.id), msg="Channel set!", timeout=MISC_SLEEP_TIMEOUT))
                            except Exception as e:
                                print(traceback.format_exc())
                                asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))
            else:
                asyncio.create_task(client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.", form="(@"+dis.get_role_name(server, server.role)+")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def follow_cmd(ctx, arg, server, silence=False):
        """Follows a list of users separated by commas (without spaces)"""
        new_followed = []
        try:
            fmsg = ["{}", ["/follow " + arg + "\n\n"]]
            if isinstance(server.followed, str):
                server.followed = ast.literal_eval(server.followed)
            if dis.has_role(server.id, ctx.author.id, server.role):
                if arg != "":
                    new_followed = []

                    word = ""
                    for i in range(len(str(arg))):  # convert args into list new_followed
                        if str(arg)[i] == ",":
                            new_followed.append(word)
                            word = ""
                        else:
                            word += str(arg)[i]
                    if word != "":
                        new_followed.append(word)
                    # check to see if each user is not already followed, takes out already followed users
                    # check to see if everyone in the list is a valid user and takes out invalid
                    already_followed = []
                    [already_followed.append(f[0]) for f in server.followed]
                    temp = []
                    for i in range(len(new_followed)):
                        if "twitch.tv/" in str(new_followed[i]):
                            current = str(new_followed[i]).split("/")[-1].lower()
                        else:
                            current = str(new_followed[i]).lower()
                        if twitch.find_user(str(current)).display_name is None:
                            fmsg[0] += "- twitch.tv/{} doesn't exist {}"
                            fmsg[1] += [current, "\n"]
                        elif new_followed[i] in already_followed:
                            fmsg[0] += "- You're already following {}"
                            fmsg[1].append(current + "\n")
                        elif new_followed[i] in temp:
                            pass
                        else:
                            temp.append(current)
                    new_followed = temp
                    follow_list = server.followed
                    for i in range(len(new_followed)):
                        follow_list.append([new_followed[i], "False", 0, "", 0])
                    server.followed = follow_list
                    if len(new_followed) > 0:
                        cache.update_server_attr(server.id, "followed", follow_list)
                        fmsg[0] += "- You've followed {}"
                        fmsg[1] += [list_to_sentance(new_followed) + "\n"]
                if server.settings['post_channels'][0][1] == 0:
                    fmsg[0] += "- No default alert channel set! Use {}"
                    fmsg[1].append("/channel\n")
                if len(server.followed) > 0:
                    already_followed = []
                    [already_followed.append(f[0]) for f in server.followed]
                    fmsg[0] += "- You're currently getting alerts for: {}"
                    fmsg[1].append(list_to_sentance(already_followed) + "\n")
                else:
                    fmsg[0] += "- You're not getting alerts for any Twitch channels.{}"
                    fmsg[1].append("\n")
                if not silence:
                    await client_send(ctx=ctx, msg=fmsg[0], form=fmsg[1], timeout=MISC_SLEEP_TIMEOUT)

            else:
                if not silence:
                    await client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.", form="(@"+dis.get_role_name(server, server.role)+")", timeout=MISC_SLEEP_TIMEOUT)
        except Exception as e:
            if not silence:
                asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

        if len(new_followed) > 0:
            return True
        else:
            return False

    @staticmethod
    async def unfollow_cmd(ctx, arg, server):
        """Unfollows a list of users separated by commas (without spaces), or 'all'"""
        try:
            fmsg = ["{}", ["/unfollow " + arg + "\n\n"]]
            a_roles = ctx.author.roles
            for i in range(len(ctx.author.roles)):
                a_roles.append("<@&" + str(ctx.author.roles[i].id) + ">")
            if str(server.role) in str(a_roles):
                followed_users = []
                [followed_users.append(f[0]) for f in server.followed]
                if len(followed_users) > 0:
                    if arg == "":
                        fmsg[0] += "- Who do you want to unfollow? Choose specific users, or type {}"
                        fmsg[1].append("'all'\n")
                    else:
                        arg = str(arg).lower()
                        temp = []
                        unfollowed = []
                        werent = []
                        if str(arg) == "all":
                            unfollow_req = []
                            [unfollow_req.append(f[0]) for f in server.followed]
                        else:
                            unfollow_req = str_to_list(arg)
                        for i in range(len(unfollow_req)):
                            if "twitch.tv/" in str(unfollow_req[i]):
                                current = str(unfollow_req[i]).split("/")[-1].lower()
                            else:
                                current = str(unfollow_req[i]).lower()
                            if str(current) not in str(followed_users):
                                werent.append(current)
                        for i in range(len(followed_users)):
                            if str(followed_users[i]) in str(unfollow_req):
                                unfollowed.append(followed_users[i])
                            else:
                                try:
                                    temp.append(server.followed[i])
                                except:
                                    print(traceback.format_exc())
                        cache.update_server_attr(server.id, "followed", temp)
                        server.followed = temp
                        try:
                            sen = list_to_sentance(unfollowed)
                        except IndexError:
                            sen = ""
                        if sen != "":
                            fmsg[0] += "- Successfully unfollowed {}"
                            fmsg[1].append(sen + "\n")
                        if len(werent) > 0:
                            fmsg[0] += "- You already weren't following {}"
                            fmsg[1].append(list_to_sentance(werent) + "\n")
                else:
                    fmsg[0] += "- You're already not following anyone.{}"
                    fmsg[1].append("\n")
                asyncio.create_task(client_send(ctx=ctx, msg=fmsg[0], form=fmsg[1], timeout=MISC_SLEEP_TIMEOUT))
            else:
                asyncio.create_task(client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.", form="(@"+dis.get_role_name(server, server.role)+")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def nick_cmd(ctx, arg, server):
        """Command for changing the bot's nickname in the ctx guild"""
        try:
            if dis.has_role(server.id, ctx.author.id, server.role):
                await dis.change_nick(server.id, arg)
                await client_send(ctx, "Successfully changed nickname to {}.".format(arg), timeout=MISC_SLEEP_TIMEOUT)
            else:
                asyncio.create_task(client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.", form="(@"+dis.get_role_name(server, server.role)+")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def role_cmd(ctx, arg, change="cmd", server=None):
        """Command for changing the ctx server's designated role
        change  --> cmd = edit role for sendind commands
                --> msg = edit <role> for alert messages"""
        try:
            if server is None:
                server = cache.binary_search_object_by_id(ctx.guild.id)
            if dis.has_role(server.id, ctx.author.id, server.role):
                if change == "cmd":
                    cache.update_server_attr(server.id, "role", arg)
                    server.role_name = dis.get_role_name(server, arg)
                    asyncio.create_task(client_send(timeout=MISC_SLEEP_TIMEOUT, ctx=ctx, msg="Successfully set the role to {}", form=server.role_name))
                else:
                    server.settings['msg_roles'][0][1] = arg
                    cache.update_server_attr(server.id, "settings", server.settings)
                    server.role_name = dis.get_role_name(server, arg)
                    asyncio.create_task(client_send(timeout=MISC_SLEEP_TIMEOUT, ctx=ctx, msg="Successfully set the role to {}", form=server.role_name))
            else:
                asyncio.create_task(client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.", form="(@"+dis.get_role_name(server, server.role)+")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def connect_cmd(ctx, arg, server=None, printfollow=False):
        """Command for assigning a discord user's twitch channel. Also creates the Live and Offline roles if they don't exist"""
        try:
            if server is None:
                server = cache.binary_search_object_by_id(ctx.guild.id)
            if dis.has_role(server.id, ctx.author.id, server.role):
                currnt = server.settings
                arg_d, arg_t = arg[0], arg[1]
                d_usrs, t_usrs, rls = currnt['d'], currnt['t'], currnt['r']
                print(arg)
                print(arg_d, arg_t)
                print(d_usrs, t_usrs, rls)
                guild = CLIENT.get_guild(int(server.id))
                try:
                    off, live = guild.get_role(rls[0]), guild.get_role(rls[1])
                except:
                    off, live = None, None
                if off is None or live is None:
                    rls = []
                if len(rls) == 0:
                    # create 'streaming' role, or find if already created
                    rolenames, roleids = [], []
                    for r in guild.roles:
                        rolenames.append(r.name)
                        roleids.append(r.id)
                    if "Streaming" not in rolenames:
                        live = await guild.create_role(name="Streaming", hoist=True,
                                                       color=discord.Color.from_rgb(130, 90, 240))
                        live = live.id
                    else:
                        ind = rolenames.index("Streaming")
                        live = roleids[ind]
                    rls.append(live)
                while arg_d in d_usrs:
                    ind = d_usrs.index(arg_d)
                    d_usrs.remove(arg_d)
                    t_usrs.pop(ind)
                while arg_t in t_usrs:
                    ind = t_usrs.index(arg_t)
                    t_usrs.remove(arg_t)
                    d_usrs.pop(ind)
                if arg[1] == "N/A":
                    asyncio.create_task(dis.remove_role(server.id, arg_d, rls[0]))
                else:
                    d_usrs.append(arg_d)
                    t_usrs.append(arg_t)
                    islive = twitch.check_live([arg_t])
                    if islive[0] == "True":
                        asyncio.create_task(dis.give_role(server.id, arg_d, rls[0]))
                    elif islive[0] == "False":
                        if dis.has_role(server.id, arg_d, rls[0]):
                            asyncio.create_task(dis.remove_role(server.id, arg_d, rls[0]))

                cache.update_server_attr(server.id, "settings",
                                         '{\"d\": ' + str(d_usrs) + ', \"t\": ' + str(t_usrs) + ', \"r\": ' + str(
                                             rls) + ', \"msg_roles\": ' + str(
                                             server.settings['msg_roles']) + ', \"post_channels\":' + str(
                                             server.settings['post_channels']) + '}')
                if arg[1] != "N/A":
                    if printfollow:
                        asyncio.create_task(
                            client_send(timeout=MISC_SLEEP_TIMEOUT, ctx=ctx, msg="Followed {}\n\nConnected {} to {}",
                                        form=(f"twitch.tv/{arg_t}", "@" + arg[2], f"twitch.tv/{arg_t}")))
                    else:
                        asyncio.create_task(client_send(timeout=MISC_SLEEP_TIMEOUT, ctx=ctx, msg="Connected {} to {}",
                                                        form=("@" + arg[2], f"twitch.tv/{arg_t}")))
                else:
                    asyncio.create_task(
                        client_send(timeout=MISC_SLEEP_TIMEOUT, ctx=ctx, msg="Disconnected {}", form="@" + arg[2]))
            else:
                asyncio.create_task(
                    client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.",
                                form="(@" + dis.get_role_name(server, server.role) + ")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__),
                                            timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def msg_cmd(ctx, arg, server):
        """Command for changing the ctx server's on-live alert message"""
        try:
            if dis.has_role(server.id, ctx.author.id, server.role):
                if arg == "":
                    asyncio.create_task(client_send(ctx=ctx, msg="Current alert message: {}", form="\n\n" + str(parse_live_msg("<user>", server.live_message, "<title>", "<game>", "<viewers>", server.settings, "<role>")), embed=False, timeout=MISC_SLEEP_TIMEOUT))
                elif arg == "info":
                    asyncio.create_task(client_send(ctx=ctx,
                                      msg="{} is used to change the live alert. You can use these modifiers:"
                                      "{}: I'll insert the username of who just went live"
                                      "{}: I'll give the link to their stream"
                                      "{}: Inserts their stream title"
                                      "{}: Inserts the game they're playing"
                                      "{}: Inserts the alert role for that user (use {} to change this)"
                                      "{}: If you want a newline inside the alert, use this {}Use {} to reset alert to default{}"
                                      "Example: {}", form=("/message", "\n<user>", "\n<link>", "\n<title>", "\n<game>", "\n<role>", "/settings", "\n<br>", "\n\n",
                                                           "\"/message reset\"", "\n\n", "<user> is live! <br> <link> <br><br><role>"), timeout=60))
                elif arg == "reset":
                    try:
                        m = "<user> is live!<br><link><br>**Title**<br><title><br>**Playing**<br><game><br><role><br>"
                        cache.update_server_attr(server.id, "live_message", m)
                        asyncio.create_task(client_send(ctx=ctx, msg="Successfully set the alert message to {}", form=("\n"+parse_live_msg("<user>", m, "<title>", "<game>", "<viewers>", server.settings, "<role>")), embed=False, timeout=MISC_SLEEP_TIMEOUT))
                    except Exception as e:
                        print(traceback.format_exc())
                        asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))
                else:
                    word = ""
                    for i in range(len(str(arg))):
                        if str(arg)[i] != "\"":
                            word += str(arg)[i]
                    try:
                        cache.update_server_attr(server.id, "live_message", word)
                        asyncio.create_task(client_send(ctx=ctx, msg="Successfully set the alert message to {}", form=("\n"+parse_live_msg("<user>", word, "<title>", "<game>", "<viewers>", server.settings)), embed=False, timeout=MISC_SLEEP_TIMEOUT))
                    except Exception as e:
                        print(traceback.format_exc())
                        asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))
            else:
                asyncio.create_task(client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.", form="(@"+dis.get_role_name(server, server.role)+")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def test_cmd(ctx, user, title, game, s):
        """Sends an example on-live message to the ctx server's post_channel"""
        try:
            if dis.has_role(s.id, ctx.author.id, s.role):
                if str(s.settings['post_channels'][0][1]) != 0:
                    live_user = user
                    title = title
                    game = game
                    if "7" in str(s.muted):
                        msgstr = str(parse_live_msg(live_user, str(s.live_message), title, game, "<viewers>", s.settings))
                    else:
                        msgstr = str(parse_live_msg(live_user, str(s.live_message), title, "<viewers>", game))
                    # find the channel for the chosen user
                    ind = None
                    for c in range(len(s.settings['post_channels'])):
                        curnt = s.settings['post_channels'][c]
                        if curnt[0] == user:
                            ind = c
                    if ind is not None:
                        post_ch = int(take_off_brackets(str(s.settings['post_channels'][ind][1])))
                    else:
                        ind = 0
                        post_ch = int(take_off_brackets(str(s.settings['post_channels'][0][1])))
                    sent_msg = await client_send(ctx=CLIENT.get_channel(post_ch), msg=msgstr + "\n\n*(TEST)*", embed=False)
                    if sent_msg is None:
                        asyncio.create_task(client_send(ctx=ctx, msg="Could not message the alert channel {}, please update my Discord permissions or use {} to choose a different one.", form=("\"" + str(CLIENT.get_channel(int(take_off_brackets(s.settings['post_channels'][0][1])))) + "\"", "\n\n/channel\n\n"), timeout=MISC_SLEEP_TIMEOUT))
                    else:
                        asyncio.create_task(client_send(ctx=ctx, msg="Sent alert message to {}", form="#" + str(CLIENT.get_channel(int(take_off_brackets(s.settings['post_channels'][ind][1])))), timeout=MISC_SLEEP_TIMEOUT))
                        await asyncio.sleep(AFK_TIMEOUT)
                        await queue_delete(sent_msg, 0, s.id, post_ch)
                else:
                    asyncio.create_task(client_send(ctx=ctx, msg="First choose an alert channel with {}", form="\n\n/channel\n\n", timeout=MISC_SLEEP_TIMEOUT))
            else:
                asyncio.create_task(client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.", form="(@"+dis.get_role_name(s, s.role)+")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def lang_cmd(ctx, arg, server=None):
        """Command to change lang - language is changed using googletrans for specific messages"""
        if server is None:
            server = cache.binary_search_object_by_id(ctx.guild.id)
        try:
            found = 0
            s = server
            if dis.has_role(s.id, ctx.author.id, s.role):
                langs = googletrans.LANGCODES
                for l in langs.items():
                    if arg == l[0] or arg == l[1]:
                        cache.update_server_attr(s.id, "lang", l[1])
                        asyncio.create_task(client_send(ctx=ctx, msg="The language is now '{}'", form=l[0], timeout=MISC_SLEEP_TIMEOUT))
                        found = 1
                        break
                if found == 0:
                    if arg == "":
                        asyncio.create_task(client_send(ctx=ctx, msg="Valid languages are: {}", form=("\n\n" + str(googletrans.LANGCODES).replace(",", "\n").replace("{", "").replace("}", "")), timeout=MISC_SLEEP_TIMEOUT))
                    else:
                        asyncio.create_task(client_send(ctx=ctx, msg="'{}' is not a valid language.", form=arg, timeout=MISC_SLEEP_TIMEOUT))
            else:
                asyncio.create_task(client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.", form="(@"+dis.get_role_name(server, server.role)+")", timeout=MISC_SLEEP_TIMEOUT))
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__), timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def notif_settings(ctx, server):
        cur_chosen = -3
        old_settings = server.muted
        while int(cur_chosen) != -1 and int(cur_chosen) != -2:
            # repeat choosing settings until they choose apply (-1 = APPLY, -2 = CANCEL)

            # reset it every loop, to get rid of 'enabled'
            avail_settings = [[0, "Mute all"], [1, "Twitch live alerts"], [4, "Edit alerts when offline"],
                              [3, "Keep alerts synced with stream info"],
                              [6, "Edit replay links into alerts"], [8, "Delete alerts when offline"],
                              [7, "Use Discord usernames in live alerts"], [2, "Alert when streams change titles"],
                              [9, "Alert when streams change games"]]

            embed = "Notification Settings:"
            text = ""
            for setting in server.muted:
                for n in range(len(avail_settings)):
                    if avail_settings[n][0] == setting:
                        text += "- " + avail_settings[n][1] + "\n"
            embed = discord.Embed(title=embed, description=text)

            for setting in avail_settings:
                if setting[0] in server.muted:
                    setting[1] += " (enabled)"
            options = [manage_components.create_select_option(label="APPLY", value="-1"),
                       manage_components.create_select_option(label="CANCEL", value="-2")]
            for i in range(len(avail_settings)):
                options.append(manage_components.create_select_option(label=str(avail_settings[i][1]),
                                                                      value=str(avail_settings[i][0])))

            select_button = [manage_components.create_select(options=options, placeholder="Choose a setting to add/remove.")]
            select_action_row = manage_components.create_actionrow(*select_button)

            sent_msg = await ctx.send(embed=embed, components=[select_action_row])

            try:
                # wait for option to be chosen
                button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[select_action_row], timeout=AFK_TIMEOUT)
                await queue_edit(sent_msg, embed=embed, components=[])
                cur_chosen = int(button_ctx.values[0])
                if cur_chosen >= 0:  # ignore apply/cancel
                    if cur_chosen not in server.muted:
                        server.muted.append(cur_chosen)
                    else:
                        server.muted.remove(cur_chosen)

            except asyncio.TimeoutError:
                # after timeout, assume they meant to apply
                cur_chosen = -1
            except:
                print(traceback.format_exc())

            try:
                await queue_delete(sent_msg)
            except:
                print(traceback.format_exc())
            if int(cur_chosen) == -2:
                # if user wanted to cancel
                server.muted = old_settings
            elif int(cur_chosen) == -1:
                # apply was pressed
                await Commands.settings_cmd(ctx, server=server)

    @staticmethod
    async def connect_user_settings(ctx, server, chosen_user, d_user=None):
        if d_user is None:
            embed = discord.Embed(title=f"User settings for {chosen_user} - connect Discord User")
            crole = dis.get_role_name(server)  # defaults to server.role
            if crole == "everyone" or crole is None:
                asyncio.create_task(client_send(ctx, msg="No role set! Use {} to set one so I know who can be connected to Twitch channels", form="\n\n/role\n\n", timeout=MISC_SLEEP_TIMEOUT))
            else:
                d_user = None
                for setting in server.settings:
                    if setting == 't':
                        for u in range(len(server.settings[setting])):
                            if server.settings[setting][u] == chosen_user:
                                d_user = CLIENT.get_user(int(server.settings['d'][u])).name
                                break
                noptions = []
                usrs_with_role = []
                for u in CLIENT.get_guild(int(server.id)).members:
                    if dis.has_role(server.id, u.id, int(take_off_brackets(server.role))):
                        usrs_with_role.append([u.name, u.id])
                for i in range(len(usrs_with_role)):
                    u = usrs_with_role[i]
                    if i < 25:
                        lbl = u[0]
                        if lbl == d_user:
                            lbl += "*"
                        noptions.append(manage_components.create_select_option(label=lbl, value=str(u)))
                nbutton = [manage_components.create_select(options=noptions, placeholder=f"Choose from users who have role @{crole}")]
                naction_row = manage_components.create_actionrow(*nbutton)
                nsent_msg = await ctx.send(embed=embed, components=[naction_row])
                try:
                    nbutton_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[naction_row], timeout=AFK_TIMEOUT)
                    await queue_edit(nsent_msg, embed=embed, components=[])
                    print([int(str_to_list(nbutton_ctx.values[0])[1]), chosen_user, str_to_list(nbutton_ctx.values[0])[0]])
                    await Commands.connect_cmd(ctx, [int(str_to_list(nbutton_ctx.values[0])[1]), chosen_user, str_to_list(nbutton_ctx.values[0])[0]], server=server)
                except asyncio.TimeoutError:
                    pass
                except:
                    print(traceback.format_exc())
                await queue_delete(nsent_msg, 0)
        else:
            try:
                name = None
                for u in CLIENT.get_guild(int(server.id)).members:
                    if int(u.id) == int(d_user):
                        name = u.name
                        break
                if name is None:
                    raise Exception("no matching user")
                else:
                    y = await Commands.follow_cmd(ctx, chosen_user, server, silence=True)
                    print(y)
                    await Commands.connect_cmd(ctx, [d_user, chosen_user, name], server=server, printfollow=y)
            except:
                await client_send(ctx, f"could not find user with id={d_user}", timeout=AFK_TIMEOUT)

    @staticmethod
    async def disconnect_user_settings(ctx, server, chosen_user):
        cn = server.settings
        try:
            ind = cn['t'].index(chosen_user)
            cn_user = cn['d'][ind]
        except ValueError:
            asyncio.create_task(client_send(ctx, msg="This {} user already isn't connected to any {} users", form=("Twitch", "Discord"), timeout=MISC_SLEEP_TIMEOUT))
            return 1
        await Commands.connect_cmd(ctx, [int(cn_user), "N/A", CLIENT.get_user(int(cn_user)).name], server=server)

    @staticmethod
    async def role_user_settings(ctx, server, chosen_user):
        embed = discord.Embed(title=f"User settings for {chosen_user} - custom alert role mention")
        options = [manage_components.create_select_option(label="None (remove custom role)", value="N/A")]
        guild = CLIENT.get_guild(int(server.id))
        for i in range(len(guild.roles)):
            if i == 23:  # +1 for remove option
                break
            rol = guild.roles[i]
            try:
                ind = server.settings['msg_roles'].index([chosen_user, rol.id])
                rid = server.settings['msg_roles'][ind][1]
            except:
                ind, rid = None, None

            lbl = str(rol.name)
            if rol.id == rid:
                lbl += "*"
            options.append(manage_components.create_select_option(label=lbl, value=str(rol.id)))
        button = [manage_components.create_select(options=options, placeholder="Choose what role to mention in alerts")]
        action_row = manage_components.create_actionrow(*button)
        sent_msg = await ctx.send(embed=embed, components=[action_row])
        chosen_role = None
        try:
            button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[action_row], timeout=AFK_TIMEOUT)
            # to get the option that was chosen use button_ctx.values
            await queue_edit(sent_msg, embed=embed, components=[])
            chosen_role = button_ctx.values[0]
        except asyncio.TimeoutError:
            # TIMEOUT
            pass
        except Exception as e:
            print(traceback.format_exc())
            raise e
        asyncio.create_task(queue_delete(sent_msg))
        newset = server.settings['msg_roles']
        # [[user, role], [..., ...]]
        usrs, roles = [], []
        for i in range(len(newset)):
            usrs.append(newset[i][0])
            roles.append(newset[i][1])
        if chosen_role == "N/A":
            try:
                ind = usrs.index(chosen_user)
            except ValueError:
                await client_send(ctx, "There already wasn't a role set for {}", form=chosen_user,
                                  timeout=MISC_SLEEP_TIMEOUT)
                return 1
            tempu, tempr = [], []
            for i in range(len(usrs)):
                if i != ind:
                    tempu.append(usrs[i])
                    tempr.append(roles[i])
            newset = []
            [newset.append([tempu[i], tempr[i]]) for i in range(len(tempr))]
            server.settings['msg_roles'] = newset
            cache.update_server_attr(server.id, "settings", server.settings)
            await client_send(ctx, "Role removed", form="", timeout=MISC_SLEEP_TIMEOUT)
        elif chosen_role is not None:
            chosen_role = int(chosen_role)
            if chosen_user in usrs:
                ind = usrs.index(chosen_user)
                roles[ind] = chosen_role
            else:
                usrs.append(chosen_user)
                roles.append(chosen_role)
            newset = []
            [newset.append([usrs[i], roles[i]]) for i in range(len(roles))]
            server.settings['msg_roles'] = newset
            cache.update_server_attr(server.id, "settings", server.settings)
            await client_send(ctx, "Role set. {} To have custom roles appear in alert messages, use {} with {} as part of the alert message", form=("\n\n", "/message", "<role>"), timeout=MISC_SLEEP_TIMEOUT)

    @staticmethod
    async def channel_user_settings(ctx, server, chosen_user):
        embed = discord.Embed(title=f"User settings for {chosen_user} - custom alert channel")
        options = [manage_components.create_select_option(label="None (reset to default channel)", value="N/A")]
        for chn in ctx.guild.channels:
            # add all server's channels to possible options
            i = 0
            try:
                ind = server.settings['post_channels'].index([chosen_user, chn.id])
                cid = server.settings['post_channels'][ind][1]
            except:
                ind, cid = None, None
            if str(chn.type) == "text" and i < 25:
                i += 1
                lbl = str(chn.name)
                if cid == chn.id:
                    lbl += "*"
                options.append(manage_components.create_select_option(label=lbl, value=str(chn.id)))
        button = [manage_components.create_select(options=options, placeholder=f"Choose where to send alerts for {chosen_user}")]
        action_row = manage_components.create_actionrow(*button)
        sent_msg = await ctx.send(embed=embed, components=[action_row])
        chosen_chn = None
        try:
            button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[action_row], timeout=AFK_TIMEOUT)
            # to get the option that was chosen use button_ctx.values
            await queue_edit(sent_msg, embed=embed, components=[])
            chosen_chn = button_ctx.values[0]
            await Commands.channel_command(ctx, chosen_chn, chosen_user, server)
        except asyncio.TimeoutError:
            # TIMEOUT
            pass
        except Exception as e:
            print(traceback.format_exc())
            raise e
        await queue_delete(sent_msg)

    @staticmethod
    async def user_settings(ctx, server):
        try:
            embed = discord.Embed(title="User Settings")
            if len(server.followed) == 0:
                return await client_send(ctx, msg="First use the {} command to follow a Twitch user", form="/follow", timeout=MISC_SLEEP_TIMEOUT)
            changed_users = []
            for setting in server.settings:
                if setting == 't':
                    for u in server.settings[setting]:
                        if u not in changed_users:
                            changed_users.append(u)
                elif setting != 'd' and setting != 'r':
                    for u in server.settings[setting]:
                        if u[0] not in changed_users:
                            changed_users.append(u[0])
            options, flist = [], []
            [flist.append(f[0]) for f in server.followed]
            for c in range(len(flist)):
                ch, lb = flist[c], flist[c]
                if ch in changed_users:
                    lb += "*"
                if c < 25:
                    options.append(manage_components.create_select_option(label=lb, value=ch))
                else:
                    # more than 25 followed -> don't display past 25 (>25 in select menu raises error in discord.py)
                    break
            button = [manage_components.create_select(options=options, placeholder="Choose Twitch user to modify settings for")]
            action_row = manage_components.create_actionrow(*button)
            sent_msg = await ctx.send(embed=embed, components=[action_row])
            chosen_user = None
            try:
                button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[action_row], timeout=AFK_TIMEOUT)
                chosen_user = button_ctx.values[0]
                await queue_edit(sent_msg, embed=embed, components=[])
                # await Commands.connect_cmd(ctx, [user.id, button_ctx.values[0], user.name], server=server)
            except asyncio.TimeoutError:
                # TIMEOUT
                pass
            except:
                print(traceback.format_exc())
            await queue_delete(sent_msg)

            if chosen_user is not None:
                opstrs = ["Connect a Discord user", "Disconnect a Discord user",
                          "Choose a role to mention in alerts", "Set a custom alert channel"]
                for setting in server.settings:
                    if setting == 't':
                        for u in server.settings[setting]:
                            if u == chosen_user:
                                opstrs[0] += "*"
                    elif setting != 'd' and setting != 'r':
                        for u in server.settings[setting]:
                            if u[0] == chosen_user:
                                if setting == "msg_roles":
                                    opstrs[2] += "*"
                                elif setting == "post_channels":
                                    opstrs[3] += "*"
                embed = discord.Embed(title=f"User settings for {chosen_user}")
                options = [manage_components.create_select_option(label=opstrs[0], value="connect"),
                           manage_components.create_select_option(label=opstrs[1], value="dconnect"),
                           manage_components.create_select_option(label=opstrs[2], value="role"),
                           manage_components.create_select_option(label=opstrs[3], value="channel")]
                button = [manage_components.create_select(options=options, placeholder="What setting would you like to change?")]
                action_row = manage_components.create_actionrow(*button)
                sent_msg = await ctx.send(embed=embed, components=[action_row])
                chosen_setting = None
                try:
                    button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[action_row], timeout=AFK_TIMEOUT)
                    chosen_setting = button_ctx.values[0]
                    await queue_edit(sent_msg, embed=embed, components=[])
                    if chosen_setting == "connect":
                        await Commands.connect_user_settings(ctx, server, chosen_user)
                    elif chosen_setting == "dconnect":
                        await Commands.disconnect_user_settings(ctx, server, chosen_user)
                    elif chosen_setting == "role":
                        await Commands.role_user_settings(ctx, server, chosen_user)
                    elif chosen_setting == "channel":
                        await Commands.channel_user_settings(ctx, server, chosen_user)
                except asyncio.TimeoutError:
                    # TIMEOUT
                    pass
                except Exception as e:
                    print(traceback.format_exc())
                    raise e
                await queue_delete(sent_msg)
        except Exception as e:
            print(traceback.format_exc())
            asyncio.create_task(client_send(ctx=ctx, msg="Error {}: {}", form=(type(e).__name__, type(e).__doc__),timeout=MISC_SLEEP_TIMEOUT))

    @staticmethod
    async def role_settings(ctx, server):
        mrole = server.settings['msg_roles'][0][1]
        embed = discord.Embed(title=f"Current command role: {dis.get_role_name(server)}\n\nCurrent default msg role: {dis.get_role_name(server, mrole)}")
        preopt = [manage_components.create_select_option(label="Set required role for changing settings", value="cmd"),
                  manage_components.create_select_option(label="Set default alert role for <role>",
                                                         value="msg")]
        prebutton = [manage_components.create_select(options=preopt, placeholder="What would you like to do?")]
        preac = manage_components.create_actionrow(*prebutton)
        presnt = await ctx.send(embed=embed, components=[preac])
        try:
            pre_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[preac], timeout=AFK_TIMEOUT)
            await queue_edit(presnt, embed=embed, components=[])

            if pre_ctx.values[0] == "cmd":
                options = []
                for i in range(len(ctx.author.roles)):
                    rol = ctx.author.roles[i]
                    if i < 25:
                        lbl = str(rol.name)
                        options.append(manage_components.create_select_option(label=lbl, value=str(rol.id)))
                button = [manage_components.create_select(options=options, placeholder="Choose what role can send commands")]
                action_row = manage_components.create_actionrow(*button)
                sent_msg = await ctx.send(embed=embed, components=[action_row])
                try:
                    button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[action_row], timeout=AFK_TIMEOUT)
                    # to get the option that was chosen use button_ctx.values
                    await queue_edit(sent_msg, embed=embed, components=[])
                    await Commands.role_cmd(ctx, button_ctx.values[0], server=server)
                except asyncio.TimeoutError:
                    # TIMEOUT
                    pass
                except:
                    print(traceback.format_exc())
                await queue_delete(sent_msg)
            else:
                options = [manage_components.create_select_option(label="@here", value="here")]
                allroles = CLIENT.get_guild(int(server.id)).roles
                for i in range(len(allroles)):
                    rol = allroles[i]
                    if rol.name == "@everyone":
                        ID = "everyone"
                    else:
                        ID = str(rol.id)
                    if i < 24:
                        options.append(manage_components.create_select_option(label=str(rol.name), value=ID))
                button = [manage_components.create_select(options=options, placeholder="Choose who to mention for <role> in alerts")]
                action_row = manage_components.create_actionrow(*button)
                sent_msg = await ctx.send(embed=embed, components=[action_row])
                try:
                    button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[
                        action_row], timeout=AFK_TIMEOUT)
                    # to get the option that was chosen use button_ctx.values
                    await queue_edit(sent_msg, embed=embed, components=[])
                    await Commands.role_cmd(ctx, button_ctx.values[0], server=server, change="msg")
                except asyncio.TimeoutError:
                    # TIMEOUT
                    pass
                except:
                    print(traceback.format_exc())
                await queue_delete(sent_msg)
        except asyncio.TimeoutError:
            # TIMEOUT
            pass
        except:
            print(traceback.format_exc())
        await queue_delete(presnt)


WELCOME_MSG = "Welcome to your new Twitch alert bot!"\
        "\n\nTo get started, tell me where to send alerts with\n**/channel**\n\nThen choose which "\
        "Twitch channel(s) I'll send alerts for with\n**/follow**\nYou can add multiple users at once by splitting their"\
        " names with a comma (without spaces).\n\nIf you want to only allow a certain role to send commands to me, use"\
        "\n**/role**\n\nFor more help, use **/help**\n\nGood luck, have fun, and happy streaming!"


async def run_setup(ctx):
    await manual_join(ctx.guild)
    asyncio.create_task(client_send(ctx=ctx, msg=WELCOME_MSG, embed=False))


@SLASH.slash(name="setup", description="Run the initial setup", guild_ids=guild_ids)
async def setup(ctx):
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
        await client_send(ctx=ctx, msg=WELCOME_MSG, form="", timeout=MISC_SLEEP_TIMEOUT, embed=False)
    except NoServerFound:
        await run_setup(ctx)
        return 1


@SLASH.slash(name="upgrade",
             description="Subscribe to have your bot hosted for you",
             guild_ids=guild_ids)
async def upgrade(ctx):
    await ctx.defer()
    await client_send(ctx=ctx,
                      msg="Support us to access hosting for your bot on the premium tier!\n\nTo get started, visit\nhttps://patreon.com/discotwitch",
                      form="",
                      embed=False,
                      timeout=MISC_SLEEP_TIMEOUT)


@SLASH.slash(name="connect", description="Designate a Discord user to a Twitch channel (optional)", guild_ids=guild_ids)
async def connect(ctx, discord_userid, twitch_username):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    await Commands.connect_user_settings(ctx, server, twitch_username, discord_userid)


@SLASH.slash(name="language", description="Change default language", guild_ids=guild_ids)
async def language(ctx, language=""):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    await Commands.lang_cmd(ctx, language, server)


@SLASH.slash(name="reset", description="Resets all cached data", guild_ids=guild_ids)
async def reset(ctx):
    await ctx.defer()
    server = cache.binary_search_object_by_id(ctx.guild.id)
    reset_button = [manage_components.create_button(style=ButtonStyle.green, label="YES", custom_id="y"), manage_components.create_button(style=ButtonStyle.red, label="NO", custom_id="n")]
    reset_ar = manage_components.create_actionrow(*reset_button)
    embed = discord.Embed(title="RESET?", description="If DiscoTwitch isn't working properly in your server, resetting might help."
                                              "\nAll settings will be remembered, only cached data will be lost.")
    msg_sent = await ctx.send(embed=embed, components=[reset_ar])
    try:
        button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[reset_ar], timeout=MISC_SLEEP_TIMEOUT)
        await msg_sent.edit(components=[])
        print(button_ctx.data)
        if button_ctx.data['custom_id'] == "y":
            await Commands.reset_cmd(ctx=ctx, server=server)
            asyncio.create_task(client_send(ctx=ctx, msg="Cached data has been reset!", form="", timeout=MISC_SLEEP_TIMEOUT))
        else:
            asyncio.create_task(client_send(ctx=ctx, msg="Reset cancelled", form="", timeout=MISC_SLEEP_TIMEOUT))
        await queue_delete(msg_sent)
    except cfb.TimeoutError:
        # TIMEOUT
        await queue_delete(msg_sent)

    except:
        print(traceback.format_exc())


@SLASH.slash(name="mute", description="Mute/unmute alerts.", guild_ids=guild_ids)
async def mute(ctx):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    if 0 not in server.muted:
        server.muted.append(0)
        await Commands.settings_cmd(ctx, server=server, mute=True)
    else:
        server.muted.remove(0)
        await Commands.settings_cmd(ctx, server=server, mute=False)


@SLASH.slash(name="help")
async def help(ctx):
    await ctx.defer()
    await Commands.help_command(ctx)


@SLASH.slash(name="role", description="Choose what role can change bot settings.", guild_ids=guild_ids)
async def role(ctx):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    embed = discord.Embed(title=f"Current command role: {dis.get_role_name(server)}")
    options = []
    for i in range(len(ctx.author.roles)):
        rol = ctx.author.roles[i]
        if i < 25:
            lbl = str(rol.name)
            options.append(manage_components.create_select_option(label=lbl, value=str(rol.id)))
    button = [manage_components.create_select(options=options, placeholder="Choose what role can send commands")]
    action_row = manage_components.create_actionrow(*button)
    sent_msg = await ctx.send(embed=embed, components=[action_row])
    try:
        button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[action_row], timeout=AFK_TIMEOUT)
        # to get the option that was chosen use button_ctx.values
        await queue_edit(sent_msg, embed=embed, components=[])
        await Commands.role_cmd(ctx, button_ctx.values[0], server=server)
    except asyncio.TimeoutError:
        # TIMEOUT
        pass
    except:
        print(traceback.format_exc())
    await queue_delete(sent_msg)


@SLASH.slash(name="channel", description="Choose where to send alerts.", guild_ids=guild_ids)
async def channel(ctx, id=None, twitch_channel=None):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    if id is not None and twitch_channel is not None:
        await Commands.channel_command(ctx, id, twitch_channel, server=server)
    elif id is not None:
        await Commands.channel_command(ctx, id, server=server)
    else:
        # id not provided
        chn = "None"
        try:
            chn = CLIENT.get_channel(int(take_off_brackets(server.settings['post_channels'][0][1])))
            chn = "#" + str(chn.name)
        except:
            try:
                server.settings['post_channels'][0][1] = 0
                cache.update_server_attr(server.id, "settings", server.settings)
            except:
                print(traceback.format_exc())
        try:
            embed = discord.Embed(title="Current Channel:\n\n" + chn)
        except:
            embed = discord.Embed(title="Current Channel:\n\nNone")
        options = []
        i = 0
        for channel in ctx.guild.channels:
            # add all server's channels to possible options
            if str(channel.type) == "text" and i < 25:
                i += 1
                options.append(manage_components.create_select_option(label=str(channel.name), value=str(channel.id)))
        button = [manage_components.create_select(options=options, placeholder="Choose where to send alerts")]
        action_row = manage_components.create_actionrow(*button)
        sent_msg = await ctx.send(embed=embed, components=[action_row])
        if twitch_channel is not None:
            await ctx.send("Cannot set the alert channel for a specific Twitch channel if an ID has not been given\n"
                           "Use /channel id={channel id} twitch_user={username}\n"
                           "Or go to /settings -> Twitch User Settings -> <user> -> Set custom alert channel")
        try:
            button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[action_row], timeout=AFK_TIMEOUT)
            await queue_edit(sent_msg, embed=embed, components=[])
            # to get the option that was chosen use button_ctx.values
            await Commands.channel_command(ctx, button_ctx.values[0], server=server)
        except asyncio.TimeoutError:
            # TIMEOUT
            pass
        await queue_delete(sent_msg)


@SLASH.slash(name="settings", description="Modify settings", guild_ids=guild_ids)
async def settings(ctx):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    if not dis.has_role(server.id, ctx.author.id, server.role):
        asyncio.create_task(client_send(ctx=ctx, msg="You don't have the required server role to use this command {}.",
                                        form="(@" + dis.get_role_name(server, server.role) + ")",
                                        timeout=MISC_SLEEP_TIMEOUT))
        return 1
    options = [manage_components.create_select_option(label="Notification Settings", value="n"),
               manage_components.create_select_option(label="Role Settings", value="r"),
               manage_components.create_select_option(label="Twitch User Settings", value="u")]
    button = [manage_components.create_select(options=options, placeholder="What settings do you want to modify?")]
    action_row = manage_components.create_actionrow(*button)
    sent_msg = await ctx.send(components=[action_row])
    try:
        button_ctx: ComponentContext = await manage_components.wait_for_component(CLIENT, components=[action_row], timeout=AFK_TIMEOUT)
        # to get the option that was chosen use button_ctx.values
        if button_ctx.values[0] == "n":
            await queue_edit(sent_msg, embed=discord.Embed(title="Now modifying notification settings"), components=[])
            await Commands.notif_settings(ctx, server)
        elif button_ctx.values[0] == "u":
            await queue_edit(sent_msg, embed=discord.Embed(title="Now modifying user settings"), components=[])
            await Commands.user_settings(ctx, server)
        else:
            await queue_edit(sent_msg, embed=discord.Embed(title="Now modifying role settings"), components=[])
            await Commands.role_settings(ctx, server)
    except asyncio.TimeoutError:
        # TIMEOUT
        pass
    except:
        print(traceback.format_exc())
    await queue_delete(sent_msg)


@SLASH.slash(name="test", description="Sends a test live alert message.", guild_ids=guild_ids)
async def test(ctx, user="<user>", title="<title>", game="<game>"):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    await Commands.test_cmd(ctx, user, title, game, server)


@SLASH.slash(name="message", description="Change the live alert message. Type \"info\" for usage or \"reset\" to set msg to default.", guild_ids=guild_ids)
async def message(ctx, alert_message=""):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    await Commands.msg_cmd(ctx, alert_message, server)


@SLASH.slash(name="follow", description="Choose what Twitch users to get live alerts for (separate with commas, without spaces).", guild_ids=guild_ids)
async def follow(ctx, users=""):
    await ctx.defer()  # allows 15-min before failed interaction, as opposed to 3-sec default
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    await Commands.follow_cmd(ctx, users, server)


@SLASH.slash(name="unfollow", description="Choose Twitch users to stop getting alerts for, or type 'all'.", guild_ids=guild_ids)
async def unfollow(ctx, users=""):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    await Commands.unfollow_cmd(ctx, users, server)


@SLASH.slash(name="status", description="Check if a Twitch user is live or not.", guild_ids=guild_ids)
async def status(ctx, user=""):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    await Commands.status_cmd(ctx, user, server)


@SLASH.slash(name="nickname", description="Change the bot's username in your server.", guild_ids=guild_ids)
async def nickname(ctx, name):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    await Commands.nick_cmd(ctx, name, server)


@SLASH.slash(name="clips", description="View all-time top clip of a Twitch channel", guild_ids=guild_ids)
async def clips(ctx, user):
    await ctx.defer()
    try:
        server = cache.binary_search_object_by_id(ctx.guild.id)
    except NoServerFound:
        await run_setup(ctx)
        return 1
    await Commands.top_clip_cmd(ctx, user)


@SLASH.slash(name="log", description="Twitch chatlogs for a user in a channel", guild_ids=guild_ids)
async def log(ctx, user, channel, month=None, year=None):
    await ctx.defer()
    try:
        await Commands.logs_cmd(ctx, twitch_user=user, twitch_channel=channel, year=year, month=month)
    except:
        pass


@CLIENT.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        await client_send(ctx, "Standard commands have been replaced with slash commands! If you're not seeing the slash commands in your server, make sure to update my permissions by clicking my profile and \"Add to Server\".\n\nNote that it may take up to an hour for them to appear after doing so.", timeout=AFK_TIMEOUT)



ready = False
@CLIENT.event
async def on_ready():
    print("start on_ready")
    global ready, guild_ids
    if not ready:
        print(len(CLIENT.guilds))
        handle_leaves.start()
        timeout_delete.start()
        [guild_ids.append(g.id) for g in CLIENT.guilds]
        ready = True
        handle_joins.start()
        print(datetime.datetime.now())
        print("logged in as")
        print("username: " + str(CLIENT.user.name))
        print("client id: " + str(DISCORD_TOKEN))
        print("----------")


async def manual_join(g):
    cache.append_server(g.name, g.id)
    global guild_ids
    if g.id not in guild_ids:
        guild_ids.append(g.id)
    print("joined", g.name, "-", g.id)


# TASKS
activity_set = -1


@tasks.loop(seconds=5)
async def handle_joins():
    cache.remove_duplicates()


@tasks.loop(seconds=60)
async def handle_leaves():
    global activity_set
    for s in cache.server_objects:
        if CLIENT.get_guild(int(s.id)) is None:
            try:
                cache.remove_server(s.id)
                global guild_ids
                guild_ids.remove(int(s.id))
                print("left", s.name)
            except:
                print(traceback.format_exc())
    if activity_set == -1:
        activity_set = 0
    if activity_set == 0:
        await CLIENT.change_presence(activity=discord.Streaming(name="DiscoTwitch v2.1.2", url="https://twitch.tv/hesmen"))
        activity_set = 1
    else:
        # switch between the two
        activity_set = 0
        await CLIENT.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Twitch"))


@tasks.loop(seconds=MISC_SLEEP_TIMEOUT)
async def timeout_delete():
    global delete_queue
    for m in delete_queue:
        try:
            await m[0].delete()
        except:
            pass
        delete_queue.remove(m)


if __name__ == "__main__":
    twitch = Twitch()
    cache = Cache()
    dis = Discord(CLIENT)
    CLIENT.run(DISCORD_TOKEN)
