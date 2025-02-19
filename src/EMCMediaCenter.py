﻿#!/usr/bin/python
# encoding: utf-8
#
# Copyright (C) 2011 by Coolman & Swiss-MAD
#
# In case of reuse of this source code please do not remove this copyright.
#
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	For more information on the GNU General Public License see:
#	<http://www.gnu.org/licenses/>.
#
from __future__ import print_function, absolute_import
import os, re
import sys, traceback
from time import time

from Components.config import *
from Components.ActionMap import ActionMap, NumberActionMap, HelpableActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.ServiceEventTracker import ServiceEventTracker, InfoBarBase
from enigma import eTimer, iPlayableService, iServiceInformation, eServiceReference, iServiceKeys, getDesktop
from Screens.Screen import Screen
from Screens.InfoBarGenerics import *
from Screens.InfoBar import MoviePlayer, InfoBar
from Screens.MessageBox import MessageBox
from Screens.HelpMenu import HelpableScreen
from Tools.BoundFunction import boundFunction
from Tools.Directories import fileExists, resolveFilename, SCOPE_LANGUAGE, SCOPE_PLUGINS
from .ISO639 import LanguageCodes as langC
from Components.Language import language

try:
	from enigma import eMediaDatabase
	isDreamOS = True
except:
	isDreamOS = False

# Zap to Live TV of record
from Screens.MessageBox import MessageBox
from Tools.Notifications import AddPopup

# Plugin internal
from .EnhancedMovieCenter import _
from .EMCTasker import emcDebugOut
from .DelayedFunction import DelayedFunction
from .CutListSupport import CutList
from .InfoBarSupport import InfoBarSupport
from Components.Sources.EMCCurrentService import EMCCurrentService
from .ServiceSupport import ServiceCenter

# Cover
from Components.AVSwitch import AVSwitch
from Components.Pixmap import Pixmap
from enigma import ePicLoad

from .MovieCenter import sidDVD, sidDVB, toggleProgressService, getPosterPath

from .RecordingsControl import getRecording
import NavigationInstance

from six.moves import range


dvdPlayerPlg = "%s%s"%(resolveFilename(SCOPE_PLUGINS), "Extensions/DVDPlayer/plugin.py")

class EMCMoviePlayerSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent)
		self.skinName = "EMCMoviePlayerSummary"
		self["Service"] = EMCCurrentService(session.nav, parent)

def getSkin():
	skin = None
	CoolWide = getDesktop(0).size().width()
	if CoolWide == 1280:
		skin = "/usr/lib/enigma2/python/Plugins/Extensions/EnhancedMovieCenter/CoolSkin/EMCMediaCenter.xml"
	elif CoolWide == 1920:
		skin = "/usr/lib/enigma2/python/Plugins/Extensions/EnhancedMovieCenter/CoolSkin/EMCMediaCenter_1080.xml"
	return skin

# Just a dummy to prevent crash
class InfoBarTimeshift:
	def __init__(self):
		pass

	def startTimeshift(self):
		pass

