import xbmc, xbmcvfs, xbmcgui, xbmcaddon
from time import sleep
from datetime import datetime
import requests
import os, pytz

class Scores():

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
        self.wait = 30
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

        gid = str(game['gamePk'])
        ateam = game['teams']['away']['team']['abbreviation']
        hteam = game['teams']['home']['team']['abbreviation']
        ascore = str(game['linescore']['teams']['away']['goals'])
        hscore = str(game['linescore']['teams']['home']['goals'])

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
            self.new_game_stats.append([gid, ateam, hteam, ascore, hscore, gameclock, current_period, desc, headshot])

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

    def check_if_changed(self, new_item, old_item):
            # --------------------------
            # Array key
            # --------------------------
            # 0 = game id
            # 1 = away team
            # 2 = home team
            # 3 = away score
            # 4 = home score
            # 5 = game clock
            # 6 = current period
            # 7 = goal description
            # 8 = headshot img url
            # --------------------------

            # If the score for either team has changed and is greater than zero.
            # Or if the game has just ended show the final score
            # Or the current peroid has changed
            if ((new_item[3] != old_item[3]) or (new_item[4] != old_item[4])) or (new_item[5].upper().find('FINAL') != -1 and old_item[5].upper().find('FINAL') == -1) or (new_item[6] != old_item[6]):

                # Game variables
                ateam = new_item[1]
                hteam = new_item[2]
                ascore = new_item[3]
                hscore = new_item[4]
                gameclock = new_item[5]
                current_period = new_item[6]
                desc = new_item[7]
                headshot = new_item[8]

                notify_mode = ''
                if new_item[5].upper().find('FINAL') != -1:
                    # Highlight score of the winning team
                    notify_mode = 'final'
                    title = 'Final Score'
                    if int(ascore) > int(hscore):
                        message = '[COLOR=' + SCORE_COLOR + ']' + ateam + ' ' + ascore + '[/COLOR]    ' + hteam + ' ' + hscore + '    [COLOR=' + GAMETIME_COLOR + ']' + gameclock + '[/COLOR]'
                    else:
                        message = ateam + ' ' + ascore + '    [COLOR=' + SCORE_COLOR + ']' + hteam + ' ' + hscore + '[/COLOR]    [COLOR=' + GAMETIME_COLOR + ']' + gameclock + '[/COLOR]'

                elif new_item[6] != old_item[6]:
                    # Notify user that the game has started / period has changed
                    notify_mode = 'game'
                    title = "Game Update"
                    message = ateam + ' ' + ascore + '    ' + hteam + ' ' + hscore + '   [COLOR=' + GAMETIME_COLOR + ']' + current_period + ' has started[/COLOR]'

                else:
                    # Highlight score for the team that just scored a goal
                    notify_mode = 'score'
                    if new_item[3] != old_item[3]: ascore = '[COLOR=' + SCORE_COLOR + ']' + new_item[
                        3] + '[/COLOR]'
                    if new_item[4] != old_item[4]: hscore = '[COLOR=' + SCORE_COLOR + ']' + new_item[
                        4] + '[/COLOR]'

                    if self.addon.getSetting(id="goal_desc") == 'false':
                        title = 'Score Update'
                        message = ateam + ' ' + ascore + '    ' + hteam + ' ' + hscore + '    [COLOR=' + GAMETIME_COLOR + ']' + gameclock + '[/COLOR]'
                    else:
                        title = ateam + ' ' + ascore + '    ' + hteam + ' ' + hscore + '    [COLOR=' + GAMETIME_COLOR + ']' + gameclock + '[/COLOR]'
                        message = desc

                if self.scoring_updates_on():
                    img = self.nhl_logo
                    # Get goal scorers head shot if notification is a score update
                    if self.addon.getSetting(id="goal_desc") == 'true' and notify_mode == 'score' and headshot != '':
                        img = headshot
                    self.dialog.notification(title, message, self.nhl_logo, display_milliseconds, False)
                    self.monitor.waitForAbort(display_seconds + 5)


    def scoring_updates(self):
        todays_date = self.local_to_eastern()

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
                    if new_item[5].upper().find('FINAL') == -1:
                        all_games_finished = 0

                    for old_item in self.old_game_stats:
                        # Break out of loop if updates disabled
                        if not self.scoring_updates_on():
                            break
                        if new_item[0] == old_item[0]:
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

