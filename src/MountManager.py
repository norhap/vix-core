# for localized messages
from boxbranding import getMachineBrand, getMachineName, getMachineBuild
from os import system, rename, path, mkdir, remove
from time import sleep
import re

from enigma import eTimer

from . import _
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Screens.ChoiceBox import ChoiceBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ConfigList import ConfigListScreen
from Components.config import config, getConfigListEntry, ConfigSelection, NoSave
from Components.Console import Console
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Components.Harddisk import Harddisk
from Components.SystemInfo import SystemInfo
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import SCOPE_ACTIVE_SKIN, resolveFilename, pathExists
import os

class VIXDevicesPanel(Screen):
	skin = """
	<screen position="center,center" size="640,460">
		<ePixmap pixmap="skin_default/buttons/red.png" position="25,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="175,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/yellow.png" position="325,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/blue.png" position="475,0" size="140,40" alphatest="on"/>
		<widget name="key_red" position="25,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="175,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="key_yellow" position="325,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1"/>
		<widget name="key_blue" position="475,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1"/>
		<widget source="list" render="Listbox" position="10,50" size="620,450" scrollbarMode="showOnDemand">
			<convert type="TemplatedMultiContent">
				{"template": [
				 MultiContentEntryText(pos = (90,0), size = (600,30), font=0, text = 0),
				 MultiContentEntryText(pos = (110,30), size = (600,50), font=1, flags = RT_VALIGN_TOP, text = 1),
				 MultiContentEntryPixmapAlphaBlend(pos = (0,0), size = (80,80), png = 2),
				],
				"fonts": [gFont("Regular",24),gFont("Regular",20)],
				"itemHeight":85
				}
			</convert>
		</widget>
		<widget name="lab1" zPosition="2" position="50,90" size="600,40" font="Regular;22" halign="center" transparent="1"/>
	</screen>"""

	def __init__(self, session, menu_path=""):
		Screen.__init__(self, session)
		screentitle =  _("Mount manager")
		self.menu_path = menu_path
		if config.usage.show_menupath.value == 'large':
			self.menu_path += screentitle
			title = self.menu_path
			self["menu_path_compressed"] = StaticText("")
			self.menu_path += ' / '
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			condtext = ""
			if self.menu_path and not self.menu_path.endswith(' / '):
				condtext = self.menu_path + " >"
			elif self.menu_path:
				condtext = self.menu_path[:-3] + " >"
			self["menu_path_compressed"] = StaticText(condtext)
			self.menu_path += screentitle + ' / '
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)

		self['key_red'] = Label(" ")
		self['key_green'] = Label(_("Setup mounts"))
		self['key_yellow'] = Label(_("Un-mount"))
		self['key_blue'] = Label(_("Mount"))
		self['lab1'] = Label()
		self.onChangedEntry = []
		self.list = []
		self['list'] = List(self.list)
		self["list"].onSelectionChanged.append(self.selectionChanged)
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', "MenuActions"], {'back': self.close, 'green': self.SetupMounts, 'red': self.saveMypoints, 'yellow': self.Unmount, 'blue': self.Mount, "menu": self.close})
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.updateList2)
		self.updateList()

	def createSummary(self):
		return VIXDevicesPanelSummary

	def selectionChanged(self):
		if len(self.list) == 0:
			return
		sel = self['list'].getCurrent()
		seldev = sel
		for line in sel:
			try:
				line = line.strip()
				if _('Mount: ') in line:
					if line.find('/media/hdd') < 0:
					    self["key_red"].setText(_("Use as HDD"))
				else:
					self["key_red"].setText(" ")
			except:
				pass
		if sel:
			try:
				name = str(sel[0])
				desc = str(sel[1].replace('\t', '  '))
			except:
				name = ""
				desc = ""
		else:
			name = ""
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def updateList(self, result=None, retval=None, extra_args=None):
		scanning = _("Please wait while scanning for devices...")
		self['lab1'].setText(scanning)
		self.activityTimer.start(10)

	def updateList2(self):
		self.activityTimer.stop()
		self.list = []
		list2 = []
		z = open('/proc/cmdline', 'r').read()
		f = open('/proc/partitions', 'r')
		for line in f.readlines():
			parts = line.strip().split()
			if not parts:
				continue
			device = parts[3]
			if not re.search('sd[a-z][1-9]', device) and not re.search('mmcblk[0-9]p[1-9]', device):
				continue
			if SystemInfo["HasSDmmc"] and pathExists("/dev/sda4") and re.search('sd[a][1-4]', device):
				continue
			if SystemInfo["HasMMC"] and "root=/dev/mmcblk0p1" in z and re.search('mmcblk0p1', device):
				continue
			if device in list2:
				continue
			self.buildMy_rec(device)
			list2.append(device)
		f.close()
		self['list'].list = self.list
		self['lab1'].hide()

	def buildMy_rec(self, device):
		if re.search('mmcblk[0-9]p[0-9][0-9]', device):
			device2 = re.sub('p[0-9][0-9]', '', device)
		elif re.search('mmcblk[0-9]p[0-9]', device):
			device2 = re.sub('p[0-9]', '', device)
		else:
			device2 = re.sub('[0-9]', '', device)
		devicetype = path.realpath('/sys/block/' + device2 + '/device')
		if devicetype.find('mmc') != -1 and (devicetype.find('rdb') != -1 or (devicetype.find('soc') != -1 and  getMachineBuild() not in ("h9", "i55plus", "h9combo", "u5pvr"))):
			return
		if  getMachineBuild() == 'h9combo' and "mmcblk0" in device:
			return
		if  getMachineBuild() == 'u5pvr' and "mmcblk0" in device:
			return
		d2 = device
		name = _("HARD DISK: ")
		if path.exists(resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_hdd.png")):
			mypixmap = resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_hdd.png")
		else:
			mypixmap = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_hdd.png'
		if pathExists('/sys/block/' + device2 + '/device/model'):
			model = file('/sys/block/' + device2 + '/device/model').read()
		elif pathExists('/sys/block/' + device2 + '/device/name'):
			model = file('/sys/block/' + device2 + '/device/name').read()
		model = str(model).replace('\n', '')
		des = ''
		if devicetype.find('usb') != -1:
			name = _('USB: ')
			if path.exists(resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_usb.png")):
				mypixmap = resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_usb.png")
			else:
				mypixmap = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_usb.png'
		elif devicetype.find('mmc') != -1:
			name = _('SDCARD: ')
			if path.exists(resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_sd.png")):
				mypixmap = resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_sd.png")
			else:
				mypixmap = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_sd.png'
		name += model
		# self.Console.ePopen("sfdisk -l /dev/sd? | grep swap | awk '{print $(NF-9)}' >/tmp/devices.tmp")
		# sleep(0.5)
		# f = open('/tmp/devices.tmp', 'r')
		# swapdevices = f.read()
		# f.close()
		# if path.exists('/tmp/devices.tmp'):
		# 	remove('/tmp/devices.tmp')
		# swapdevices = swapdevices.replace('\n', '')
		# swapdevices = swapdevices.split('/')
		f = open('/proc/mounts', 'r')
		d1 = _("None")
		dtype = _("unavailable")
		rw = _("None")
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				d1 = parts[1]
				dtype = parts[2]
				rw = parts[3]
				break
			# else:
			# 	if device in swapdevices:
			# 		parts = line.strip().split()
			# 		d1 = _("None")
			# 		dtype = 'swap'
			# 		rw = _("None")
			# 		break
		f.close()
		size = Harddisk(device).diskSize()

		if ((float(size) / 1024) / 1024) >= 1:
			des = _("Size: ") + str(round(((float(size) / 1024) / 1024), 2)) + _("TB")
		elif (size / 1024) >= 1:
			des = _("Size: ") + str(round((float(size) / 1024), 2)) + _("GB")
		elif size >= 1:
			des = _("Size: ") + str(size) + _("MB")
		else:
			des = _("Size: ") + _("unavailable")

		if des != '':
			if rw.startswith('rw'):
				rw = ' R/W'
			elif rw.startswith('ro'):
				rw = ' R/O'
			else:
				rw = ""
			des += '\t' + _("Mount: ") + d1 + '\n' + _("Device: ") + '/dev/' + device + '\t' + _("Type: ") + dtype + rw
			png = LoadPixmap(mypixmap)
			res = (name, des, png)
			self.list.append(res)

	def SetupMounts(self):
		self.session.openWithCallback(self.updateList, VIXDevicePanelConf, self.menu_path)

	def Mount(self):
		if len(self['list'].list) < 1: return
		sel = self['list'].getCurrent()
		if sel:
			des = sel[1]
			des = des.replace('\n', '\t')
			parts = des.strip().split('\t')
			mountp = parts[1].replace(_("Mount: "), '')
			device = parts[2].replace(_("Device: "), '')
			moremount = sel[1]
			adv_title = moremount != "" and _("Warning, this device is used for more than one mount point!\n") or ""
			if device != '':
				devicemount = device[-5:]
				curdir = '/media%s' % (devicemount)
				mountlist = [
				(_("Mount current device from the fstab"), self.MountCur3),
				(_("Mount current device to %s") % (curdir), self.MountCur2),
				(_("Mount all device from the fstab"), self.MountCur1),
				]
				self.session.openWithCallback(
				self.menuCallback,
				ChoiceBox,
				list = mountlist,
				title= adv_title + _("Select mount action for %s:") % device,
				)

	def menuCallback(self, ret = None):
		ret and ret[1]()				
			
	def MountCur3(self):
		sel = self['list'].getCurrent()
		if sel:
			parts = sel[1].split()
			self.device = parts[5]
			self.mountp = parts[3]
			des = sel[1]
			des = des.replace('\n', '\t')
			parts = des.strip().split('\t')
			device = parts[2].replace(_("Device: "), '')
			try:
				f = open('/proc/mounts', 'r')
			except IOError:
				return
			for line in f.readlines():
				if line.find(device) != -1 and '/omb' not in line:
					self.session.open(MessageBox, _("The device is already mounted!"), MessageBox.TYPE_INFO, timeout=5)
					f.close()
					return
			f.close()
			self.mbox = self.session.open(MessageBox, _("Please wait..."), MessageBox.TYPE_INFO)
			system('mount ' + device)
			self.Console = Console()
			self.Console.ePopen("/sbin/blkid | grep " + self.device, self.cur_in_fstab, [self.device, self.mountp])

	def MountCur1(self):
		if len(self['list'].list) < 1: return
		system('mount -a')
		self.updateList()

	def MountCur2(self):
		sel = self['list'].getCurrent()
		if sel:
			des = sel[1]
			des = des.replace('\n', '\t')
			parts = des.strip().split('\t')
			device = parts[2].replace(_("Device: "), '')
			try:
				f = open('/proc/mounts', 'r')
			except IOError:
				return
			for line in f.readlines():
				if line.find(device) != -1 and '/omb' not in line:
					f.close()
					self.session.open(MessageBox, _("The device is already mounted!"), MessageBox.TYPE_INFO, timeout=5)
					return
			f.close()
			if device != '':
				devicemount = device[-5:]
				mountdir = '/media/%s' % (devicemount)
				if not os.path.exists(mountdir):
					os.mkdir(mountdir, 0755)
				system ('mount ' + device + ' /media/%s' % (devicemount))
				mountok = False
				f = open('/proc/mounts', 'r')
				for line in f.readlines():
					if line.find(device) != -1 and '/omb' not in line:
						mountok = True
				f.close()
				if not mountok:
					self.session.open(MessageBox, _("The mount failed, completely restart the receiver to reassemble it, or press the green button (setup mounts) to mount as /media/hdd../media/usb..."), MessageBox.TYPE_ERROR, timeout=20)
				self.updateList()

	def cur_in_fstab(self, result = None, retval = None, extra_args = None):
		self.device = extra_args[0]
		self.mountp = extra_args[1]
		self.device_uuid_tmp = result.split('UUID=')
		if str(self.device_uuid_tmp) != "['']":
			try:
				self.device_uuid_tmp = self.device_uuid_tmp[1].replace('TYPE="ext2"','').replace('TYPE="ext3"','').replace('TYPE="ext4"','').replace('TYPE="ntfs"','').replace('TYPE="exfat"','').replace('TYPE="vfat"','').replace('"','')
				self.device_uuid_tmp = self.device_uuid_tmp.replace('\n',"")
				self.device_uuid = 'UUID=' + self.device_uuid_tmp
				system ('mount ' + self.device_uuid)
				mountok = False
				f = open('/proc/mounts', 'r')
				for line in f.readlines():
					if line.find(self.device) != -1 and '/omb' not in line:
						mountok = True
				f.close()
				if not mountok:
					self.session.open(MessageBox, _("Mount current device failed!\nMaybe this device is not spelled out in the fstab?"), MessageBox.TYPE_ERROR, timeout=8)
			except:
				pass
		if self.mbox:
			self.mbox.close()
		self.updateList()				

	def Unmount(self):
		if len(self['list'].list) < 1: return
		sel = self['list'].getCurrent()
		if sel:
			des = sel[1]
			des = des.replace('\n', '\t')
			parts = des.strip().split('\t')
			mountp = parts[1].replace(_("Mount: "), '')
			device = parts[2].replace(_("Device: "), '')
			print mountp
			if mountp == _("None"): return
			message = _("Really unmount drive ?")
			self.session.openWithCallback(self.UnmountAnswer, MessageBox, message, MessageBox.TYPE_YESNO)

	def UnmountAnswer(self, answer):
		if answer:
			sel = self['list'].getCurrent()
			if sel:
				des = sel[1]
				des = des.replace('\n', '\t')
				parts = des.strip().split('\t')
				mountp = parts[1].replace(_("Mount: "), '')
				device = parts[2].replace(_("Device: "), '')
				moremount = sel[1]
				if mountp != _("None"):
					system('umount ' + mountp)
				if moremount == "":
					system('umount ' + device)
				try:
					mounts = open("/proc/mounts")
				except IOError:
					return
				mountcheck = mounts.readlines()
				mounts.close()
				for line in mountcheck:
					#if moremount == "":
					#	parts = line.strip().split(" ")
					#	if os.path.realpath(parts[0]).startswith(device):
					#		os.self.session.open(MessageBox, _("Can't unmount partiton, make sure it is not being used for swap or record/timeshift paths!"), MessageBox.TYPE_ERROR, timeout = 6, close_on_any_key = True)
					if mountp in line and device in line and '/omb' not in line:
						parts = line.strip().split(" ")
						if parts[1] == mountp:
							self.session.open(MessageBox, _("Can't unmount partiton, make sure it is not being used for swap or record/timeshift paths!"), MessageBox.TYPE_ERROR, timeout = 5, close_on_any_key = True)
							break
				self.updateList()

	def saveMypoints(self):
		if len(self['list'].list) < 1: return
		sel = self['list'].getCurrent()
		if sel:
			des = sel[1]
			des = des.replace('\n', '\t')
			parts = des.strip().split('\t')
			device = parts[2].replace(_("Device: "), '')
			moremount = sel[1]
			adv_title = moremount != "" and _("Warning, this device is used for more than one mount point!\n") or ""
			message = adv_title + _("Really use and mount %s as HDD ?") % device
			self.session.openWithCallback(self.saveMypointAnswer, MessageBox, message, MessageBox.TYPE_YESNO)

	def saveMypointAnswer(self, answer):
		if answer:
			sel = self['list'].getCurrent()
			if sel:
				des = sel[1]
				des = des.replace('\n', '\t')
				parts = des.strip().split('\t')
				self.mountp = parts[1].replace(_("Mount: "), '')
				self.device = parts[2].replace(_("Device: "), '')
				if self.mountp.find('/media/hdd') < 0:
					pass
				else:
					self.session.open(MessageBox, _("This Device is already mounted as HDD."), MessageBox.TYPE_INFO, timeout = 6, close_on_any_key = True)
					return
				system('[ -e /media/hdd/swapfile ] && swapoff /media/hdd/swapfile')
				#system('[ -e /etc/init.d/transmissiond ] && /etc/init.d/transmissiond stop')
				system('umount /media/hdd')
				try:
					f = open('/proc/mounts', 'r')
				except IOError:
					return
				for line in f.readlines():
					if '/media/hdd' in line:
						f.close()
						self.session.open(MessageBox, _("Cannot unmount from the previous device from /media/hdd.\nA record in progress, timeshift or some external tools (like samba, nfsd,transmission and etc) may cause this problem.\nPlease stop this actions/applications and try again!"), MessageBox.TYPE_ERROR)
						return
					else:
						pass
				f.close()
				if self.mountp.find('/media/hdd') < 0:
					if self.mountp != _("None"):
						system('umount ' + self.mountp)
					system('umount ' + self.device)
					self.Console.ePopen("/sbin/blkid | grep " + self.device, self.add_fstab, [self.device, self.mountp])

	def add_fstab(self, result=None, retval=None, extra_args=None):
		self.device = extra_args[0]
		self.mountp = extra_args[1]
		self.device_uuid = 'UUID=' + result.split('UUID=')[1].split(' ')[0].replace('"', '')
		if not path.exists(self.mountp):
			mkdir(self.mountp, 0755)
		file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if '/media/hdd' not in l])
		rename('/etc/fstab.tmp', '/etc/fstab')
		file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if self.device not in l])
		rename('/etc/fstab.tmp', '/etc/fstab')
		file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if self.device_uuid not in l])
		rename('/etc/fstab.tmp', '/etc/fstab')
		out = open('/etc/fstab', 'a')
		line = self.device_uuid + '\t/media/hdd\tauto\tdefaults\t0 0\n'
		out.write(line)
		out.close()
		self.Console.ePopen('mount -a', self.updateList)

	def restBo(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 2)
		else:
			self.updateList()
			self.selectionChanged()

