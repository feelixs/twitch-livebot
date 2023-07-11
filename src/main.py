import cache as CACHE
import datetime
import time
import ast
import tqdm
import asyncio
import discord
import importlib
import requests
import traceback
from discord.errors import Forbidden
from discord.ext import tasks, commands
from discord.ext.commands.errors import CommandNotFound
from discord.errors import NotFound
from googletrans import Translator

SHARD_ID = 0
TOTAL_SHARDS = 1

translator = Translator()

DISCORD_TOKEN = CACHE.DISCORD_TOKEN
TWITCH_ID = CACHE.TWITCH_ID
TWITCH_SECRET = CACHE.TWITCH_SECRET

intent = discord.Intents.default()
intent.members = True
CLIENT = commands.AutoShardedBot(command_prefix=CACHE.prefix, intents=intent, shard_ids=[SHARD_ID], shard_count=TOTAL_SHARDS)


@CLIENT.event
async def on_message(msg):
    # tell it to do nothing on message. If there's no on_message function it defaults to trying to handle commands
    # but only commands.py should do that
    pass


async def client_send(ctx, msg, embed=1):
    """Sends messages to Discord context. Easily makes messages 'embeded' if embed == 1"""
    try:
        msg = str(msg)
        if embed == 1:
            m = await ctx.send("```" + msg + "```")
        else:
            m = await ctx.send(msg)

        return m
    except:
        return None


def str_to_list(st):
    """Turns a list that's stored as a str back into a list"""
    # made this because I apparently didn't know list(str) was a thing
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


def translate(st, lang):
    try:
        if lang != 'en':
            return translator.translate(st, dest=lang).text
        else:
            return st
    except:
        print(traceback.format_exc())
        return st


def take_off_brackets(arg, noand=0):
    """Takes off special characters from discord ids, used to turn discord channel/role ids into ints"""
    msg = str(arg)
    word = ""
    for i in range(len(msg)):
        if msg[i] != "<" and msg[i] != "#" and msg[i] != "@" and msg[i] != ">":
            if noand != 1 and msg[i] != "&":
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
        word += ", " + str(li[-1])
    else:
        word = str(li[0])
    return word


