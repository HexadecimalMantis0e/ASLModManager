import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import struct
import io
import hashlib
import configparser


def getFileSize(fp):
    fp.seek(0x00, os.SEEK_END)
    fileSize = fp.tell()
    fp.seek(0x00, os.SEEK_SET)
    return fileSize

class ASLDirEntry:
    def __init__(self, name, size, address):
        self.name = name
        self.size = size
        self.address = address

class ASLDir:
    def __init__(self):
        self.count = 0x00
        self.entries = []

    def readDir(self, fp):
        self.count = struct.unpack("<I", fp.read(4))[0]

        for i in range(0, self.count):
            name = fp.read(0x40).decode().replace('\0', '')
            size = struct.unpack("<I", fp.read(4))[0]
            address = struct.unpack("<I", fp.read(4))[0]
            self.entries.append(ASLDirEntry(name, size, address))

    def writeDir(self, fp):
        fp.write(struct.pack("<I", self.count))

        for i in range(0, len(self.entries)):
            fp.write(self.entries[i].name.encode())
            fp.write(bytearray([0x00]) * (0x40 - len(self.entries[i].name)))
            fp.write(struct.pack("<I", self.entries[i].size))
            fp.write(struct.pack("<I", self.entries[i].address))

    def addEntry(self, fp, wad):
        self.count += 1

        if len(self.entries) != 0:
            size = self.entries[len(self.entries) - 1].size
            address = self.entries[len(self.entries) - 1].address
            address += size
            file = wad.files[len(wad.files) - 1]
            header = file.read(4)

            if header != "BIGB".encode() and header != 0x00.to_bytes(4, byteorder = "little"):
                paddingSize = 0x800 - (size % 0x800)
                address += paddingSize

            file.seek(0x00, os.SEEK_SET)
        else:
            address = 0x00

        self.entries.append(ASLDirEntry(os.path.basename(fp.name), getFileSize(fp), address))

    def replaceEntry(self, fp, wad, index):
        size = getFileSize(fp)
        oldSize = self.entries[index].size
        self.entries[index].name = os.path.basename(fp.name)
        self.entries[index].size = size
        header = fp.read(4)

        if header != "BIGB".encode() and header != 0x00.to_bytes(4, byteorder = "little"):
            paddingSize = 0x800 - (size % 0x800)
            size += paddingSize

        fp.seek(0x00, os.SEEK_SET)

        file = wad.files[index]
        header = file.read(4)

        if header != "BIGB".encode() and header != 0x00.to_bytes(4, byteorder = "little"):
            paddingSize = 0x800 - (oldSize % 0x800)
            oldSize += paddingSize

        file.seek(0x00, os.SEEK_SET)

        for entry in self.entries[index + 1:]:
            entry.address += (size - oldSize)

class ASLWad:
    def __init__(self):
        self.files = []

    def readWad(self, fp, dir):
        for entry in dir.entries:
            fp.seek(entry.address, os.SEEK_SET)
            file = io.BytesIO(fp.read(entry.size))
            self.files.append(file)

    def writeWad(self, fp):
        for file in self.files:
            fp.write(file.getbuffer())
            header = file.read(4)

            if header != "BIGB".encode() and header != 0x00.to_bytes(4, byteorder = "little"):
                paddingSize = 0x800 - (file.getbuffer().nbytes % 0x800)
                fp.write(bytearray([0x00]) * paddingSize)

            file.seek(0x00, os.SEEK_SET)

    def addFile(self, fp):
        file = io.BytesIO(fp.read(getFileSize(fp)))
        self.files.append(file)

    def replaceFile(self, fp, index):
        self.files[index] = io.BytesIO(fp.read(getFileSize(fp)))

class ASLGame:
    def __init__(self, dir, wad):
        self.dir = dir
        self.wad = wad

    def readGame(self, fpDir, fpWad):
        self.dir.readDir(fpDir)
        self.wad.readWad(fpWad, self.dir)

    def writeGame(self, fpDir, fpWad):
        self.dir.writeDir(fpDir)
        self.wad.writeWad(fpWad)

    def addFile(self, fp):
        self.dir.addEntry(fp, self.wad)
        self.wad.addFile(fp)

    def replaceFile(self, fp, index):
        self.dir.replaceEntry(fp, self.wad, index)
        self.wad.replaceFile(fp, index)

