import xbmc, xbmcvfs, xbmcgui, xbmcaddon
from time import sleep
from datetime import datetime
import requests
import os, pytz


class Scores:

    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.addon_path = xbmcvfs.translatePath(self.addon.getAddonInfo('path'))
        self.local_string = self.addon.getLocalizedString
        self.ua_ipad = 'Mozilla/5.0 (iPad; CPU OS 8_4 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Mobile/12H143 ipad nhl 5.0925'
        self.nhl_logo = os.path.join(self.addon_path,'resources','nhl_logo.png')
        self.api_url = 'http://statsapi.web.nhl.com/api/v1/schedule?date=%s&expand=schedule.teams,schedule.linescore,schedule.scoringplays'
        self.headshot_url = 'http://nhl.bamcontent.com/images/headshots/current/60x60/%s@2x.png'
        # Colors
        self.score_color = 'FF00B7EB'
        self.gametime_color = 'FFFFFF66'
        self.first_time_thru = 1
        self.old_game_stats = []
        self.new_game_stats = []
        self.wait = 3
        self.display_seconds = 5
        self.display_milliseconds = 5000
        self.dialog = xbmcgui.Dialog()
        self.monitor = xbmc.Monitor()

    def toggle_script(self):
        # Toggle the setting
        if not self.scoring_updates_on():
            self.addon.setSetting(id='score_updates', value='true')
            self.dialog.notification(self.local_string(30300), 'Starting...', self.nhl_logo, self.display_milliseconds, False)
            self.scoring_updates()
        else:
            self.addon.setSetting(id='score_updates', value='false')
            self.dialog.notification(self.local_string(30300), 'Stopping...', self.nhl_logo, self.display_milliseconds, False)

    def local_to_eastern(self):
        eastern = pytz.timezone('US/Eastern')
        local_to_utc = datetime.now(pytz.timezone('UTC'))
        local_to_eastern = local_to_utc.astimezone(eastern).strftime('%Y-%m-%d')
        return local_to_eastern

    def get_scoreboard(self,date):
        url = self.api_url % date
        headers = {'User-Agent': self.ua_ipad}
        r = requests.get(url, headers=headers)
        return r.json()

    def scoring_updates_on(self):
        return self.addon.getSetting(id="score_updates") == 'true'

    def get_video_playing(self):
        video_playing = ''
        if xbmc.Player().isPlayingVideo():
            video_playing = xbmc.Player().getPlayingFile().lower()
        return video_playing

    def get_new_stats(self, game):
        video_playing = self.get_video_playing()

        gid = game['gamePk']
        ateam = game['teams']['away']['team']['abbreviation']
        hteam = game['teams']['home']['team']['abbreviation']
        ascore = game['linescore']['teams']['away']['goals']
        hscore = game['linescore']['teams']['home']['goals']

        # Team names (these can be found in the live streams url)
        atcommon = game['teams']['away']['team']['abbreviation']
        htcommon = game['teams']['home']['team']['abbreviation']
        gameclock = game['status']['detailedState']

        current_period = game['linescore']['currentPeriod']
        try:
            current_period = game['linescore']['currentPeriodOrdinal']
        except:
            pass

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

        if 'In Progress' in gameclock:
            gameclock = game['linescore']['currentPeriodTimeRemaining'] + ' ' + game['linescore']['currentPeriodOrdinal']

        # Disable spoiler by not showing score notifications for the game the user is currently watching
        if video_playing.find(atcommon.lower()) == -1 and video_playing.find(htcommon.lower()) == -1:
            if self.addon.getSetting(id="goal_desc") == 'false' or self.addon.getSetting(id="goal_desc") == 'true' and desc.lower() != 'goal':
                self.new_game_stats.append(
                    {"game_id": gid,
                     "away_name": ateam,
                     "home_name": hteam,
                     "away_score": ascore,
                     "home_score": hscore,
                     "game_clock": gameclock,
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
        game_clock = '[COLOR=%s]%s[/COLOR]' % (self.gametime_color, new_item['game_clock'])
        if new_item['away_score'] > new_item['home_score']:
            away_score = '[COLOR=%s]%s %s[/COLOR]' % (self.score_color, new_item['away_name'], new_item['away_score'])
            home_score = '%s %s' % (new_item['home_name'], new_item['home_score'])
        else:
            away_score = '%s %s' % (new_item['away_name'], new_item['away_score'])
            home_score = '[COLOR=%s]%s %s[/COLOR]' % (self.score_color, new_item['home_name'], new_item['home_score'])

        message = '%s    %s    %s' % (away_score, home_score, game_clock)
        return title, message

    def period_change_message(self, new_item):
        # Notify user that the game has started / period has changed
        title = "Game Update"

        message = '%s %s    %s %s   [COLOR=%s]%s has started[/COLOR]' % \
                  (new_item['away_name'], new_item['away_score'], new_item['home_name'], new_item['home_score'],
                   self.gametime_color, new_item['period'])
        return title, message

    def goal_scored_message(self, new_item):
        # Highlight score for the team that just scored a goal
        away_score = '%s %s' % (new_item['away_name'], new_item['away_score'])
        home_score = '%s %s' % (new_item['home_name'], new_item['home_score'])
        game_clock = '[COLOR=%s]%s[/COLOR]' % (self.gametime_color, new_item['game_clock'])

        if new_item['away_score'] != new_item['away_score']:
            away_score = '[COLOR=%s]%s[/COLOR]' % (self.score_color, away_score)
        if new_item['home_score'] != new_item['home_score']:
            home_score = '[COLOR=%s]%s[/COLOR]' % (self.score_color, home_score)

        if self.addon.getSetting(id="goal_desc") == 'false':
            title = 'Score Update'
            message = '%s    %s    %s' % (away_score, home_score, game_clock)
        else:
            title = '%s    %s    %s' % (away_score, home_score, game_clock)
            message = new_item['goal_desc']

        return title, message

    def check_if_changed(self, new_item, old_item):
        # If the score for either team has changed and is greater than zero.
        # Or if the game has just ended show the final score
        # Or the current period has changed
        # if ((new_item[3] != old_item[8]) or (new_item[4] != old_item[4])) or (new_item[5].upper().find('FINAL') != -1 and old_item[5].upper().find('FINAL') == -1) or (new_item[6] != old_item[6]):

        notify_mode = ''
        if 'FINAL' in new_item['game_clock'].upper():
            notify_mode = 'final'
            title, message = self.final_score_message(new_item)
        elif new_item['period'] != old_item['period']:
            # Notify user that the game has started / period has changed
            notify_mode = 'game'
            title, message = self.period_change_message(new_item)
        else:
            # Highlight score for the team that just scored a goal
            notify_mode = 'score'
            title, message = self.goal_scored_message(new_item)

        if self.scoring_updates_on():
            img = self.nhl_logo
            # Get goal scorers head shot if notification is a score update
            if self.addon.getSetting(id="goal_desc") == 'true' and notify_mode == 'score' and new_item['headshot'] != '':
                img = new_item['headshot']
            self.dialog.notification(title, message, img, self.display_milliseconds, False)
            self.monitor.waitForAbort(self.display_seconds + 5)

    def scoring_updates(self):
        todays_date = self.local_to_eastern()
        todays_date = '2022-04-06'

        while self.scoring_updates_on() and not self.monitor.abortRequested():
            json = self.get_scoreboard(todays_date)
            for game in json['dates'][0]['games']:
                # Break out of loop if updates disabled
                if not self.scoring_updates_on():
                    break
                self.get_new_stats(game)

            if self.first_time_thru != 1:
                self.set_display_ms()
                all_games_finished = 1
                for new_item in self.new_game_stats:
                    if not self.scoring_updates_on():
                        break
                    # Check if all games have finished
                    if 'FINAL' in new_item['game_clock'].upper():
                        all_games_finished = 0

                    for old_item in self.old_game_stats:
                        # Break out of loop if updates disabled
                        if not self.scoring_updates_on():
                            break
                        xbmc.log(str(new_item))
                        xbmc.log(str(old_item))
                        if new_item['game_id'] == old_item['game_id']:
                            self.check_if_changed(new_item, old_item)

                # if all games have finished for the night kill the thread
                if all_games_finished and self.scoring_updates_on():
                    self.addon.setSetting(id='score_updates', value='false')
                    # If the user is watching a game don't display the all games finished message
                    if 'nhl_game_video' not in self.get_video_playing():
                        dialog = xbmcgui.Dialog()
                        title = "Score Notifications"
                        self.dialog.notification(title, 'All games have ended, good night.', self.nhl_logo, 5000, False)

            self.old_game_stats = self.new_game_stats
            self.first_time_thru = 0
            # If kodi exits or goes idle stop running the script
            if self.monitor.waitForAbort(self.wait):
                xbmc.log("**************Abort Called**********************")
                break