def parse_live_msg(user, msg, title, game, viewers, server_connections=None, mention_users=False, server=None):
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
            mrole = dis.get_mention_role(server, user)
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
            [u.append(0) for u in self.followed]
            # for this script there's an extra slot in followed that keeps track of whether a role
            # has been added for the user being live (if their connected to a discord user)

    def __init__(self):
        self.data = CACHE.data
        self.server_objects = []
        self.reload_objects(self.data)

    def reload_objects(self, newdata):
        """Sets self.data to newdata, reloads server objects with newdata, and writes updated data to file"""
        newdata = ast.literal_eval(str(newdata))
        self.data = newdata
        self.server_objects = []
        [self.server_objects.append(self.Server(newdata, i)) for i in range(len(newdata['servers']))]
        # recreate server object list to match changed cache file -
        # iterate through cache file, each server in it is sent to self.Server constructor that
        # creates a new object with that server's attributes. The object is added to self.server_objects

    @staticmethod
    def get_obdated_obj_followed(serverid):
        importlib.reload(CACHE)
        newdata = CACHE.data
        for i in range(len(newdata['servers'])):
            if newdata['servers'][i]['id'] == serverid:
                return newdata['servers'][i]['followed']

    @staticmethod
    def get_obdated_obj_settings(serverid):
        importlib.reload(CACHE)
        newdata = CACHE.data
        for i in range(len(newdata['servers'])):
            if newdata['servers'][i]['id'] == serverid:
                return ast.literal_eval(newdata['servers'][i]['settings']), newdata['servers'][i]['muted'], \
                       newdata['servers'][i]['live_message'], newdata['servers'][i]['lang']

    def reload_objects_nolive(self):
        """Re-import data file, reload server objects with updated file data EXCEPT for already_live, titles, and msg id info"""
        importlib.reload(CACHE)
        newdata = CACHE.data
        for i in range(len(newdata['servers'])):
            for j in range(len(self.server_objects)):
                if newdata['servers'][i]['id'] == self.server_objects[j].id:
                    newdata['servers'][i]['followed'] = self.server_objects[j].followed
        self.data = newdata
        self.server_objects = []
        [self.server_objects.append(self.Server(newdata, i)) for i in range(len(newdata['servers']))]

    def binary_search_object_by_id(self, server_id, calltype=1) -> Server:
        """Binary search through object list of servers, and return the index or object for the server depending on the calltype"""
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
            raise Exception("No matching server")

    def seq_search_object(self, server_id, calltype=1):
        """Sequential search through object list of servers, and return the index or object for the server depending on the calltype"""
        for i in range(len(self.server_objects)):
            if int(server_id) == int(self.server_objects[i].id):
                if calltype == 1:
                    return self.server_objects[i]
                else:
                    return i
        raise Exception("No matching server")

    def strtup_refresh_follows(self):
        """When the script starts, update twitch live statuses & stream titles without sending discord msgs"""
        for i in tqdm.tqdm(range(len(self.server_objects))):
            # print(self.server_objects[i].already_live, ">")
            followed_usernames, ids = [], []
            for f in self.server_objects[i].followed:
                followed_usernames.append(f[0])
                ids.append(f[2])
            already_live = twitch.check_live(followed_usernames)
            titles = twitch.get_titles(followed_usernames)
            games = twitch.get_game_ids(followed_usernames)
            for j in range(len(self.server_objects[i].followed)):
                self.server_objects[i].followed[j] = [followed_usernames[j], already_live[j], ids[j], titles[j], 0, games[j]]

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
        try:
            return a.json()["data"][0]["name"]
        except:
            return "N/A"

    def check_live(self, ulist):
        """Given a list of Twitch usernames, return a boolean list of live statuses"""
        out = []
        [out.append(str(self.find_user(ulist[i]).is_live)) for i in range(len(ulist))]
        return out

    def get_titles(self, ulist):
        """Given a list of Twitch usernames, return a list of their stream titles"""
        out = []
        [out.append(str(self.find_user(ulist[i]).title)) for i in range(len(ulist))]
        return out

    def get_game_ids(self, ulist):
        """Given a list of Twitch usernames, return list of games they're playing"""
        out = []
        [out.append(str(self.find_user(ulist[i]).game_id)) for i in range(len(ulist))]
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

    def get_most_recent_vid(self, user_query):
        """Given a Twitch username, return their most recent VOD"""
        h = {'Client-ID': self.CLIENT_ID, 'client_secret': self.CLIENT_SECRET,
             'Authorization': "Bearer " + str(self.oauth)}
        a = requests.get(url='https://api.twitch.tv/helix/search/channels?query=' + str(user_query), headers=h)
        try:
            for u in a.json()['data']:
                if str(u['display_name']).lower() == str(user_query).lower():
                    res = requests.get('https://api.twitch.tv/helix/videos?user_id=' + u['id'] + "&sort=time",
                                       headers=h).json()
                    # print(res)
                    return res['data'][0]['url']
        except IndexError:
            raise Exception("novids")
        except Exception as e:
            raise e

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
        try:
            if data is not None:
                for usr in data:
                    if str(usr['display_name']).replace(" ", "").lower() == str(query).lower():
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
                self.is_live = 'False'
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