class EMCMediaCenter( CutList, Screen, HelpableScreen, InfoBarTimeshift, InfoBarSupport ):

	ENABLE_RESUME_SUPPORT = True
	ALLOW_SUSPEND = True

	def __init__(self, session, playlist, playall=None, lastservice=None):

		# The CutList must be initialized very first
		CutList.__init__(self)
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		InfoBarTimeshift.__init__(self)
		InfoBarSupport.__init__(self)

		# Skin
		if config.EMC.use_orig_skin.value:
			self.skinName = "EMCMediaCenterOwn"
		else:
			self.skinName = "EMCMediaCenter"
		skin = getSkin()
		if skin:
			Cool = open(skin)
			self.skin = Cool.read()
			Cool.close()

		self.serviceHandler = ServiceCenter.getInstance()

		# EMC Source
		self["Service"] = EMCCurrentService(session.nav, self)

		# Events
		if isDreamOS:
			self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
				{
					iPlayableService.evEnd: self.__serviceStopped,
					iPlayableService.evStopped: self.__serviceStopped,
					iPlayableService.evAudioListChanged: self.__osdAudioInfoAvail,
					iPlayableService.evSubtitleListChanged: self.__osdSubtitleInfoAvail,
					iPlayableService.evUser+3: self.__osdFFwdInfoAvail,
					iPlayableService.evUser+4: self.__osdFBwdInfoAvail,
					iPlayableService.evUser+6: self.__osdAngleInfoAvail,
					iPlayableService.evUser+7: self.__chapterUpdated,
					iPlayableService.evUser+8: self.__titleUpdated,
					iPlayableService.evUser+9: self.__menuOpened,
					iPlayableService.evUser+10: self.__menuClosed
				})
		else:
			self.__event_tracker = ServiceEventTracker(screen=self, eventmap=
				{
					# Disabled for tests
					# If we enable them, the sound will be delayed for about 2 seconds ?
					iPlayableService.evStart: self.__serviceStarted,
					iPlayableService.evStopped: self.__serviceStopped,
					#iPlayableService.evEnd: self.__evEnd,
					#iPlayableService.evEOF: self.__evEOF,
					#iPlayableService.evUser: self.__timeUpdated,
					#iPlayableService.evUser+1: self.__statePlay,
					#iPlayableService.evUser+2: self.__statePause,
					iPlayableService.evUser+3: self.__osdFFwdInfoAvail,
					iPlayableService.evUser+4: self.__osdFBwdInfoAvail,
					#iPlayableService.evUser+5: self.__osdStringAvail,
					iPlayableService.evUser+6: self.__osdAudioInfoAvail,
					iPlayableService.evUser+7: self.__osdSubtitleInfoAvail,
					iPlayableService.evUser+8: self.__chapterUpdated,
					iPlayableService.evUser+9: self.__titleUpdated,
					iPlayableService.evUser+11: self.__menuOpened,
					iPlayableService.evUser+12: self.__menuClosed,
					iPlayableService.evUser+13: self.__osdAngleInfoAvail
				})

			# Keymap
	#		self["SeekActions"] = HelpableActionMap(self, "InfobarSeekActions", 							-1 higher priority
	#		self["MovieListActions"] = HelpableActionMap(self, "InfobarMovieListActions", 		0
	#		self["ShowHideActions"] = ActionMap( ["InfobarShowHideActions"] ,  								0
	#		self["EPGActions"] = HelpableActionMap(self, "InfobarEPGActions",									0
	#		self["CueSheetActions"] = HelpableActionMap(self, actionmap,											1 lower priority
	#		self["InstantExtensionsActions"] = HelpableActionMap(self, "InfobarExtensions", 	1 lower priority
	#		self["NumberActions"] = NumberActionMap( [ "NumberActions"],											0 Set by EMC to 2 very lower priority
	#		self["TeletextActions"] = HelpableActionMap(self, "InfobarTeletextActions",				0 Set by EMC to 2 very lower priority
	#		self["MenuActions"] = HelpableActionMap(self, "InfobarMenuActions",  							0 Set by EMC to 2 very lower priority
		if config.EMC.movie_exit.value:
			self["actions"] = HelpableActionMap(self, "CoolPlayerActions",
				{
					"leavePlayer":	(self.leavePlayer, 		_("Stop playback")),
				}, -1)
		else:
			self["actions"] = HelpableActionMap(self, "CoolPlayerActions2",
				{
					"leavePlayer":	(self.leavePlayer, 		_("Stop playback")),
				}, -1)

		self["DVDPlayerPlaybackActions"] = HelpableActionMap(self, "EMCDVDPlayerActions",
			{
				"dvdMenu": (self.enterDVDMenu, _("show DVD main menu")),
				#"showInfo": (self.showInfo, _("toggle time, chapter, audio, subtitle info")),
				"nextChapter": (self.nextChapter, _("forward to the next chapter")),
				"prevChapter": (self.prevChapter, _("rewind to the previous chapter")),
				"nextTitle": (self.nextTitle, _("jump forward to the next title")),
				"prevTitle": (self.prevTitle, _("jump back to the previous title")),
				"dvdAudioMenu": (self.enterDVDAudioMenu, _("(show optional DVD audio menu)")),
				"nextAudioTrack": (self.nextAudioTrack, _("switch to the next audio track")),
				"nextSubtitleTrack": (self.nextSubtitleTrack, _("switch to the next subtitle language")),
				"nextAngle": (self.nextAngle, _("switch to the next angle")),
			}, 1) # lower priority
		# Only enabled if playing a dvd
		self["DVDPlayerPlaybackActions"].setEnabled(False)

		self["DVDMenuActions"] = ActionMap(["WizardActions"],
			{
				"left": self.keyLeft,
				"right": self.keyRight,
				"up": self.keyUp,
				"down": self.keyDown,
				"ok": self.keyOk,
				"back": self.keyBack,
			}, 2) # lower priority
		# Only enabled during DVD Menu
		self["DVDMenuActions"].setEnabled(False)

		self["GeneralPlayerPlaybackActions"] = HelpableActionMap(self, "EMCGeneralPlayerActions",
			{
				"showExtensions": (self.openExtensions, _("view extensions...")),
				"EMCGreen":	(self.CoolAVSwitch, _("Format AVSwitch")),
				"seekFwd": (self.seekFwd, _("Seek forward")),
				"seekBack": (self.seekBack, _("Seek backward")),
				"nextTitle": (self.nextTitle, _("jump forward to the next title")),
				"prevTitle": (self.prevTitle, _("jump back to the previous title")),
				"movieInfo": (self.infoMovie, _("Movie information")),
			},-2) # default priority

		self["MenuActions"].prio = 2
		if "TeletextActions" in self:
			self["TeletextActions"].prio = 2
		else:
			emcDebugOut("[EMCMediaCenter] teletext plugin not installed")
		self["NumberActions"].prio = 2

		# Cover Anzeige
		self["Cover"] = Pixmap()

		# DVD Player
		self["audioLabel"] = Label("")
		self["subtitleLabel"] = Label("")
		self["angleLabel"] = Label("")
		self["chapterLabel"] = Label("")
		self["anglePix"] = Pixmap()
		self["anglePix"].hide()
		self.last_audioTuple = None
		self.last_subtitleTuple = None
		self.last_angleTuple = None
		self.totalChapters = 0
		self.currentChapter = 0
		self.totalTitles = 0
		self.currentTitle = 0
		self.in_menu = None
		self.dvdScreen = None

		# Further initialization
		self.firstStart = True
		self.stopped = False
		self.closedByDelete = False
		self.closeAll = False

		self.lastservice = lastservice or self.session.nav.getCurrentlyPlayingServiceReference()
		if not self.lastservice:
			self.lastservice = InfoBar.instance.servicelist.servicelist.getCurrent()
		self.playlist = playlist
		self.playall = playall
		self.playcount = -1
		self.service = None
		self.allowPiP = True
		self.allowPiPSwap = False			# this is needed for vti-image
		self.realSeekLength = None
		self.servicelist = InfoBar.instance.servicelist

		self.picload = ePicLoad()
		try:
			self.picload_conn = self.picload.PictureData.connect(self.showCoverCallback)
		except:
			self.picload.PictureData.get().append(self.showCoverCallback)

		# Record events
		try:
			NavigationInstance.instance.RecordTimer.on_state_change.append(self.recEvent)
		except Exception as e:
			emcDebugOut("[EMCMediaCenter] Record observer add exception:\n" + str(e))

		# Dialog Events
		self.onShown.append(self.__onShow)  # Don't use onFirstExecBegin() it will crash
		self.onClose.append(self.__onClose)
		self.file_format = "(.ts|.avi|.mkv|.divx|.f4v|.flv|.img|.iso|.m2ts|.m4v|.mov|.mp4|.mpeg|.mpg|.mts|.vob|.asf|.wmv|.stream|.webm)"

	### Cover anzeige
	def showCover(self):
		service = self.playlist[self.playcount]
		path = service.getPath()
		jpgpath = getPosterPath(path)
		if not os.path.exists(jpgpath):
			self["Cover"].hide()
		else:
			sc = AVSwitch().getFramebufferScale() # Maybe save during init
			size = self["Cover"].instance.size()
			if self.picload:
				self.picload.setPara((size.width(), size.height(), sc[0], sc[1], False, 1, config.EMC.movie_cover_background.value)) # Background dynamically
				self.picload.startDecode(jpgpath)

	def showCoverCallback(self, picInfo=None):
		if self.picload and picInfo:
			ptr = self.picload.getData()
			if ptr != None:
				self["Cover"].instance.setPixmap(ptr)
				self["Cover"].show()

	def CoolAVSwitch(self):
		idx = 0
		choices = []
		if os.path.exists("/proc/stb/video/policy_choices"):
			f = open("/proc/stb/video/policy_choices")
			entrys = f.readline().replace("\n", "").split(" ", -1)
			for x in entrys:
				idx += 1
				entry = idx, x
				choices.append(entry)
			f.close()
			if os.path.exists("/proc/stb/video/policy"):
				act = open("/proc/stb/video/policy").read()[:-1]
				for x in choices:
					if act == x[1]:
						actIdx = x[0]
				if actIdx == len(choices):
					actIdx = 0
				for x in choices:
					if x[0] == actIdx + 1:
						newChoice = x[1]
				try:
					f = open("/proc/stb/video/policy", "w")
					f.write(newChoice)
					f.close()
				except Exception as e:
					print("[EMCMediaCenter] CoolAVSwitch exception:" + str(e))

	def getCurrentEvent(self):
		service = self.currentlyPlayedMovie()
		if service:
			info = self.serviceHandler.info(service)
			return info and info.getEvent(service)

	def infoMovie(self):
		try:
			from .MovieSelection import IMDbEventViewSimple
			from ServiceReference import ServiceReference
			service = self.currentlyPlayedMovie()

			evt = self.getCurrentEvent()
			if evt:
				self.session.open(IMDbEventViewSimple, evt, ServiceReference(service))
		except Exception as e:
			emcDebugOut("[EMCPlayer] showMovies detail exception:\n" + str(e))

	def __onShow(self):
		if self.firstStart:
			# Avoid new playback if the user switches between MovieSelection and MoviePlayer
			self.firstStart = False
			self.evEOF()	# begin playback
			if self.service and self.service.type != sidDVB:
				self.realSeekLength = self.getSeekLength()

	def evEOF(self, needToClose=False, prevTitle=False):
		# see if there are more to play
		playlist_string = "[ "
		for p in self.playlist:
			playlist_string += (os.path.basename(p.getPath()) + " ")
		playlist_string += "]"
		print("EMC PLAYER evEOF", self.playall, self.playcount, playlist_string)
		if self.playall:
			# Play All
			try:
				# for being able to jump back in 'playall' mode, new titles are added to the playlist acting like a cache
				# (the generator 'getNextService' cannot easily be made bidirectional, using os.walk)
				if prevTitle:
					if self.playcount > 0:
						self.playcount -= 2
					else:
						self.playcount -= 1
				else:
					if self.playcount == -1:
						self.playlist = [next(self.playall)]
					elif (self.playcount + 1) == len(self.playlist):
						self.playlist.append(next(self.playall))
						if len(self.playlist) > 25:
							del self.playlist[0]
							self.playcount -= 1
			except StopIteration:
				self.playall = None
				self.playlist = []

		if (self.playcount + 1) < len(self.playlist):
			self.playcount += 1
			service = self.playlist[self.playcount]
			#TODO Problem with VLC
			path = service and service.getPath()
			if os.path.exists(path): #TODO use ext != vlc but must be prepared first
				# Why should the file be removed? Maybe that's the problem with "no Cutlist while recording"
				#cutspath = path + ".cuts"
				#if os.path.exists(cutspath):
					# prepare cut list
					#try:
					#	# Workaround for not working E2 cue.setCutListEnable not working :-(
					#	# We always have to set this permission, we can not detect all stop preview events
					#	os.chmod(cutspath, 755)
					#	print "EMC set chmod read and write"
					#except:
					#	pass
					# Workaround for E2 dvb player bug in combination with running recordings and existings cutlists
					#record = getRecording(path)
					#if record:
						#try:
							# os.remove(cutspath)
						#except:
						#	pass
				# Further cutlist handling
				toggleProgressService(service, True)
				self.service = service

				if service and service.type == sidDVD:
					# Only import DVDPlayer, if we want to play a DVDPlayer format
					if fileExists(dvdPlayerPlg) or fileExists("%sc"%dvdPlayerPlg):
						try:
							from Plugins.Extensions.DVDPlayer import servicedvd # load c++ part of dvd player plugin
						except:
							pass
						from Plugins.Extensions.DVDPlayer.plugin import DVDOverlay
						if not self.dvdScreen:
							self.dvdScreen = self.session.instantiateDialog(DVDOverlay)
					else:
						self.session.open(MessageBox, _("No DVD-Player found!"), MessageBox.TYPE_ERROR, 10)
						self.leavePlayer(True)
						return
					if "TeletextActions" in self:
						self["TeletextActions"].setEnabled(False)
					self["DVDPlayerPlaybackActions"].setEnabled(True)
				else:
					if self.dvdScreen:
						self.dvdScreen.close()
						self.dvdScreen = None
					else:
						self.dvdScreen = None
					if "TeletextActions" in self:
						self["TeletextActions"].setEnabled(True)
					self["DVDPlayerPlaybackActions"].setEnabled(False)

				# Check if the video preview is active and already running
		#				if config.EMC.movie_preview.value:
		#					ref = self.session.nav.getCurrentlyPlayingServiceReference()
		#					if ref and service and ref.getPath() == service.getPath():
		#						#s = self.session.nav.getCurrentService()
		#						#cue = s and s.cueSheet()
		#						#if cue is not None:
		#							#cue.setCutListEnable(1)
		#						self.downloadCuesheet()
		#							#print "EMC cue.setCutListEnable(1)"
		#						#return

				# Is this really necessary
				# TEST for M2TS Audio problem
				#self.session.nav.stopService()

				# Start playing movie
				self.session.nav.playService(service)

				if self.service and self.service.type != sidDVB:
					self.realSeekLength = self.getSeekLength()

				if service and service.type == sidDVD:
					# Seek will cause problems with DVDPlayer!
					# ServiceDVD needs this to start
					subs = self.getServiceInterface("subtitle")
					if subs and self.dvdScreen:
						subs.enableSubtitles(self.dvdScreen.instance, None)
				else:
					# TEST for M2TS Audio problem
					#self.setSeekState(InfoBarSeek.SEEK_STATE_PLAY)
					#TODO Do we need this
					#self.doSeek(0)
					#TODO AutoSelect subtitle for DVD Player is not implemented yet
					DelayedFunction(750, self.setAudioTrack)      # we need that to configure! on some images it comes with 200 too early
					DelayedFunction(750, self.setSubtitleState, True)

				### Cover anzeige
				self.showCover()
			else:
				self.session.open(MessageBox, _("Skipping movie, the file does not exist.\n\n") + service.getPath(), MessageBox.TYPE_ERROR, 10)
				self.evEOF(needToClose)

		else:
			if needToClose or config.usage.on_movie_eof.value != "pause":
				self.closedByDelete = needToClose
				self.leavePlayer(False)

	def leavePlayer(self, stopped=True):
		#TEST is stopped really necessary
		self.stopped = stopped

		self.setSubtitleState(False)
		if self.dvdScreen:
			self.dvdScreen.close()

		# Possible Problem: Avoid GeneratorExit exception
		#if self.playall:
		#	playall.close()

		if self.service and self.service.type != sidDVB:
			self.makeUpdateCutList()

		reopen = False
		try:
