from resources.lib.scores import *

# dialog = xbmcgui.Dialog()
# title = "Score Notifications"
scores = Scores()
scores.toggle_script()

# # Toggle the setting
# if not scores.scoring_updates_on():
#     xbmcaddon.Addon().setSetting(id='score_updates', value='true')
#     dialog.notification(title, 'Starting...', nhl_logo, 5000, False)
#     score.scoring_updates()
# else:
#     xbmcaddon.Addon().setSetting(id='score_updates', value='false')
#     dialog.notification(title, 'Stopping...', nhl_logo, 5000, False)