class Discord:
    def __init__(self, dis_client):
        self.activity = ""
        self.timer = 0
        self.client = dis_client

    @staticmethod
    def get_mention_role(server, twitch_user):
        if server is None:
            return ""
        server_connections = server.settings
        try:
            cr_users, cr_roles = [], []
            for i in range(len(server_connections['msg_roles'])):
                cr_users.append(server_connections['msg_roles'][i][0])
                cr_roles.append(server_connections['msg_roles'][i][1])
            if twitch_user in cr_users:
                ind = cr_users.index(twitch_user)
                return "<@&" + str(cr_roles[ind]) + ">"

            default = str(server_connections['msg_roles'][0][1])
            if default == "everyone":
                return "@everyone"
            elif default == "here":
                return "@here"
            else:
                return "<@&" + default + ">"
        except:
            pass
        return ""

    async def set_watching_activity(self, activity):
        """Changes discord 'watching' status"""
        await self.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=activity))
        self.activity = activity

    def has_role(self, serverid, userid, roleid):
        user = self.get_member(serverid, userid)
        for r in user.roles:
            if r.id == roleid:
                return True
        return False

    @staticmethod
    def get_member(serverid, userid):
        for m in CLIENT.get_guild(int(serverid)).members:
            if int(m.id) == int(userid):
                return m
        return None

    async def give_role(self, serverid, userid, roleid):
        guild = self.client.get_guild(int(serverid))
        user = self.get_member(serverid, userid)
        role = guild.get_role(roleid)
        await user.add_roles(role)

    async def remove_role(self, serverid, userid, roleid):
        guild = self.client.get_guild(int(serverid))
        user = self.get_member(serverid, userid)
        role = guild.get_role(roleid)
        await user.remove_roles(role)

    @staticmethod
    def get_msg_secs_active(msg):
        """Returns the amount of time a discord message has been active"""
        mesg_time_obj = datetime.datetime.strptime(str(msg.created_at),
                                                   "%Y-%m-%d %H:%M:%S.%f")  # convert created_at string to datetime format
        mesg_ms = time.mktime(
            mesg_time_obj.timetuple())  # - mesg_time_obj.microsecond / 1E6  # convert datetime format to time.time format
        utctimenow = time.mktime((datetime.datetime.utcnow()).timetuple())
        seconds_active = int(utctimenow - mesg_ms)
        return seconds_active


started = 0


@CLIENT.event
async def on_ready():
    global started
    if started == 0:
        started = 1
        print("start on_ready")
        cache.strtup_refresh_follows()
        main.start()
        print(datetime.datetime.now())
        print("logged in as")
        print("username: " + str(CLIENT.user.name))
        print("client id: " + str(DISCORD_TOKEN))
        print("total shards: " + str(CLIENT.shard_count))
        print("Running as shard: " + str(SHARD_ID))
        print("shard guilds: " + str(len(CLIENT.guilds)))
        print("----------")
    else:
        print("ALREADY STARTED")


# PROCESSES

delete_queue = []
oldt = 0