#			self.recordings.returnService = self.service
			if self.stopped:
				emcDebugOut("[EMCPlayer] Player closed by user")
				if config.EMC.movie_reopen.value:
					#self.recordings.show()
					reopen = True
			elif self.closedByDelete:
				emcDebugOut("[EMCPlayer] closed due to file delete")
				#self.recordings.show()
				reopen = True
			else:
				emcDebugOut("[EMCPlayer] closed due to playlist EOF")
				if self.closeAll:
					if config.EMC.record_eof_zap.value == "1":
						AddPopup(
									_("EMC\nZap to Live TV of record"),
									MessageBox.TYPE_INFO,
									3,
									"EMCCloseAllAndZap"
								)
				else:
					if config.EMC.movie_reopenEOF.value: # did the player close while movie list was open?
						#self.recordings.show()
						reopen = True
			#self.service = None
		except Exception as e:
			emcDebugOut("[EMCPlayer] leave exception:\n" + str(e))

		self.session.nav.stopService()
		# [Cutlist.Workaround] - part 2
		# Always make a backup-copy when recording is running and we stopped the playback
		if self.stopped:
			if self.service and self.service.type == sidDVB:
				recFileName=self.service.getPath()
				record = getRecording(recFileName)
				if record:
					cutspath = recFileName + '.cuts'
					bcutspath = cutspath + '.save'
					if os.path.exists(cutspath):
						import shutil
						shutil.copy2(cutspath, bcutspath)
		self.close(reopen, self.service)

	def recEvent(self, timer):
		try:
			# Check if record is currently played
			path = timer.Filename + ".ts"
			if path == self.service.getPath():
				# WORKAROUND Player is running during a record ends
				# We should find a more flexible universal solution
				DelayedFunction(500, self.updatePlayer)
				# ATTENTION thist won't fix the other situation
				# If a running record will be played and the player is stopped before the record ends
				# -> Then E2 will overwrite the existing cuts.
		except Exception as e:
			emcDebugOut("[spRO] recEvent exception:\n" + str(e))

	def updatePlayer(self):
		self.updateFromCuesheet()

	def __onClose(self):
		if self.picload:
			del self.picload
		if self.lastservice:
			self.session.nav.playService(self.lastservice)
		# Record events
		try:
			NavigationInstance.instance.RecordTimer.on_state_change.remove(self.recEvent)
		except Exception as e:
			emcDebugOut("[EMCMediaCenter] Record observer remove exception:\n" + str(e))

	##############################################################################
	## Recordings relevant function
	def getLength(self):
		if config.EMC.record_show_real_length.value:
			service = self.service
			path = service and service.getPath()
			if path:
				record = getRecording(path)
				if record:
					#TODO There is still a problem with split records with cut numbers
					begin, end, s = record
					return int((end - begin) * 90000)
		# Fallback
		seek = self.getSeek()
		if seek is None:
			return None
		length = seek.getLength()
		if length[0]:
			return 0
		return length[1]

	def getPosition(self):
		if config.EMC.record_show_real_length.value:
			service = self.service
			path = service and service.getPath()
			if path:
				record = getRecording(path)
				if record:
					begin, end, s = record
					return int((time() - begin) * 90000)
		# Fallback
		seek = self.getSeek()
		if seek is None:
			return None
		pos = seek.getPlayPosition()
		if pos[0]:
			return 0
		return pos[1]

	##############################################################################
	## List functions
	def removeFromPlaylist(self, deletedlist):
		callEOF = False
		for x in deletedlist:
			#TEST
			xp = os.path.basename( x.getPath() )
			if xp == os.path.basename( self.service.getPath() ):
				callEOF = True
			for p in self.playlist:
				if xp == os.path.basename( p.getPath() ):
					self.playlist.remove(p)
		if callEOF:
			self.playcount -= 1	# need to go one back since the current was removed
			self.evEOF(True)	# force playback of the next movie or close the player if none left

	def currentlyPlayedMovie(self):
		return self.service

	def movieSelected(self, playlist, playall=None):
		print("EMC movieSelected")

		if playlist is not None and len(playlist) > 0:
			self.playcount = -1
			self.playlist = playlist
			self.playall = playall

			if self.service.type != sidDVB:
				self.makeUpdateCutList()

			self.evEOF()	# start playback of the first movie
		#self.showCover()

	##############################################################################
	## Audio and Subtitles
	def setAudioTrack(self):
		try:
			print("###############################################audio")
			if not config.EMC.autoaudio.value: return
			service = self.session.nav.getCurrentService()
			tracks = service and self.getServiceInterface("audioTracks")
			nTracks = tracks and tracks.getNumberOfTracks() or 0
			if not nTracks: return
			idx = 0
			trackList = []
			for i in range(nTracks):
				audioInfo = tracks.getTrackInfo(i)
				lang = audioInfo.getLanguage()
				print("lang", lang)
				desc = audioInfo.getDescription()
				print("desc", desc)
				if isDreamOS:
					type = audioInfo.getType()
				else:
					type = None
				track = idx, lang, desc, type
				idx += 1
				trackList += [track]
			seltrack = tracks.getCurrentTrack()
			# we need default selected language from image
			# to set the audiotrack if "config.EMC.autoaudio.value" are not set
			syslang = language.getLanguage()[:2]
			if config.EMC.autoaudio.value:
				audiolang = [config.EMC.audlang1.value, config.EMC.audlang2.value, config.EMC.audlang3.value]
			else:
				audiolang = syslang
			useAc3 = config.EMC.autoaudio_ac3.value	# emc has new value, in some images it gives different values for that
			if useAc3:
				matchedAc3 = self.tryAudioTrack(tracks, audiolang, trackList, seltrack, useAc3)
				if matchedAc3: return
				matchedMpeg = self.tryAudioTrack(tracks, audiolang, trackList, seltrack, False)
				if matchedMpeg: return
				tracks.selectTrack(0)		# fallback to track 1(0)
				return
			else:
				matchedMpeg = self.tryAudioTrack(tracks, audiolang, trackList, seltrack, False)
				if matchedMpeg:	return
				matchedAc3 = self.tryAudioTrack(tracks, audiolang, trackList, seltrack, useAc3)
				if matchedAc3: return
				tracks.selectTrack(0)		# fallback to track 1(0)
			print("###############################################audio1")
		except Exception as e:
			emcDebugOut("[EMCPlayer] audioTrack exception:\n" + str(e))

	def tryAudioTrack(self, tracks, audiolang, trackList, seltrack, useAc3):
		for entry in audiolang:
			entry = langC[entry][0]
			print("###############################################audio2")
			for x in trackList:
				try:
					x1val = langC[x[1]][0]
				except:
					x1val = x[1]
				print(x1val)
				print("entry", entry)
				print(x[0])
				print("seltrack", seltrack)
				print(x[2])
				print(x[3])
				if entry == x1val and seltrack == x[0]:
					if useAc3:
						print("###############################################audio3")
						if x[3] == 1 or x[2].startswith('AC'):
							emcDebugOut("[EMCPlayer] audio track is current selected track: " + str(x))
							return True
					else:
						print("###############################################audio4")
						emcDebugOut("[EMCPlayer] audio track is current selected track: " + str(x))
						return True
				elif entry == x1val and seltrack != x[0]:
					if useAc3:
						print("###############################################audio5")
						if x[3] == 1 or x[2].startswith('AC'):
							emcDebugOut("[EMCPlayer] audio track match: " + str(x))
							tracks.selectTrack(x[0])
							return True
					else:
						print("###############################################audio6")
						emcDebugOut("[EMCPlayer] audio track match: " + str(x))
						tracks.selectTrack(x[0])
						return True
		return False

	def trySubEnable(self, slist, match):
		for e in slist:
			print("e", e)
			print("match", langC[match][0])
			if langC[match][0] == e[2]:
				emcDebugOut("[EMCPlayer] subtitle match: " + str(e))
				if self.selected_subtitle != e[0]:
					self.subtitles_enabled = False
					self.selected_subtitle = e[0]
					self.subtitles_enabled = True
					return True
			else:
				print("nomatch")
		return False

	def setSubtitleState(self, enabled):
		try:
			if not config.EMC.autosubs.value or not enabled: return

			if isDreamOS:
				subs = isinstance(self, InfoBarSubtitleSupport) and self.getCurrentServiceSubtitle() or None
				n = subs and subs.getNumberOfSubtitleTracks() or 0
				if n == 0:
					return
				from enigma import iSubtitleType_ENUMS
				from Screens.AudioSelection import SUB_FORMATS, GST_SUB_FORMATS
				self.sub_format_dict = {}
				self.gstsub_format_dict= {}
				for idx, (short, text, rank) in sorted(SUB_FORMATS.items(), key=lambda x: x[1][2]):
					if rank > 0:
						self.sub_format_dict[idx] = short
				for idx, (short, text, rank) in sorted(GST_SUB_FORMATS.items(), key=lambda x: x[1][2]):
					if rank > 0:
						self.gstsub_format_dict[idx] = short
				lt = []
				l = []
				for idx in range(n):
					info = subs.getSubtitleTrackInfo(idx)
					languages = info.getLanguage().split('/')
					print("lang", languages)
					iType = info.getType()
					print("type", iType)
					if iType == iSubtitleType_ENUMS.GST:
						iType = info.getGstSubtype()
						codec = iType in self.gstsub_format_dict and self.gstsub_format_dict[iType] or "?"
					else:
						codec = iType in self.sub_format_dict and self.sub_format_dict[iType] or "?"
					print("codec", codec)

					lt.append((idx, (iType == 1 and "DVB" or iType == 2 and "TTX" or "???"), languages))
				if lt:
					print(lt)
					for e in lt:
						l.append((e[0], e[1], e[2][0] in langC and langC[e[2][0]][0] or e[2][0]))
						if l:
							print(l)
							for sublang in [config.EMC.sublang1.value, config.EMC.sublang2.value, config.EMC.sublang3.value]:
								if self.trySubEnable(l, sublang): break
			else:
				subs = self.getCurrentServiceSubtitle() or self.getServiceInterface("subtitle")
				if subs:
					print("############################subs")
					print(subs.getSubtitleList())
					lt = [ (e, (e[0] == 0 and "DVB" or e[0] == 1 and "TXT" or "???")) for e in (subs and subs.getSubtitleList() or []) ]
					if lt:
						l = [ [e[0], e[1], e[0][4] in langC and langC[e[0][4]][0] or e[0][4] ] for e in lt ]
						if l:
							print(l)
							for sublang in [config.EMC.sublang1.value, config.EMC.sublang2.value, config.EMC.sublang3.value]:
								if self.trySubEnable(l, sublang): break
		except Exception as e:
			emcDebugOut("[EMCPlayer] setSubtitleState exception:\n" + str(e))

	##############################################################################
	## DVD Player keys
	def keyLeft(self):
		self.sendKey(iServiceKeys.keyLeft)

	def keyRight(self):
		self.sendKey(iServiceKeys.keyRight)

	def keyUp(self):
		self.sendKey(iServiceKeys.keyUp)

	def keyDown(self):
		self.sendKey(iServiceKeys.keyDown)

	def keyOk(self):
		self.sendKey(iServiceKeys.keyOk)

	def keyBack(self):
		self.leavePlayer()

	def openExtensions(self):
		try:
			InfoBar.instance and InfoBar.instance.showExtensionSelection()
		except Exception as e:
			emcDebugOut("[EMCPlayer] openExtensions exception:\n" + str(e))

	def nextAudioTrack(self):
		self.sendKey(iServiceKeys.keyUser)

	def nextSubtitleTrack(self):
		self.sendKey(iServiceKeys.keyUser+1)
		if self.dvdScreen:
			# Force show dvd screen
			#self.dvdScreen.hide()
			self.dvdScreen.show()

	def enterDVDAudioMenu(self):
		self.sendKey(iServiceKeys.keyUser+2)

	def nextChapter(self):
		if self.sendKey(iServiceKeys.keyUser+3):
			if config.usage.show_infobar_on_skip.value:
				# InfoBarSeek
				self.showAfterSeek()

	def prevChapter(self):
		if self.sendKey(iServiceKeys.keyUser+4):
			if config.usage.show_infobar_on_skip.value:
				# InfoBarSeek
				self.showAfterSeek()

	def nextTitle(self):
		if self.dvdScreen:
			if self.sendKey(iServiceKeys.keyUser+5):
				if config.usage.show_infobar_on_skip.value:
					# InfoBarSeek
					self.showAfterSeek()
		else:
			if (len(self.playlist) > 1) or self.playall:
				self.evEOF(False)

	def prevTitle(self):
		if self.dvdScreen:
			if self.sendKey(iServiceKeys.keyUser+6):
				if config.usage.show_infobar_on_skip.value:
					# InfoBarSeek
					self.showAfterSeek()
		else:
			if self.playall:
				self.evEOF(False, True) # True=previous
			elif len(self.playlist) > 1:
				if self.playcount >= 1:
					self.playcount -= 2
					self.evEOF(False)

	def enterDVDMenu(self):
		self.sendKey(iServiceKeys.keyUser+7)

	def nextAngle(self):
		self.sendKey(iServiceKeys.keyUser+8)

	def sendKey(self, key):
		if self.service and self.service.type != sidDVD: return None
		keys = self.getServiceInterface("keys")
		if keys:
			keys.keyPressed(key)
		return keys

	def getServiceInterface(self, iface):
		service = self.session.nav.getCurrentService() # self.service
		if service:
			attr = getattr(service, iface, None)
			if callable(attr):
				return attr()
		return None

	##############################################################################
	## DVD Player specific
	def __serviceStarted(self):
		if self.dvdScreen:
			# Force show dvd screen
			#self.dvdScreen.hide()
			self.dvdScreen.show()

	def __serviceStopped(self):
		print("EMC MediaCenter serviceStopped")
		if self.dvdScreen:
			self.dvdScreen.hide()
		subs = self.getServiceInterface("subtitle")
		if subs and self.session and self.session.current_dialog:
			subs.disableSubtitles(self.session.current_dialog.instance)

	def __osdFFwdInfoAvail(self):
		self.setChapterLabel()

	def __osdFBwdInfoAvail(self):
		self.setChapterLabel()

	def __osdAudioInfoAvail(self):
		info = self.getServiceInterface("info")
		audioTuple = info and info.getInfoObject(iServiceInformation.sUser+6)
		if audioTuple:
			audioString = "%d: %s (%s)" % (audioTuple[0], audioTuple[1], audioTuple[2])
			self["audioLabel"].setText(audioString)
			#if audioTuple != self.last_audioTuple: # and not self.in_menu:
			#	self.doShow()
		self.last_audioTuple = audioTuple

	def __osdSubtitleInfoAvail(self):
		info = self.getServiceInterface("info")
		subtitleTuple = info and info.getInfoObject(iServiceInformation.sUser+7)
		if subtitleTuple:
			subtitleString = ""
			if subtitleTuple[0] != 0:
				subtitleString = "%d: %s" % (subtitleTuple[0], subtitleTuple[1])
			self["subtitleLabel"].setText(subtitleString)
			#if subtitleTuple != self.last_subtitleTuple: # and not self.in_menu:
			#	self.doShow()
		self.last_subtitleTuple = subtitleTuple

	def __osdAngleInfoAvail(self):
		info = self.getServiceInterface("info")
		angleTuple = info and info.getInfoObject(iServiceInformation.sUser+8)
		if angleTuple:
			angleString = ""
			if angleTuple[1] > 1:
				angleString = "%d / %d" % (angleTuple[0], angleTuple[1])
				self["anglePix"].show()
			else:
				self["anglePix"].hide()
			self["angleLabel"].setText(angleString)
			#if angleTuple != self.last_angleTuple: # and not self.in_menu:
			#	self.doShow()
		self.last_angleTuple = angleTuple

	def __chapterUpdated(self):
		info = self.getServiceInterface("info")
		if info:
			self.currentChapter = info.getInfo(iServiceInformation.sCurrentChapter)
			self.totalChapters = info.getInfo(iServiceInformation.sTotalChapters)
			self.setChapterLabel()

	def __titleUpdated(self):
		info = self.getServiceInterface("info")
		if info:
			self.currentTitle = info.getInfo(iServiceInformation.sCurrentTitle)
			self.totalTitles = info.getInfo(iServiceInformation.sTotalTitles)
			self.setChapterLabel()
			#if not self.in_menu:
			#self.doShow()

	def __menuOpened(self):
		self.hide()
		#if self.dvdScreen:
		#	# Force show dvd screen
		#	self.dvdScreen.hide()
		#	self.dvdScreen.show()
		self.in_menu = True
		if "ShowHideActions" in self:
			self["ShowHideActions"].setEnabled(False)
		if "MovieListActions" in self:
			self["MovieListActions"].setEnabled(False)
		if "SeekActions" in self:
			self["SeekActions"].setEnabled(False)
		if "DVDMenuActions" in self:
			self["DVDMenuActions"].setEnabled(True)

	def __menuClosed(self):
		#if self.dvdScreen:
		#	self.dvdScreen.hide()
		self.show()
		self.in_menu = None
		if "DVDMenuActions" in self:
			self["DVDMenuActions"].setEnabled(False)
		if "ShowHideActions" in self:
			self["ShowHideActions"].setEnabled(True)
		if "MovieListActions" in self:
			self["MovieListActions"].setEnabled(True)
		if "SeekActions" in self:
			self["SeekActions"].setEnabled(True)

	def createSummary(self):
		if self.service and self.service.type == sidDVD and (fileExists(dvdPlayerPlg) or fileExists("%sc"%dvdPlayerPlg)):
			from Plugins.Extensions.DVDPlayer.plugin import DVDSummary
			return DVDSummary
		else:
			return EMCMoviePlayerSummary

	def setChapterLabel(self):
		chapterLCD = "Menu"
		chapterOSD = "DVD Menu"
		if self.currentTitle > 0:
			chapterLCD = "%s %d" % (_("Chap."), self.currentChapter)
			chapterOSD = "DVD %s %d/%d" % (_("Chapter"), self.currentChapter, self.totalChapters)
			chapterOSD += " (%s %d/%d)" % (_("Title"), self.currentTitle, self.totalTitles)
		self["chapterLabel"].setText(chapterOSD)
		#try:
		#	self.session.summary.updateChapter(chapterLCD)
		#except:
		#	pass

	##############################################################################
	## Implement functions for InfoBarGenerics.py
	# InfoBarShowMovies
	def showMovies(self):
		try:
			from .MovieSelection import EMCSelection
			#self.session.openWithCallback(showMoviesCallback, EMCSelection)
			self.session.open(EMCSelection, returnService=self.service, playerInstance=self)
		except Exception as e:
			emcDebugOut("[EMCPlayer] showMovies exception:\n" + str(e))

	##############################################################################
	## Override functions from InfoBarGenerics.py
	# InfoBarShowHide
	if isDreamOS:
		def serviceStarted(self): #override InfoBarShowHide function
			if self.dvdScreen:
				subTracks = self.getCurrentServiceSubtitle()
				subTracks.enableSubtitles(self.dvdScreen.instance, 0) # give parent widget reference to service for drawing menu highlights in a repurposed subtitle widget
				self.dvdScreen.show()
	#def serviceStarted(self):
	#	if not self.in_menu:
	#		if self.dvdScreen:
	#			self.dvdScreen.show()
	#	else:
	#		InfoBarShowHide.serviceStarted(self)

	def doShow(self):
		### Cover anzeige
		#self.showCover()
		if self.in_menu:
			pass
			#self.hide()
			#if self.dvdScreen:
			#	# Force show dvd screen
			#	self.dvdScreen.hide()
			#	self.dvdScreen.show()
		else:
			#if self.dvdScreen:
			#	self.dvdScreen.hide()
			InfoBarShowHide.doShow(self)

	# InfoBarNumberZap
	def keyNumberGlobal(self, number):
		if self.service and self.service.type == sidDVD:
			if fileExists(dvdPlayerPlg) or fileExists("%sc"%dvdPlayerPlg):
				if fileExists('/usr/lib/enigma2/python/Screens/DVD.py') or fileExists('/usr/lib/enigma2/python/Screens/DVD.pyc'):
					from Screens.DVD import ChapterZap
					self.session.openWithCallback(self.numberEntered, ChapterZap, "0")
				else:
					from Plugins.Extensions.DVDPlayer.plugin import ChapterZap
					self.session.openWithCallback(self.numberEntered, ChapterZap, "0")

	# InfoBarMenu Key_Menu
	#def mainMenu(self):
	#	self.enterDVDMenu()

	# InfoBarShowHide Key_Ok
	def toggleShow(self):
		### Cover anzeige
		self.LongButtonPressed = False

		if not self.in_menu:
			### Cover anzeige
			#self.showCover()
			# Call baseclass function
			InfoBarShowHide.toggleShow(self)

	# InfoBarSeek