class ASLModManager:
    def __init__(self, window):
        window.title("ASLModManager")
        self.menuBar = tk.Menu(window)
        self.fileMenu = tk.Menu(self.menuBar, tearoff = 0)
        self.openMenu = tk.Menu(self.fileMenu, tearoff = 0)
        self.openMenu.add_command(label = "Files", command = lambda: self.openGame())
        self.openMenu.add_command(label = "Directory", command = lambda: self.openGameDirectory())
        self.fileMenu.add_cascade(label = "Open Game", menu = self.openMenu)
        self.fileMenu.add_command(label = "Close Game", state = "disabled", command = lambda: self.closeGame())
        self.extractMenu = tk.Menu(self.fileMenu, tearoff = 0)
        self.extractMenu.add_command(label = "File", command = lambda: self.extractFile())
        self.extractMenu.add_command(label = "Game", command = lambda: self.extractGame())
        self.fileMenu.add_cascade(label = "Extract", state = "disabled", menu = self.extractMenu)
        self.saveMenu = tk.Menu(self.fileMenu, tearoff = 0)
        self.saveMenu.add_command(label = "Game", state = "disabled", command = lambda: self.saveGame())
        self.saveMenu.add_command(label = "Settings", command = lambda: self.saveSettings())
        self.fileMenu.add_cascade(label = "Save", menu = self.saveMenu)
        self.menuBar.add_cascade(label = "File", menu = self.fileMenu)
        self.editMenu = tk.Menu(self.menuBar, tearoff = 0)
        self.editMenu.add_command(label = "Add File", state = "disabled", command = lambda: self.addFile())
        self.editMenu.add_command(label = "Add Directory", state = "disabled", command = lambda: self.addDirectory())
        self.menuBar.add_cascade(label = "Edit", menu = self.editMenu)
        window.config(menu = self.menuBar)
        self.tabControl = ttk.Notebook(window)
        self.gameTab = ttk.Frame(self.tabControl)
        self.settingsTab = ttk.Frame(self.tabControl)
        self.tabControl.add(self.gameTab, text = "Game")
        self.tabControl.add(self.settingsTab, text = "Settings")
        self.tabControl.grid(row = 0, column = 0, sticky = 'W')
        self.outerDir = ttk.LabelFrame(self.gameTab, text = "Directory")
        self.outerDir.grid(row = 1, column = 0, rowspan = 2, padx = 8, pady = 8, sticky = "NS")
        self.outerDir.grid_rowconfigure(0, weight = 1)
        self.outerDir.grid_columnconfigure(0, weight = 1)
        self.innerDir = ttk.Frame(self.outerDir)
        self.innerDir.grid(row = 0, column = 0, padx = 4, pady = 4, sticky = "NSEW")
        self.innerDir.grid_rowconfigure(0, weight = 1)
        self.listBox = tk.Listbox(self.innerDir)
        self.listBox.bind("<Double-1>", self.selectFileEvent)
        self.listBox.grid(row = 0, column = 0, sticky = "NS")
        self.scrollBar = tk.Scrollbar(self.innerDir)
        self.scrollBar.config(command = self.listBox.yview)
        self.scrollBar.grid(row = 0, column = 1, sticky = "NS")
        self.listBox.config(yscrollcommand = self.scrollBar.set)
        self.outerFileInfo = ttk.LabelFrame(self.gameTab, text = "File Info")
        self.outerFileInfo.grid(row = 1, column = 1, padx = 8, pady = 8, sticky = "NSEW")
        self.outerFileInfo.grid_rowconfigure(0, weight = 1)
        self.outerFileInfo.grid_columnconfigure(0, weight = 1)
        self.innerFileInfo = ttk.Frame(self.outerFileInfo)
        self.innerFileInfo.grid(row = 0, column = 0, padx = 4, pady = 4, sticky = "NSEW")
        self.innerFileInfo.grid_columnconfigure(0, weight = 1)
        self.typeLabel = ttk.Label(self.innerFileInfo, text = "Type:", state = "disabled")
        self.typeLabel.grid(row = 0, column = 0, pady = (0, 2), sticky = 'W')
        self.typeEntryText = tk.StringVar()
        self.typeEntry = ttk.Entry(self.innerFileInfo, textvariable = self.typeEntryText, state = "disabled", width = 16)
        self.typeEntry.bind("<Key>", lambda a: "break")
        self.typeEntry.grid(row = 0, column = 1, pady = (0, 2))
        self.sizeLabel = ttk.Label(self.innerFileInfo, text = "Size:", state = "disabled")
        self.sizeLabel.grid(row = 1, column = 0, pady = 2, sticky = 'W')
        self.sizeEntryText = tk.StringVar()
        self.sizeEntry = ttk.Entry(self.innerFileInfo, textvariable = self.sizeEntryText, state = "disabled", width = 16)
        self.sizeEntry.bind("<Key>", lambda a: "break")
        self.sizeEntry.grid(row = 1, column = 1, pady = 2)
        self.addressLabel = ttk.Label(self.innerFileInfo, text = "Address:", state = "disabled")
        self.addressLabel.grid(row = 2, column = 0, pady = 2, sticky = 'W')
        self.addressEntryText = tk.StringVar()
        self.addressEntry = ttk.Entry(self.innerFileInfo, textvariable = self.addressEntryText, state = "disabled", width = 16)
        self.addressEntry.bind("<Key>", lambda a: "break")
        self.addressEntry.grid(row = 2, column = 1, pady = 2)
        self.statusLabel = ttk.Label(self.innerFileInfo, text = "Status:", state = "disabled")
        self.statusLabel.grid(row = 3, column = 0, pady = (2, 0), sticky = 'W')
        self.statusEntryText = tk.StringVar()
        self.statusEntry = ttk.Entry(self.innerFileInfo, textvariable = self.statusEntryText, state = "disabled", width = 16)
        self.statusEntry.bind("<Key>", lambda a: "break")
        self.statusEntry.grid(row = 3, column = 1, pady = (2, 0))
        self.outerWadInfo = ttk.LabelFrame(self.gameTab, text = "Wad Info")
        self.outerWadInfo.grid(row = 2, column = 1, padx = 8, pady = 8, sticky = "NSEW")
        self.outerWadInfo.grid_rowconfigure(0, weight = 1)
        self.outerWadInfo.grid_columnconfigure(0, weight = 1)
        self.innerWadInfo = ttk.Frame(self.outerWadInfo)
        self.innerWadInfo.grid(row = 0, column = 0, padx = 4, pady = 4, sticky = "NSEW")
        self.innerWadInfo.grid_columnconfigure(0, weight = 1)
        self.versionLabel = ttk.Label(self.innerWadInfo, text = "Version:", state = "disabled")
        self.versionLabel.grid(row = 0, column = 0, pady = (0, 2), sticky = 'W')
        self.versionEntryText = tk.StringVar()
        self.versionEntry = ttk.Entry(self.innerWadInfo, textvariable = self.versionEntryText, state = "disabled", width = 16)
        self.versionEntry.bind("<Key>", lambda a: "break")
        self.versionEntry.grid(row = 0, column = 1, pady = (0, 2))
        self.descriptionLabel = ttk.Label(self.innerWadInfo, text = "Description:", state = "disabled")
        self.descriptionLabel.grid(row = 1, column = 0, pady = 2, sticky = 'W')
        self.descriptionEntryText = tk.StringVar()
        self.descriptionEntry = ttk.Entry(self.innerWadInfo, textvariable = self.descriptionEntryText, state = "disabled", width = 16)
        self.descriptionEntry.bind("<Key>", lambda a: "break")
        self.descriptionEntry.grid(row = 1, column = 1, pady = 2)
        self.signatureLabel = ttk.Label(self.innerWadInfo, text = "Signature:", state = "disabled")
        self.signatureLabel.grid(row = 2, column = 0, pady = 2, sticky = 'W')
        self.signatureEntryText = tk.StringVar()
        self.signatureEntry = ttk.Entry(self.innerWadInfo, textvariable = self.signatureEntryText, state = "disabled", width = 16)
        self.signatureEntry.bind("<Key>", lambda a: "break")
        self.signatureEntry.grid(row = 2, column = 1, pady = 2)
        self.argumentsLabel = ttk.Label(self.innerWadInfo, text = "Arguments:", state = "disabled")
        self.argumentsLabel.grid(row = 3, column = 0, pady = (2, 0), sticky = 'W')
        self.argumentsEntryText = tk.StringVar()
        self.argumentsEntry = ttk.Entry(self.innerWadInfo, textvariable = self.argumentsEntryText, state = "disabled", width = 16)
        self.argumentsEntry.bind("<Key>", lambda a: "break")
        self.argumentsEntry.grid(row = 3, column = 1, pady = (2, 0))
        self.outerWadSettings = ttk.LabelFrame(self.settingsTab, text = "Wad Settings")
        self.outerWadSettings.grid(row = 1, column = 0, padx = 8, pady = 8, sticky = "NSEW")
        self.outerWadSettings.grid_rowconfigure(0, weight = 1)
        self.outerWadSettings.grid_columnconfigure(0, weight = 1)
        self.innerWadSettings = ttk.Frame(self.outerWadSettings)
        self.innerWadSettings.grid(row = 0, column = 0, padx = 4, pady = 4, sticky = "NSEW")
        self.hvState = tk.IntVar()
        self.hvCheckBox = ttk.Checkbutton(self.innerWadSettings, text = "Hex Version", variable = self.hvState)
        self.hvCheckBox.grid(row = 0, column = 0, sticky = 'W')
        self.avState = tk.IntVar()
        self.avCheckBox = ttk.Checkbutton(self.innerWadSettings, text = "Auto Version", variable = self.avState)
        self.avCheckBox.grid(row = 1, column = 0, sticky = 'W')
        self.dvLabel = ttk.Label(self.innerWadSettings, text = "Default Version:")
        self.dvLabel.grid(row = 2, column = 0, sticky = 'W')
        self.dvEntryText = tk.StringVar()
        self.dvEntry = ttk.Entry(self.innerWadSettings, textvariable = self.dvEntryText, width = 16)
        self.dvEntry.grid(row = 2, column = 1)
        self.loadSettings()

    def clearGame(self):
        self.game = None
        self.listBox.delete(0, "end")

    def clearEntries(self, option):
        if option == 0:
            self.typeEntry.delete(0, "end")
            self.sizeEntry.delete(0, "end")
            self.addressEntry.delete(0, "end")
            self.statusEntry.delete(0, "end")
        elif option == 1:
            self.versionEntry.delete(0, "end")
            self.descriptionEntry.delete(0, "end")
            self.signatureEntry.delete(0, "end")
            self.argumentsEntry.delete(0, "end")
        elif option == 2:
            self.typeEntry.delete(0, "end")
            self.sizeEntry.delete(0, "end")
            self.addressEntry.delete(0, "end")
            self.statusEntry.delete(0, "end")
            self.versionEntry.delete(0, "end")
            self.descriptionEntry.delete(0, "end")
            self.signatureEntry.delete(0, "end")
            self.argumentsEntry.delete(0, "end")

    def setMenuStates(self, widgetState):
        self.fileMenu.entryconfig("Close Game", state = widgetState)
        self.fileMenu.entryconfig("Extract", state = widgetState)
        self.saveMenu.entryconfig("Game", state = widgetState)
        self.editMenu.entryconfig("Add File", state = widgetState)
        self.editMenu.entryconfig("Add Directory", state = widgetState)

    def setFrameStates(self, widgetState, option):
        if option == 0:
            for child in self.innerFileInfo.winfo_children():
                child.configure(state = widgetState)
        elif option == 1:
            for child in self.innerWadInfo.winfo_children():
                child.configure(state = widgetState)
        elif option == 2:
            for child in self.innerWadSettings.winfo_children():
                child.configure(state = widgetState)
        elif option == 3:
            for child in self.innerFileInfo.winfo_children():
                child.configure(state = widgetState)

            for child in self.innerWadInfo.winfo_children():
                child.configure(state = widgetState)

    def closeGame(self):
        self.clearGame()
        self.clearEntries(2)
        self.setMenuStates("disabled")
        self.setFrameStates("normal", 2)
        self.setFrameStates("disabled", 3)

    def validateVersion(self):
        defaultVersion = self.dvEntryText.get()

        if defaultVersion.isdigit() and int(defaultVersion) < 256:
            return True
        else:
            msgBox = messagebox.showerror("Error", "Invalid version!")
            return False

    def filterDirectory(self, dirName):
        dirList = []

        for fileName in os.listdir(dirName):
            if not os.path.isdir(os.path.join(dirName, fileName)):
                dirList.append(fileName)
        return dirList

    def checkDirectory(self, fileList):
        if len(fileList) != 0:
            return True
        else:
            msgBox = messagebox.showerror("Error", "Directory contains no files!")
            return False

    def checkFilesConfig(self):
        if os.path.exists("Files.ini"):
            return True
        else:
            msgBox = messagebox.showerror("Error", "Files.ini not found!")
            self.closeGame()
            return False

    def writeSettings(self, parser, hvState, avState, dvState):
        parser.add_section("Settings")
        parser.set("Settings", "hexVersion", hvState)
        parser.set("Settings", "autoVersion", avState)
        parser.set("Settings", "defaultVersion", dvState)
        f = open("Settings.ini", 'w')
        parser.write(f)
        f.close()

    def loadSettings(self):
        configPath = "Settings.ini"
        config = configparser.ConfigParser()

        if not os.path.exists(configPath):
            self.writeSettings(config, "False", "False", "116")

        config.read(configPath)

        if config.getboolean("Settings", "hexVersion"):
            self.hvState.set(1)
        else:
            self.hvState.set(0)

        if config.getboolean("Settings", "autoVersion"):
            self.avState.set(1)
        else:
            self.avState.set(0)

        self.dvEntryText.set(config.getint("Settings", "defaultVersion"))

    def saveSettings(self):
        config = configparser.ConfigParser()

        if self.validateVersion():
            self.writeSettings(config, str(bool(self.hvState.get())), str(bool(self.avState.get())), self.dvEntryText.get())
            self.loadSettings()
            msgBox = messagebox.showinfo("Info", "Settings saved successfully.")

    def initUI(self):
        self.setMenuStates("active")
        self.setFrameStates("disabled", 2)
        self.listBox.select_set(0)
        self.listBox.event_generate("<<ListboxSelect>>")
        self.selectFile()

    def openGame(self):
        dirPath = filedialog.askopenfilename(filetypes = (("ASL DIR", "*.DIR"), ("All Files", "*.*")))

        if dirPath:
            wadPath = filedialog.askopenfilename(filetypes = (("ASL WAD", "*.WAD"), ("All Files", "*.*")))

            if wadPath:
                fpDir = open(dirPath, "rb")
                fpWad = open(wadPath, "rb")
                self.dirName = os.path.basename(dirPath)
                self.wadName = os.path.basename(wadPath)
                self.loadGame(fpDir, fpWad)
                fpDir.close()
                fpWad.close()

    def loadGame(self, dirPointer, wadPointer):
        if self.validateVersion():
            self.clearGame()
            self.game = ASLGame(ASLDir(), ASLWad())
            self.game.readGame(dirPointer, wadPointer)
            configPath = "Files.ini"
            writeHash = False
            config = configparser.ConfigParser()

            if not os.path.exists(configPath):
                config.add_section("Files")
                f = open(configPath, 'w')
                writeHash = True

            for i in range(0, self.game.dir.count):
                self.listBox.insert(i, self.game.dir.entries[i].name)
                self.loadFile(i, config, writeHash)

            if writeHash:
                config.write(f)
                f.close()

            self.initUI()

    def openGameDirectory(self):
        dirName = filedialog.askdirectory()

        if dirName:
            dirList = self.filterDirectory(dirName)

            if self.checkDirectory(dirList):
                self.dirName = os.path.basename(dirName) + ".DIR"
                self.wadName = os.path.basename(dirName) + ".WAD"
                self.loadGameDirectory(dirName, dirList)

    def loadGameDirectory(self, dirName, directory):
        if self.validateVersion():
            self.clearGame()
            self.game = ASLGame(ASLDir(), ASLWad())
            configPath = "Files.ini"
            writeHash = False
            config = configparser.ConfigParser()

            if not os.path.exists(configPath):
                config.add_section("Files")
                f = open(configPath, 'w')
                writeHash = True

            for i in range(0, len(directory)):
                fp = open(os.path.join(dirName, directory[i]), "rb")
                self.game.addFile(fp)
                fp.close()
                self.listBox.insert(i, directory[i])
                self.loadFile(i, config, writeHash)

            if writeHash:
                config.write(f)
                f.close()

            self.initUI()

    def calculateMd5(self, fileBytes):
        md5 = hashlib.md5()
        blockSize = 128 * md5.block_size
        fileChunk = fileBytes.read(blockSize)

        while fileChunk:
            md5.update(fileChunk)
            fileChunk = fileBytes.read(blockSize)

        md5Hash = md5.hexdigest()
        fileBytes.seek(0x00, os.SEEK_SET)
        return md5Hash

    def loadFile(self, index, parser, writeHash):
        avFlag = False
        currentFile = self.game.wad.files[index]
        currentName = self.game.dir.entries[index].name

        if writeHash:
            currentMd5 = self.calculateMd5(currentFile)
            parser.set("Files", currentName, str(currentMd5))

        header = currentFile.read(0x04)

        if header == "BIGB".encode():
            currentFile.seek(0x08, os.SEEK_SET)
            wadVersion = struct.unpack('B', currentFile.read(1))[0]

            if wadVersion != int(self.dvEntryText.get()) and self.avState.get() != 1:
                self.listBox.itemconfig(index, {"bg": "orange"})
            else:
                self.listBox.itemconfig(index, {"bg": "white"})

                if self.avState.get() == 1:
                    currentFile.seek(0x08, os.SEEK_SET)
                    currentFile.write(struct.pack('B', int(self.dvEntryText.get())))
                    avFlag = True

        currentFile.seek(0x00, os.SEEK_SET)

        if not writeHash or avFlag:
            currentMd5 = self.calculateMd5(currentFile)
            parser.read("Files.ini")

            try:
                storedMd5 = parser.get("Files", currentName)

                if currentMd5 != storedMd5:
                    self.listBox.itemconfig(index, {"fg": "green"})
                else:
                    self.listBox.itemconfig(index, {"fg": "black"})
            except configparser.NoOptionError:
                self.listBox.itemconfig(index, {"fg": "green"})

    def selectFile(self):
        config = configparser.ConfigParser()
        fileIndex = self.listBox.curselection()

        if fileIndex:
            fileIndex = fileIndex[0]
            self.currentFileName = self.game.dir.entries[fileIndex].name
            self.currentFile = self.game.wad.files[fileIndex]
            self.sizeEntryText.set(hex(self.game.dir.entries[fileIndex].size))
            self.addressEntryText.set(hex(self.game.dir.entries[fileIndex].address))
            header = self.currentFile.read(4)
            self.setFrameStates("normal", 0)

            if header == "BIGB".encode():
                self.setFrameStates("normal", 1)
                self.typeEntryText.set("Strat Wad")
                self.currentFile.seek(0x08, os.SEEK_SET)
                wadVersion = struct.unpack('I', self.currentFile.read(4))[0]

                if self.hvState.get() == 1:
                    self.versionEntryText.set(hex(wadVersion))
                else:
                    self.versionEntryText.set(wadVersion)

                self.currentFile.seek(0x10, os.SEEK_SET)
                description = self.currentFile.read(0x40).decode().replace('\0', '')
                self.descriptionEntryText.set(description)
                self.currentFile.seek(0x50, os.SEEK_SET)
                signature = self.currentFile.read(0x28).decode().replace('\0', '')
                self.signatureEntryText.set(signature)
                self.currentFile.seek(0x90, os.SEEK_SET)
                arguments = self.currentFile.read(0x100).decode().replace('\0', '')
                self.argumentsEntryText.set(arguments)
            else:
                self.clearEntries(1)
                self.setFrameStates("disabled", 1)
                self.typeEntryText.set("Other")

            self.currentFile.seek(0x00, os.SEEK_SET)

            if self.checkFilesConfig():
                config.read("Files.ini")

                try:
                    currentMd5 = self.calculateMd5(self.currentFile)
                    storedMd5 = config.get("Files", self.currentFileName)

                    if currentMd5 == storedMd5:
                        self.statusEntryText.set("Original")
                    else:
                        self.statusEntryText.set("Edited!")
                except configparser.NoOptionError:
                    self.statusEntryText.set("New!")

    def selectFileEvent(self, event):
        self.selectFile()

    def addFile(self):
        filePath = filedialog.askopenfile(mode = "rb", filetypes = (("All Files", "*.*"),))

        if filePath:
            if self.checkFilesConfig():
                result = self.processFile(filePath)
                filePath.close()

                if result:
                    msgBox = messagebox.showinfo("Info", "File replaced successfully.")
                else:
                    msgBox = messagebox.showinfo("Info", "File appended successfully.")

    def addDirectory(self):
        dirName = filedialog.askdirectory()

        if dirName:
            dirList = self.filterDirectory(dirName)

            if self.checkDirectory(dirList):
                if self.checkFilesConfig():
                    newFileCount = 0
                    replaceFileCount = 0

                    for fileName in dirList:
                        filePath = os.path.join(dirName, fileName)
                        f = open(filePath, "rb")
                        result = self.processFile(f)
                        f.close()

                        if result:
                            replaceFileCount += 1
                        else:
                            newFileCount += 1

                    msgBox = messagebox.showinfo("Info", str(replaceFileCount) + " file(s) replaced.\n" + str(newFileCount) + " files(s) appended.")

    def processFile(self, fp):
        config = configparser.ConfigParser()
        fileMatch = False

        for i in range(0, self.game.dir.count):
            if os.path.basename(fp.name) == self.game.dir.entries[i].name:
                self.game.replaceFile(fp, i)
                self.loadFile(i, config, False)
                fileMatch = True
                break
        else:
            self.game.addFile(fp)
            self.listBox.insert(self.game.dir.count, os.path.basename(fp.name))
            self.loadFile(i + 1, config, False)
        return fileMatch

    def extractFile(self):
        filePath = filedialog.asksaveasfile(mode = "wb", initialfile = self.currentFileName, defaultextension = os.path.splitext(self.currentFileName)[1], filetypes = (("All Files", "*.*"),))

        if filePath:
            filePath.write(self.currentFile.getbuffer())
            filePath.close()
            msgBox = messagebox.showinfo("Info", "File extracted successfully.")

    def extractGame(self):
        dirName = filedialog.askdirectory()

        if dirName:
            combined = os.path.join(dirName, self.dirName[:-4])
            os.mkdir(combined)

            for i in range(0, self.game.dir.count):
                filePath = os.path.join(combined, self.game.dir.entries[i].name)
                f = open(filePath, "wb")
                f.write(self.game.wad.files[i].getbuffer())
                f.close()

            msgBox = messagebox.showinfo("Info", "Game extracted successfully.")

    def saveGame(self):
        dirPath = filedialog.asksaveasfilename(initialfile = self.dirName, defaultextension = ".DIR", filetypes = (("ASL DIR", "*.DIR"), ("All Files", "*.*")))

        if dirPath:
            wadPath = filedialog.asksaveasfilename(initialfile = self.wadName, defaultextension = ".WAD", filetypes = (("ASL WAD", "*.WAD"), ("All Files", "*.*")))

            if wadPath:
                fpDir = open(dirPath, "wb")
                fpWad = open(wadPath, "wb")
                self.game.writeGame(fpDir, fpWad)
                fpDir.close()
                fpWad.close()
                msgBox = messagebox.showinfo("Info", "Game saved successfully.")

def main():
    root = tk.Tk()
    root.resizable(0, 0)
    gui = ASLModManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