async def server_background(s):
    """Code where live messages, offline msgs, etc are sent. main() runs this in background for each server"""
    ulist, stats, live_msg_ids, titles, prev_times, games = [], [], [], [], [], []
    global delete_queue, oldt
    try:
        for f in s.followed:
            ulist.append(f[0])
            live_msg_ids.append(f[2])
            titles.append(f[3])
            prev_times.append(f[4])
            games.append(f[5])
        try:
            stats = twitch.check_live(ulist)
        except:
            stats = []
        for i in range(len(stats)):  # for followed user online status
            time_since_last_msg = None
            try:
                time_since_last_msg = round(time.time() - s.followed[i][4])
                # print(time_since_last_msg, "since last msg for", s.followed[i])
                live_msg_timeout = time_since_last_msg < 300  # checks if it's sent a live alert within the last (10) minutes for this user
                # print(live_msg_timeout)
            except:
                live_msg_timeout = False
            if live_msg_timeout:
                # print(f"within timeout for {s.followed[i]}, {300-time_since_last_msg} secs left")
                continue

            live_user = ulist[i]
            old_stat = s.followed[i][1]
            if stats[i] == "True" and old_stat == "False":  # if new status = True and old status = False
                send_bool = True
                t_user = twitch.find_user(live_user)
                dta = twitch.get_streams(live_user)
                original_starttime = datetime.datetime.fromisoformat(t_user.started_at[:-1]).timestamp()
                curr_time = datetime.datetime.utcnow().timestamp()
                print(curr_time - original_starttime)
                if curr_time - original_starttime > 1800:
                    # theres a bug where sometimes live msgs will be repeated
                    # if 30 mins have passed since the user was recorded going live by twitch, assume we've already sent a msg
                    send_bool = False
                try:
                    viewers = str(dta['viewer_count'])
                except:
                    viewers = "0"
                sent_msg = None
                game = twitch.get_game_name(str(t_user.game_id))
                title = str(t_user.title)
                if "7" in str(s.muted):
                    message = str(parse_live_msg(str(live_user), str(s.live_message), title, game, viewers, s.settings, mention_users=True, server=s))
                else:
                    message = str(parse_live_msg(str(live_user), str(s.live_message), title, game, viewers, s.settings, mention_users=False, server=s))
                try:
                    titles[i] = title
                except IndexError:
                    titles.append(title)
                if "1" in str(s.muted) and "0" not in str(s.muted):  # on-live alerts
                    try:
                        # find the channel for the chosen user
                        ind = None
                        for c in range(len(s.settings['post_channels'])):
                            curnt = s.settings['post_channels'][c]
                            if curnt[0] == live_user:
                                ind = c
                        if ind is not None:
                            post_ch = int(take_off_brackets(str(s.settings['post_channels'][ind][1])))
                        else:
                            post_ch = int(take_off_brackets(str(s.settings['post_channels'][0][1])))
                        if send_bool:
                            try:
                                sent_msg = await client_send(CLIENT.get_channel(post_ch), message, 0)
                            except:
                                print("send msg:", traceback.format_exc())
                            print(datetime.datetime.now(), s.name, s.id, ":\n", message, "\nsent_msg:", sent_msg)
                        try:
                            prev_times[i] = round(time.time())
                        except:
                            print(traceback.format_exc())
                    except Exception as e:
                        if str(s.settings['post_channels'][0][1]) == "":
                            print("\n", s.name, s.id, "- couldn't send live message (no channel set)")
                        else:
                            print("\n", s.name, s.id, "- couldn't send live message\n", type(e).__name__)
                            print(traceback.format_exc())
                    if sent_msg is not None:  # client_send returns None on errors
                        tempids, temptimes = [], []
                        for n in range(len(stats)):
                            if n == i:  # if n equals the i (index of twitch users list), it's the live msg the bot sent for them
                                tempids.append(sent_msg.id)
                                temptimes.append(round(time.time()))
                            else:
                                tempids.append(live_msg_ids[n])
                                try:
                                    temptimes.append(prev_times[n])
                                except:
                                    temptimes.append(0)
                        live_msg_ids = tempids
            if str(stats[i]) == "False" and str(old_stat) == "True":  # if new status = False and old status = True
                print(datetime.datetime.now(), s.name, "-", live_user, translate("has gone", s.lang) + " offline")

            if str(stats[i]) == "False" and live_msg_ids[i] != 0:  # edit alert message if user is offline
                if "4" in str(s.muted) or "6" in str(s.muted):  # edit "OFFLINE" into alerts
                    try:
                        ind = None
                        for c in range(len(s.settings['post_channels'])):
                            curnt = s.settings['post_channels'][c]
                            if curnt[0] == live_user:
                                ind = c
                        if ind is not None:
                            post_ch = int(take_off_brackets(str(s.settings['post_channels'][ind][1])))
                        else:
                            post_ch = int(take_off_brackets(str(s.settings['post_channels'][0][1])))
                        ms = await CLIENT.get_channel(post_ch).fetch_message(live_msg_ids[i])
                        if "\n*(OFFLINE)*" not in str(ms.content) and "4" in str(s.muted):
                            await ms.edit(content=str(ms.content) + "\n*(OFFLINE)*")
                        if "\n**VOD - **" not in str(ms.content) and "6" in str(s.muted):
                            vod = twitch.get_most_recent_vid(s.followed[i])
                            await ms.edit(content=str(ms.content) + "\n**VOD - **" + str(vod))
                    except TimeoutError:
                        print(traceback.format_exc())
                        print("restarting on server", s.name)
                        asyncio.create_task(server_background(s))
                        return -1
                    except AttributeError:
                        print(s.name, "AttrError on message edit")
                    except Exception as e:
                        print(s.name, traceback.format_exc())
                        try:
                            print("ms:", ms)
                        except:
                            pass
                if "8" in str(s.muted):
                    try:
                        ms = await CLIENT.get_channel(
                            int(take_off_brackets(str(s.settings['post_channels'][0][1])))).fetch_message(
                            live_msg_ids[i])
                        print(ms)
                        try:
                            print(ms.__dict__)
                        except:
                            pass
                        delete_queue.append([ms, time.time()])
                    except TimeoutError:
                        print(traceback.format_exc())
                        print("restarting on server", s.name)
                        asyncio.create_task(server_background(s))
                        return -1
                    except AttributeError:
                        print(s.name, "AttrError on message edit")
                    except Exception as e:
                        print(s.name, traceback.format_exc())
                temp = []
                for n in range(len(live_msg_ids)):
                    if n == i:
                        temp.append(0)
                    else:
                        temp.append(live_msg_ids[n])
                live_msg_ids = temp

        try:
            d_usrs, t_usrs, rls = s.settings['d'], s.settings['t'], s.settings['r']
            livedata = twitch.check_live(t_usrs)
            for i in range(len(livedata)):
                if t_usrs[i] in ulist:
                    findex = ulist.index(t_usrs[i])
                    if livedata[i] == "True":
                        if s.followed[findex][6] == 0:
                            try:
                                await dis.give_role(s.id, d_usrs[i], rls[0])
                            except:
                                pass
                            s.followed[findex][6] = 1  # this keeps track of if the role was added already
                    else:
                        if s.followed[findex][6] == 1:
                            try:
                                await dis.remove_role(s.id, d_usrs[i], rls[0])
                            except:
                                pass
                            s.followed[findex][6] = 0
        except:
            print(s.id, s.name, "d_t connections:", traceback.format_exc())

        titles, games = [], []
        for i in range(len(s.followed)):
            user = twitch.find_user(s.followed[i][0])
            try:
                stitle = s.followed[i][3]
                titles.append(user.title)
                if stitle != "":
                    if user.title != stitle and s.followed[i][1] == "True" and str(user.title) != "None":  # title change alerts
                        post_ch = int(take_off_brackets(str(s.settings['post_channels'][0][1])))
                        try:
                            if "2" in str(s.muted):
                                print("old title:" + stitle, "\nnew title:", user.title)
                                tm = await client_send(CLIENT.get_channel(post_ch), str(s.followed[i][0]) + " " + translate("has changed their title to", s.lang) + " **" + str(user.title) + "**", 0)
                                delete_queue.append([tm, time.time()])
                        except:
                            pass
                        if "3" in str(s.muted):
                            # make it so it edits title in original alert
                            try:
                                ms = await CLIENT.get_channel(int(take_off_brackets(str(s.settings['post_channels'][0][1])))).fetch_message(s.followed[i][2])
                            except:
                                pass
                            live_user = s.followed[i][0]
                            title = user.title
                            game = twitch.get_game_name(user.game_id)
                            dta = twitch.get_streams(live_user)
                            try:
                                viewers = str(dta['viewer_count'])
                            except:
                                viewers = "0"
                            if "7" in str(s.muted):
                                message = str(parse_live_msg(str(live_user), str(s.live_message), title, game, viewers, s.settings, mention_users=True, server=s))
                            else:
                                message = str(parse_live_msg(str(live_user), str(s.live_message), title, game, viewers, s.settings, mention_users=False, server=s))
                            try:
                                await ms.edit(content=message)
                            except:
                                pass
            except:
                print(s.id, s.name, "titles:", traceback.format_exc())

            try:
                sgame = s.followed[i][5]
                games.append(user.game_id)
                curr_game_name = twitch.get_game_name(user.game_id)
                if curr_game_name != "N/A":
                    if user.game_id != sgame and s.followed[i][1] == "True":
                        post_ch = int(take_off_brackets(str(s.settings['post_channels'][0][1])))
                        if "9" in str(s.muted):
                            old_game = twitch.get_game_name(sgame)
                            print("old game:" + old_game, "\nnew game:" + curr_game_name)
                            try:
                                tg = await client_send(CLIENT.get_channel(post_ch), str(s.followed[i][0]) + " " + translate("is now playing", s.lang) + " **" + curr_game_name + "**", 0)
                                delete_queue.append([tg, time.time()])
                            except:
                                pass
                        try:
                            if "3" in str(s.muted):
                                # make it so it edits title in original alert
                                ms = await CLIENT.get_channel(int(take_off_brackets(str(s.settings['post_channels'][0][1])))).fetch_message(s.followed[i][2])
                                live_user = s.followed[i][0]
                                title = user.title
                                game = twitch.get_game_name(user.game_id)
                                dta = twitch.get_streams(live_user)
                                try:
                                    viewers = str(dta['viewer_count'])
                                except:
                                    viewers = "0"
                                if "7" in str(s.muted):
                                    message = str(parse_live_msg(str(live_user), str(s.live_message), title, game, viewers, s.settings, mention_users=True, server=s))
                                else:
                                    message = str(parse_live_msg(str(live_user), str(s.live_message), title, game, viewers, s.settings, mention_users=False, server=s))
                                await ms.edit(content=message)
                        except:
                            pass
            except:
                print(s.id, s.name, "games:", traceback.format_exc())

        tempfollowed, ulist, rolesets = [], [], []
        for f in s.followed:
            ulist.append(f[0])
            rolesets.append(f[6])
        [tempfollowed.append([ulist[j], stats[j], live_msg_ids[j], titles[j], prev_times[j], games[j], rolesets[j]]) for j in range(len(ulist))]
        # at this point s.followed also contains users we may have unfollowed, and not users we followed in commands.py
        s.followed = cache.get_obdated_obj_followed(s.id)
        # now it's synced with commands.py

        # now remove all people not in updated followed
        newfollows = []
        [newfollows.append(f[0]) for f in s.followed]
        for u in tempfollowed:
            if u[0] not in newfollows:
                tempfollowed.remove(u)
        # and add any new ones
        for f in newfollows:
            if f not in ulist:
                tempfollowed.append([f, "", 0, "", 0, 0])

        s.followed = tempfollowed
        # locally updates this script with the live statuses that we checked in this background

        # also manually update settings
        # (would have been updated anyway in main() from reload_objects_nolive() but this will just update faster)
        s.settings, s.muted, s.live_message, s.lang = cache.get_obdated_obj_settings(s.id)
    except:
        print(traceback.format_exc(), s.name)


# TASKS


@tasks.loop(seconds=1)
async def main():
    cache.reload_objects_nolive()
    try:
        user = twitch.find_user('hesmen')
        if user is None:
            print("resetting twitch oauth")
            twitch.set_oauth()
        procs = []
        for s in cache.server_objects:
            gg = CLIENT.get_guild(int(s.id))
            if gg is not None:
                s = cache.binary_search_object_by_id(gg.id)
                procs.append(asyncio.create_task(server_background(s)))

        for p in procs:
            try:
                await p
            except:
                print(traceback.format_exc())

        global delete_queue
        for m in delete_queue:
            if time.time() - m[1] > 300:
                delete_queue.remove(m)
                try:
                    print("deleting", m[0].content)
                    await m[0].delete()
                except:
                    pass
    except:
        print(traceback.format_exc())


if __name__ == "__main__":
    twitch = Twitch()
    cache = Cache()
    dis = Discord(CLIENT)
    print(len(cache.server_objects))
    CLIENT.run(DISCORD_TOKEN)