class VIXDevicePanelConf(Screen, ConfigListScreen):
	skin = """
	<screen position="center,center" size="640,460">
		<ePixmap pixmap="skin_default/buttons/red.png" position="25,0" size="140,40" alphatest="on"/>
		<ePixmap pixmap="skin_default/buttons/green.png" position="175,0" size="140,40" alphatest="on"/>
		<widget name="key_red" position="25,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1"/>
		<widget name="key_green" position="175,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1"/>
		<widget name="config" position="30,60" size="580,275" scrollbarMode="showOnDemand"/>
		<widget name="Linconn" position="30,375" size="580,20" font="Regular;18" halign="center" valign="center" backgroundColor="#9f1313"/>
	</screen>"""

	def __init__(self, session, menu_path):
		Screen.__init__(self, session)
		self.list = []
		ConfigListScreen.__init__(self, self.list)
		screentitle =  _("Choose where to mount your devices to:")
		if config.usage.show_menupath.value == 'large':
			menu_path += screentitle
			title = menu_path
			self["menu_path_compressed"] = StaticText("")
		elif config.usage.show_menupath.value == 'small':
			title = screentitle
			self["menu_path_compressed"] = StaticText(menu_path + " >" if not menu_path.endswith(' / ') else menu_path[:-3] + " >" or "")
		else:
			title = screentitle
			self["menu_path_compressed"] = StaticText("")
		Screen.setTitle(self, title)

		self['key_green'] = Label(_("Save"))
		self['key_red'] = Label(_("Cancel"))
		self['Linconn'] = Label()
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'green': self.saveMypoints, 'red': self.close, 'back': self.close})
		self.Console = Console()
		self.activityTimer = eTimer()
		self.activityTimer.timeout.get().append(self.updateList2)
		self.updateList()

	def updateList(self, result=None, retval=None, extra_args=None):
		scanning = _("Please wait while scanning your %s %s devices...") % (getMachineBrand(), getMachineName())
		self['Linconn'].setText(scanning)
		self.activityTimer.start(10)

	def updateList2(self):
		self.activityTimer.stop()
		self.list = []
		list2 = []
		# self.Console.ePopen("sfdisk -l /dev/sd? | grep swap | awk '{print $(NF-9)}' >/tmp/devices.tmp")
		# sleep(0.5)
		# swapdevices = ''
		# if path.exists('/tmp/devices.tmp'):
		# 	f = open('/tmp/devices.tmp', 'r')
		# 	swapdevices = f.read()
		# 	f.close()
		# 	remove('/tmp/devices.tmp')
		# swapdevices = swapdevices.replace('\n', '')
		# swapdevices = swapdevices.split('/')
		z = open('/proc/cmdline', 'r').read()
		f = open('/proc/partitions', 'r')
		for line in f.readlines():
			parts = line.strip().split()
			if not parts:
				continue
			device = parts[3]
			if not re.search('sd[a-z][1-9]', device) and not re.search('mmcblk[0-9]p[1-9]', device):
				continue
			if SystemInfo["HasSDmmc"] and pathExists("/dev/sda4") and re.search('sd[a][1-4]', device):
				continue
			if SystemInfo["HasMMC"] and "root=/dev/mmcblk0p1" in z and re.search('mmcblk0p1', device):
				continue
			if device in list2:
				continue
			# if device in swapdevices:
			# 	continue
			self.buildMy_rec(device)
			list2.append(device)
		f.close()
		self['config'].list = self.list
		self['config'].l.setList(self.list)
		self['Linconn'].hide()

	def buildMy_rec(self, device):
		if re.search('mmcblk[0-9]p[0-9][0-9]', device):
			device2 = re.sub('p[0-9][0-9]', '', device)
		elif re.search('mmcblk[0-9]p[0-9]', device):
			device2 = re.sub('p[0-9]', '', device)
		else:
			device2 = re.sub('[0-9]', '', device)
		devicetype = path.realpath('/sys/block/' + device2 + '/device')
		if devicetype.find('mmc') != -1 and (devicetype.find('rdb') != -1 or (devicetype.find('soc') != -1 and  getMachineBuild() not in ("h9", "i55plus", "h9combo", "u5pvr"))):
			return
		if  getMachineBuild() == 'h9combo' and "mmcblk0" in device:
			return
		if  getMachineBuild() == 'u5pvr' and "mmcblk0" in device:
			return
		d2 = device
		name = _("HARD DISK: ")
		if path.exists(resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_hdd.png")):
			mypixmap = resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_hdd.png")
		else:
			mypixmap = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_hdd.png'
		if pathExists('/sys/block/' + device2 + '/device/model'):
			model = file('/sys/block/' + device2 + '/device/model').read()
		elif pathExists('/sys/block/' + device2 + '/device/name'):
			model = file('/sys/block/' + device2 + '/device/name').read()
		model = str(model).replace('\n', '')
		des = ''
		if devicetype.find('usb') != -1:
			name = _('USB: ')
			if path.exists(resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_usb.png")):
				mypixmap = resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_usb.png")
			else:
				mypixmap = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_usb.png'
		elif devicetype.find('mmc') != -1:
			name = _('SDCARD: ')
			if path.exists(resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_sd.png")):
				mypixmap = resolveFilename(SCOPE_ACTIVE_SKIN, "vixcore/dev_sd.png")
			else:
				mypixmap = '/usr/lib/enigma2/python/Plugins/SystemPlugins/ViX/images/dev_sd.png'
		name += model
		d1 = _("None")
		dtype = _("unavailable")
		f = open('/proc/mounts', 'r')
		for line in f.readlines():
			if line.find(device) != -1:
				parts = line.strip().split()
				d1 = parts[1]
				dtype = parts[2]
				break
		f.close()

		size = Harddisk(device).diskSize()
		if ((float(size) / 1024) / 1024) >= 1:
			des = _("Size: ") + str(round(((float(size) / 1024) / 1024), 2)) + _("TB")
		elif (size / 1024) >= 1:
			des = _("Size: ") + str(round((float(size) / 1024), 2)) + _("GB")
		elif size >= 1:
			des = _("Size: ") + str(size) + _("MB")
		else:
			des = _("Size: ") + _("unavailable")

		item = NoSave(ConfigSelection(default='/media/' + device, choices=[('/media/' + device, '/media/' + device),
																		   ('/media/hdd', '/media/hdd'),
																		   ('/media/hdd2', '/media/hdd2'),
																		   ('/media/hdd3', '/media/hdd3'),
																		   ('/media/usb', '/media/usb'),
																		   ('/media/usb2', '/media/usb2'),
																		   ('/media/usb3', '/media/usb3'),
																		   ('/media/sdcard', '/media/sdcard')]))
		if dtype == 'Linux':
			dtype = 'ext4'
		else:
			dtype = 'auto'
		item.value = d1.strip()
		text = name + ' ' + des + ' /dev/' + device
		res = getConfigListEntry(text, item, device, dtype)

		if des != '' and self.list.append(res):
			pass

	def saveMypoints(self):
		mycheck = False
		for x in self['config'].list:
			self.device = x[2]
			self.mountp = x[1].value
			self.type = x[3]
			self.Console.ePopen('umount ' + self.device)
			self.Console.ePopen("/sbin/blkid | grep " + self.device + " && opkg list-installed ntfs-3g", self.add_fstab, [self.device, self.mountp])
		message = _("Updating mount locations...")
		ybox = self.session.openWithCallback(self.delay, MessageBox, message, type=MessageBox.TYPE_INFO, timeout=5, enable_input=False)
		ybox.setTitle(_("Please wait."))

	def delay(self, val):
		message = _("The changes need a system restart to take effect.\nRestart your %s %s now?") % (getMachineBrand(), getMachineName())
		ybox = self.session.openWithCallback(self.restartBox, MessageBox, message, MessageBox.TYPE_YESNO)
		ybox.setTitle(_("Restart %s %s.") % (getMachineBrand(), getMachineName()))

	def add_fstab(self, result=None, retval=None, extra_args=None):
		# print '[MountManager] RESULT:', result
		if result:
			self.device = extra_args[0]
			self.mountp = extra_args[1]
			self.device_uuid = 'UUID=' + result.split('UUID=')[1].split(' ')[0].replace('"', '')
			self.device_type = result.split('TYPE=')[1].split(' ')[0].replace('"', '')

			if self.device_type.startswith('ext'):
				self.device_type = 'auto'
			elif self.device_type.startswith('ntfs') and result.find('ntfs-3g') != -1:
				self.device_type = 'ntfs-3g'
			elif self.device_type.startswith('ntfs') and result.find('ntfs-3g') == -1:
				self.device_type = 'ntfs'

			if not path.exists(self.mountp):
				mkdir(self.mountp, 0755)
			file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if self.device not in l])
			rename('/etc/fstab.tmp', '/etc/fstab')
			file('/etc/fstab.tmp', 'w').writelines([l for l in file('/etc/fstab').readlines() if self.device_uuid not in l])
			rename('/etc/fstab.tmp', '/etc/fstab')
			out = open('/etc/fstab', 'a')
			line = self.device_uuid + '\t' + self.mountp + '\t' + self.device_type + '\tdefaults\t0 0\n'
			out.write(line)
			out.close()

	def restartBox(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 2)
		else:
			self.close()

class VIXDevicesPanelSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent=parent)
		self["entry"] = StaticText("")
		self["desc"] = StaticText("")
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)
		self.parent.selectionChanged()

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self, name, desc):
		self["entry"].text = name
		self["desc"].text = desc
