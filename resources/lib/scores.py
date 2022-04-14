import copy
import os
import pytz
import requests
import time
from datetime import datetime

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


class Scores:

    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self.local_string = self.addon.getLocalizedString
        self.ua_ipad = 'Mozilla/5.0 (iPad; CPU OS 8_4 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Mobile/12H143 ipad nhl 5.0925'
        self.nhl_logo = os.path.join(self.addon_path,'resources','nhl_logo.png')
        self.api_url = 'http://statsapi.web.nhl.com/api/v1/schedule?date=%s&expand=schedule.teams,schedule.linescore,schedule.scoringplays'
        self.headshot_url = 'http://nhl.bamcontent.com/images/headshots/current/60x60/%s@2x.png'
        self.score_color = 'FF00B7EB'
        self.gametime_color = 'FFFFFF66'
        self.new_game_stats = []
        self.wait = 30
        self.display_seconds = 5
        self.display_milliseconds = 5000
        self.dialog = xbmcgui.Dialog()
        self.monitor = xbmc.Monitor()

    def toggle_script(self):
        # Toggle the setting
        if not self.scoring_updates_on():
            self.addon.setSetting(id='score_updates', value='true')
            self.dialog.notification(self.local_string(30300), self.local_string(30350), self.nhl_logo, self.display_milliseconds, False)
            self.check_games_scheduled()
            self.scoring_updates()
            self.addon.setSetting(id='score_updates', value='false')
        else:
            self.addon.setSetting(id='score_updates', value='false')
            self.dialog.notification(self.local_string(30300), self.local_string(30351), self.nhl_logo, self.display_milliseconds, False)

    def local_to_pacific(self):
        pacific = pytz.timezone('US/Pacific')
        local_to_utc = datetime.now(pytz.timezone('UTC'))
        local_to_pacific = local_to_utc.astimezone(pacific).strftime('%Y-%m-%d')
        return local_to_pacific

    def string_to_date(self, string, date_format):
        try:
            date = datetime.strptime(str(string), date_format)
        except TypeError:
            date = datetime(*(time.strptime(str(string), date_format)[0:6]))

        return date

    def check_games_scheduled(self):
        # Check if any games are scheduled for today.
        # If so, check if any are live and if not sleep until first game starts
        json = self.get_scoreboard()
        if json['totalGames'] == 0:
            self.addon.setSetting(id='score_updates', value='false')
            self.dialog.notification(self.local_string(30300), self.local_string(30352), self.nhl_logo, self.display_milliseconds, False)
        else:
            live_games = 0
            for game in json['dates'][0]['games']:
                if game['status']['detailedState'].lower() != 'scheduled' \
                        and game['status']['detailedState'].lower() != 'preview':
                    live_games += 1

            if live_games == 0:
                first_game_start = self.string_to_date(json['dates'][0]['games'][0]['gameDate'], "%Y-%m-%dT%H:%M:%SZ")
                sleep_seconds = int((first_game_start - datetime.utcnow()).total_seconds())
                if sleep_seconds >= 6600:
                    # hour and 50 minutes or more just display hours
                    delay_time = "%s hours" % round(sleep_seconds / 3600)
                elif sleep_seconds >= 4200:
                    # hour and 10 minutes
                    delay_time = "an hour and %s minutes" % round((sleep_seconds / 60) - 60)
                elif sleep_seconds >= 3000:
                    # 50 minutes
                    delay_time = "an hour"
                else:
                    delay_time = "%s minutes" % round((sleep_seconds / 60))

                message = "First game starts in about %s" % delay_time
                self.dialog.notification(self.local_string(30300), message, self.nhl_logo, self.display_milliseconds, False)
                self.monitor.waitForAbort(sleep_seconds)

    def get_scoreboard(self):
        url = self.api_url % self.local_to_pacific()
        headers = {'User-Agent': self.ua_ipad}
        r = requests.get(url, headers=headers)
        return r.json()

    def scoring_updates_on(self):
        return self.addon.getSetting(id="score_updates") == 'true'

    def get_video_playing(self):
        video_playing = ''
        if xbmc.Player().isPlayingVideo(): video_playing = xbmc.Player().getPlayingFile().lower()
        return video_playing

    def get_new_stats(self, game):
        video_playing = self.get_video_playing()
        ateam = game['teams']['away']['team']['abbreviation']
        hteam = game['teams']['home']['team']['abbreviation']
        current_period = game['linescore']['currentPeriod']
        if 'currentPeriodOrdinal' in game['linescore']: current_period = game['linescore']['currentPeriodOrdinal']

        desc = ''
        headshot = ''
        try:
            desc = game['scoringPlays'][-1]['result']['description']
            # Remove Assists if there are none
            if ', assists: none' in desc: desc = desc[:desc.find(', assists: none')]
            player_id = game['scoringPlays'][-1]['players'][0]['player']['link']
            player_id = player_id[player_id.rfind('/') + 1:]
            headshot = self.headshot_url % player_id
        except:
            pass

        game_clock = game['status']['detailedState']
        if 'in progress' in game_clock.lower():
            game_clock = '%s %s' % (game['linescore']['currentPeriodTimeRemaining'], game['linescore']['currentPeriodOrdinal'])

        # Disable spoiler by not showing score notifications for the game the user is currently watching
        if ateam.lower() not in video_playing and hteam.lower() not in video_playing:
            # Sometimes goal desc are generic, don't alert until more info has been added to the feed
            if self.addon.getSetting(id="goal_desc") != 'true' or desc.lower() != 'goal':
                self.new_game_stats.append(
                    {"game_id": game['gamePk'],
                     "away_name": game['teams']['away']['team']['abbreviation'],
                     "home_name": game['teams']['home']['team']['abbreviation'],
                     "away_score": game['linescore']['teams']['away']['goals'],
                     "home_score": game['linescore']['teams']['home']['goals'],
                     "game_clock": game_clock,
                     "period": current_period,
                     "goal_desc": desc,
                     "headshot": headshot})

    def set_display_ms(self):
        display_seconds = int(self.addon.getSetting(id="display_seconds"))
        if display_seconds > 60:
            # Max Seconds 60
            display_seconds = 60
        elif display_seconds < 1:
            # Min Seconds 1
            display_seconds = 1
        self.display_seconds = display_seconds
        # Convert to milliseconds
        self.display_milliseconds = display_seconds * 1000

    def final_score_message(self, new_item):
        # Highlight score of the winning team
        title = 'Final Score'
        if new_item['away_score'] > new_item['home_score']:
            away_score = '[COLOR=%s]%s %s[/COLOR]' % (self.score_color, new_item['away_name'], new_item['away_score'])
            home_score = '%s %s' % (new_item['home_name'], new_item['home_score'])
        else:
            away_score = '%s %s' % (new_item['away_name'], new_item['away_score'])
            home_score = '[COLOR=%s]%s %s[/COLOR]' % (self.score_color, new_item['home_name'], new_item['home_score'])

        game_clock = '[COLOR=%s]%s[/COLOR]' % (self.gametime_color, new_item['game_clock'])
        message = '%s    %s    %s' % (away_score, home_score, game_clock)
        return title, message

    def period_change_message(self, new_item):
        # Notify user that the game has started / period has changed
        title = "Game Update"
        message = '%s %s    %s %s   [COLOR=%s]%s has started[/COLOR]' % \
                  (new_item['away_name'], new_item['away_score'], new_item['home_name'], new_item['home_score'],
                   self.gametime_color, new_item['period'])
        return title, message

    def goal_scored_message(self, new_item, old_item):
        # Highlight score for the team that just scored a goal
        away_score = '%s %s' % (new_item['away_name'], new_item['away_score'])
        home_score = '%s %s' % (new_item['home_name'], new_item['home_score'])
        game_clock = '[COLOR=%s]%s[/COLOR]' % (self.gametime_color, new_item['game_clock'])

        if new_item['away_score'] != old_item['away_score']:
            away_score = '[COLOR=%s]%s[/COLOR]' % (self.score_color, away_score)
        if new_item['home_score'] != old_item['home_score']:
            home_score = '[COLOR=%s]%s[/COLOR]' % (self.score_color, home_score)

        if self.addon.getSetting(id="goal_desc") == 'false':
            title = 'Score Update'
            message = '%s    %s    %s' % (away_score, home_score, game_clock)
        else:
            title = '%s    %s    %s' % (away_score, home_score, game_clock)
            message = new_item['goal_desc']

        return title, message

    def check_if_changed(self, new_item, old_item):
        title = None
        message = None
        img = self.nhl_logo
        xbmc.log("-"+str(new_item))
        xbmc.log("~"+str(old_item))

        if 'final' in new_item['game_clock'].lower() and new_item['game_clock'].lower() != old_item['game_clock'].lower():
            title, message = self.final_score_message(new_item)
        elif new_item['period'] != old_item['period']:
            # Notify user that the game has started / period has changed
            title, message = self.period_change_message(new_item)
        elif (new_item['home_score'] != old_item['home_score'] and new_item['home_score'] > 0) \
                or (new_item['away_score'] != old_item['away_score'] and new_item['away_score'] > 0):
            # Highlight score for the team that just scored a goal
            title, message = self.goal_scored_message(new_item, old_item)
            # Get goal scorers headshot if notification is a score update
            if self.addon.getSetting(id="goal_desc") == 'true' and new_item['headshot'] != '': img = new_item['headshot']

        if title is not None and message is not None:
            self.dialog.notification(title, message, img, self.display_milliseconds, False)
            self.monitor.waitForAbort(self.display_seconds + 5)

    def scoring_updates(self):
        first_time_thru = 1
        old_game_stats = []
        while self.scoring_updates_on() and not self.monitor.abortRequested():
            json = self.get_scoreboard()
            self.new_game_stats.clear()
            xbmc.log("Games: " + str(len(json['dates'][0]['games'])))
            for game in json['dates'][0]['games']:
                # Break out of loop if updates disabled
                if not self.scoring_updates_on(): break
                self.get_new_stats(game)

            if first_time_thru != 1:
                self.set_display_ms()
                all_games_finished = 1
                xbmc.log("new game stats count: " + str(len(self.new_game_stats)))
                xbmc.log("old game stats count: " + str(len(old_game_stats)))
                for new_item in self.new_game_stats:
                    if not self.scoring_updates_on(): break
                    # Check if all games have finished
                    if 'final' not in new_item['game_clock'].lower(): all_games_finished = 0
                    for old_item in old_game_stats:
                        if not self.scoring_updates_on(): break
                        if new_item['game_id'] == old_item['game_id']:
                            self.check_if_changed(new_item, old_item)

                # if all games have finished for the night stop the script
                if all_games_finished and self.scoring_updates_on():
                    self.addon.setSetting(id='score_updates', value='false')
                    # If the user is watching a game don't display the all games finished message
                    if 'nhl_game_video' not in self.get_video_playing():
                        title = "Score Notifications"
                        self.dialog.notification(title, 'All games have ended, good night.', self.nhl_logo, 5000, False)

            old_game_stats.clear()
            old_game_stats = copy.deepcopy(self.new_game_stats)
            first_time_thru = 0
            # If kodi exits or goes idle stop running the script
            if self.monitor.waitForAbort(self.wait):
                xbmc.log("**************Abort Called**********************")
                break