#	def showAfterSeek(self):
#		if self.in_menu and self.dvdScreen:
#			self.hideAfterResume()
#			self.dvdScreen.show()
#		else:
#			InfoBarSeek.showAfterSeek(self)

	#def __evEOF(self):
	#	print "EMC PLAYER __evEOF"

	def doEofInternal(self, playing):
		print("EMC PLAYER doEofInternal")
		if not self.execing:
			return
		if not playing:
			return

		if self.in_menu:
			self.hide()
		val = config.EMC.record_eof_zap.value
		if val == "0" or val == "1" and self.service:
			#TEST
			# get path from iPlayableService
			#ref = self.session.nav.getCurrentlyPlayingServiceReference()
			#if ref and self.service and ref.getPath() == self.service.getPath():
			record = getRecording(self.service.getPath())
			if record:
				begin, end, service = record

				# Seek play position and record length differ about one second
				#last = ( time() - begin ) * 90000
				#if last < (self.getSeekPlayPosition() + 1*90000):

				# Zap to new channel
				self.lastservice = service
				self.service = None
				self.closeAll = True
				self.leavePlayer(False)
				return

				#TEST just return and ignore if there is more to play
				#else:
				##if self.seekstate == self.SEEK_STATE_EOF:
				##	self.setSeekState(self.SEEK_STATE_PLAY)
				#	return

		if self.service.type != sidDVB:
			self.makeUpdateCutList()

		self.evEOF()

	def makeUpdateCutList(self):
		if self.getSeekPlayPosition() == 0:
			if self.realSeekLength is not None:
				self.updateCutList( self.realSeekLength, self.realSeekLength )
			else:
				self.updateCutList( self.getSeekLength(), self.getSeekLength() )
		else:
			self.updateCutList( self.getSeekPlayPosition(), self.getSeekLength() )

	##############################################################################
	## Oozoon image specific and make now the PiPzap possible
	def up(self):
		try:
			if self.servicelist and self.servicelist.dopipzap:
				if "keep" not in config.usage.servicelist_cursor_behavior.value:
					self.servicelist.moveUp()
				self.session.execDialog(self.servicelist)
			else:
				self.showMovies()
		except:
			self.showMovies()

	def down(self):
		try:
			if self.servicelist and self.servicelist.dopipzap:
				if "keep" not in config.usage.servicelist_cursor_behavior.value:
					self.servicelist.moveDown()
				self.session.execDialog(self.servicelist)
			else:
				self.showMovies()
		except:
			self.showMovies()

	def swapPiP(self):     # this is needed for oe-images to deactivate the Pip-swapping in this first way
		pass

	##############################################################################
	## LT image specific
	def startCheckLockTimer(self):
		pass
