import requests
import browser_cookie3
import os
import sys
import json
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from customtkinter import filedialog
import random

# Constants
END_OF_LOCATION_MARKER = "): "
SOLO_END_OF_LOCATION_MARKER = ": "
START_OF_PLAYER_LOCATION_MARKER = " ("
END_OF_SPHERE_MARKER = "}"
USER_ENDPOINT_API = "https://archipelago.gg/api/get_rooms"
ROOM_STATUS_API = "https://archipelago.gg/api/room_status/"
TRACKER_API = "https://archipelago.gg/api/tracker/"
STATIC_TRACKER_API = "https://archipelago.gg/api/static_tracker/"
DATAPACKAGE_API = "https://archipelago.gg/api/datapackage/"

# Appearance settings
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")
FRAME_TITLE_STYLE = {
    "text_color": "#D3D3D3",
    "font": ("Segoe UI", 14, "bold"),
    "anchor": "w",
}

class hintCompanionData:
    def __init__(self):
        self.companionDirectory = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.roomRegionsDict = {}
        self.allDatapackageData = []
        self.includedItems = []
        self.playthrough = []
        self.spoilerLocations = []
        self.trackerData = []
        self.playerData = []
        self.port = 0
        self.portText = ""
        self.trackerIdText = ""
        self.roomIdText = ""
        self.hint = ""
        self.trackerId = ""

    def connect(self):
        """Initialize connection and acquire room data, game lists, and datapackage for all games."""

        if self.port != "":
            userData = self.getSession(self.port)
            if not userData["room_id"]:
                self.processConnectionError("No session found")
            elif userData["status"] != 200:
                self.processConnectionError("Unable to connect")
            roomId = userData["room_id"]
            self.trackerId = userData["tracker"]
        elif self.trackerIdText and self.roomIdText:
            roomId = self.roomIdText
            self.trackerId = self.trackerIdText

        self.roomIdText, self.trackerIdText = roomId, self.trackerId
        roomData = self.getData(ROOM_STATUS_API + roomId)
        self.playerData = roomData["data"]["players"]

        checksumList = self.getChecksums(STATIC_TRACKER_API + self.trackerId)
        self.allDatapackageData = [self.getData(DATAPACKAGE_API + checksum)["data"] for checksum in checksumList["data"]]

        self.preLoadJson()

    def getSession(self, port):
        """Find user session by checking cookies from browsers and matching the port number."""
        cookiesJar = self.get_cookies([])
        for cookies in cookiesJar:
            response = requests.get(USER_ENDPOINT_API, cookies=cookies)
            if response.status_code == 200:
                userRoomData = response.json()
                for room in userRoomData:
                    if room["last_port"] == int(port):
                        return {"room_id": room["room_id"], "tracker": room["tracker"], "status": response.status_code}
        return {"room_id": "", "tracker": "", "status": 404}

    def get_cookies(self, cookiesJar):
        """Retrieve cookies from supported browsers."""
        browsers = [
            "chrome", "firefox", "edge", "opera", "brave", "librewolf",
            "operagx", "chromium", "vivaldi", "safari", "lynx", "w3m"
        ]
        for browser in browsers:
            try:
                cookiesJar.append(getattr(browser_cookie3, browser)(domain_name="archipelago.gg"))
            except:
                pass

            try:
                session = requests.Session()
                response = session.get("https://archipelago.gg/")
                if response.status_code == 200:
                    cookiesJar.append(session.cookies.get_dict())
                    cookiesJar.append(response.cookies)
            except:
                pass

        return cookiesJar

    def getChecksums(self, url):
        """Retrieve checksums needed to acquire data packages for games."""
        response = requests.get(url)
        if response.status_code != 200:
            return {"data": [], "status": response.status_code}
        data = response.json()
        return {"data": [data["datapackage"][player["game"]]["checksum"] for player in data["player_game"]], "status": response.status_code}

    def preLoadJson(self):
        """Preload data from regions.json to reduce scanning time."""
        with open(os.path.join(self.companionDirectory, "regions.json"), "r") as regionData:
            regions = json.load(regionData)
        self.roomRegionsDict = {game[1]: regions[game[1]] for game in self.playerData}
        self.includedItems = self.getIncludeItems(self.playerData)

    def getIncludeItems(self, playerData):
        """Load included items from include_items.json."""
        includedItems = []
        updated = False
        with open(os.path.join(self.companionDirectory, "include_items.json"), "r") as includedItemsData:
            includedItemsList = json.load(includedItemsData)
            for currentPlayer in playerData:
                if currentPlayer[0] not in includedItemsList:
                    includedItemsList[currentPlayer[0]] = {currentPlayer[1]: {"Include Items List": []}}
                    updated = True
                if currentPlayer[1] not in includedItemsList[currentPlayer[0]]:
                    includedItemsList[currentPlayer[0]][currentPlayer[1]] = {"Include Items List": []}
                    updated = True

            for player in playerData:
                items = includedItemsList[player[0]][player[1]]["Include Items List"]
                includedItems.extend(
                    [item + f" ({player[0]})" if len(playerData) > 1 else item for item in items]
                )

        if updated:
            with open(os.path.join(self.companionDirectory, "include_items.json"), "w") as includedItemsData:
                json.dump(includedItemsList, includedItemsData)

        return includedItems

    def updateIncludeItems(self, player, itemList):
        """Update the include items list for a specific player."""
        with open(os.path.join(self.companionDirectory, "include_items.json"), "r") as includedItemsData:
            includedItemsList = json.load(includedItemsData)

        includedItemsList.setdefault(player[0], {}).setdefault(player[1], {"Include Items List": []})
        includedItemsList[player[0]][player[1]]["Include Items List"] = itemList

        with open(os.path.join(self.companionDirectory, "include_items.json"), "w") as includedItemsData:
            json.dump(includedItemsList, includedItemsData)

    def getRegions(self, playerGame):
        """Retrieve regions for a specific game."""
        return self.roomRegionsDict[playerGame]["Region"]

    def getData(self, url):
        """Fetch data from an API endpoint."""
        response = requests.get(url)
        if response.status_code != 200:
            self.processConnectionError("Failed to connect to endpoint:" + url)
        try:
            return {"data": response.json(), "status": response.status_code}
        except json.JSONDecodeError:
            self.processConnectionError("Invalid or empty JSON response")

    def updateTracker(self):
        """Update tracker data."""
        self.trackerData = self.getData(TRACKER_API + self.trackerId)
        if self.trackerData["status"] != 200:
            self.processConnectionError("Failed to get tracker data")
        self.trackerData = self.trackerData["data"]

    def getRegionBasedHint(self):
        """
        Generate a hint for the next location to check based on the playthrough and tracker data.
        """
        firstNewLocationToEndOfSphereList = []
        newRegionHint = ""
        playerLocation = ""  # Player and game who the check belongs to
        foundLocation = False

        self.updateTracker()

        # Find the first unchecked location in the playthrough
        for line in self.playthrough:
            line = line.lstrip()
            if line.startswith(END_OF_SPHERE_MARKER) and foundLocation:
                break
            for location in self.getUnchecked():
                if line.startswith(location["location"]):
                    for item in self.includedItems:
                        if line[len(location["location"]) - 1:].find(item) > -1:
                            firstNewLocationToEndOfSphereList.append(location)
                            foundLocation = True

        # Randomly choose a location to avoid bias
        chosenLocation = random.choice(firstNewLocationToEndOfSphereList)

        # Determine the region for the chosen location
        regionList = self.getRegions(chosenLocation["player"][1])
        for region in regionList:
            try:
                regionListKeys = list(region.keys())
                if regionListKeys:
                    regionAlias = region[regionListKeys[0]]
                    for alias in regionAlias:
                        if chosenLocation["location"].startswith(alias):
                            newRegionHint = f"{chosenLocation["player"][0]}: {regionListKeys[0]}"
                            break
                if newRegionHint:
                    break
            except Exception:
                regionAlias = region
                if chosenLocation["location"].startswith(regionAlias):
                    newRegionHint = f"{chosenLocation["player"][0]}: {region}"
                    break

        self.hint = f"Have you tried searching here?\n {newRegionHint}"

    def getRandomItemHint(self):
        self.updateTracker()
        uncheckedLocations = self.getUnchecked()
        random.shuffle(uncheckedLocations)
        for uncheckedLocation in uncheckedLocations:
            for location in self.spoilerLocations:
                if location.startswith(uncheckedLocation["location"]):
                    for item in self.includedItems:
                        if location[len(uncheckedLocation["location"]) - 1:].find(item) > -1:
                            self.hint = location
                            return

    def getUnchecked(self):
        allCheckLocations = []
        uncheckedLocation = []

        # Gather all checked locations
        playerChecks = self.trackerData["player_checks_done"]
        
        if app.hintFrame.playerScopeToggleVar.get() == "on":
            allCheckLocations = playerChecks[app.hintFrame.playerInd]["locations"]
            locationMapping = self.allDatapackageData[app.hintFrame.playerInd]["location_name_to_id"]
            for location, locationID in locationMapping.items():
                if locationID not in allCheckLocations:
                    if len(self.playerData) > 1:
                        uncheckedLocation.append({"player": self.playerData[app.hintFrame.playerInd], "location": location + START_OF_PLAYER_LOCATION_MARKER + app.hintFrame.playerVar.get() + END_OF_LOCATION_MARKER})
                    else: 
                        uncheckedLocation.append({"player": self.playerData[app.hintFrame.playerInd], "location": location + SOLO_END_OF_LOCATION_MARKER})
        else:
            for playerInd, playerNum in enumerate(playerChecks):
                allCheckLocations = playerNum["locations"]
                locationMapping = self.allDatapackageData[playerInd]["location_name_to_id"]
                for location, locationID in locationMapping.items():
                    if locationID not in allCheckLocations:
                        if len(self.playerData) > 1:
                            uncheckedLocation.append({"player": self.playerData[playerInd], "location": location + START_OF_PLAYER_LOCATION_MARKER + self.playerData[playerInd][0] + END_OF_LOCATION_MARKER})
                        else: 
                            uncheckedLocation.append({"player": self.playerData[playerInd], "location": location + SOLO_END_OF_LOCATION_MARKER})

        return uncheckedLocation

    def buildPlaythrough(self, spoilerFile):
        """Extract playthrough data from the spoiler file."""
        self.playthrough = []
        with open(spoilerFile, "r") as spoilerData:
            spoiler = spoilerData.readlines()

        locationsStart = next((i for i, line in enumerate(spoiler) if line.startswith("Locations:\n")), 0)
        locationsEnd = next((i for i, line in enumerate(spoiler) if line.startswith("Playthrough:\n")), len(spoiler))
        self.spoilerLocations = spoiler[locationsStart + 2:locationsEnd - 1]

        playthroughStart = next((i for i, line in enumerate(spoiler) if line.startswith("Playthrough:\n")), 0)
        playthroughEnd = next((i for i, line in enumerate(spoiler) if line.startswith("Paths:\n")), len(spoiler))
        self.playthrough = spoiler[playthroughStart + 1:playthroughEnd]

        spoilerData.close()

    def processConnectionError(self, error):
        """Handle connection errors."""
        app.connectionFrame.statusFrame.statusLabel.configure(text=error)
        app.connectionFrame.statusFrame.configure(fg_color="dark red")
        raise Exception(error)

"""
GUI Classes
"""
class statusFrame(ctk.CTkFrame):
            def __init__(self, master):
                super().__init__(master)
                self.grid_columnconfigure(0, weight=1)

                # Status Label
                self.statusLabel = ctk.CTkLabel(self, text="Awaiting Connection", **FRAME_TITLE_STYLE)
                self.statusLabel.grid(row=0, column=0, padx=5, pady=5)

class connectionFrame(ctk.CTkFrame):
    """
    frame for connection stings and status
    """

    def __init__(self, master):
        super().__init__(master)
        self.portVar = ctk.StringVar()
        self.roomIdVar = ctk.StringVar()
        self.trackerIdVar = ctk.StringVar()
        self.grid_columnconfigure(0, weight=1)
                
        # Port Number
        self.portLabel = ctk.CTkLabel(self, text="Port Number", **FRAME_TITLE_STYLE)
        self.portLabel.grid(row=0, column=0, padx=5, pady=5)

        self.portEntry = ctk.CTkEntry(self, textvariable=self.portVar, width=200)
        self.portEntry.grid(row=0, column=1, padx=5, pady=5)

        # Room ID
        self.roomLabel = ctk.CTkLabel(self, text="Room ID", **FRAME_TITLE_STYLE)
        self.roomLabel.grid(row=1, column=0, padx=5, pady=5)

        self.roomEntry = ctk.CTkEntry(self, textvariable=self.roomIdVar, width=200)
        self.roomEntry.grid(row=1, column=1, padx=5, pady=5)

        # Connection Instructions
        self.roomLabel = ctk.CTkLabel(self, text="Connect with Port\nor Room and Tracker ID")
        self.roomLabel.grid(row=1, column=2, padx=5, pady=5, rowspan=2)

        # Tracker ID
        self.trackerLabel = ctk.CTkLabel(self, text="Tracker ID", **FRAME_TITLE_STYLE)
        self.trackerLabel.grid(row=2, column=0, padx=5, pady=5)

        self.trackerEntry = ctk.CTkEntry(self, textvariable=self.trackerIdVar, width=200)
        self.trackerEntry.grid(row=2, column=1, padx=5, pady=5)

        # Connect Button
        self.connectButton = ctk.CTkButton(self, text="Connect", command=lambda: self.processConnection(master))
        self.connectButton.grid(row=0, column=2, padx=5, pady=5)

        self.statusFrame = statusFrame(self)
        self.statusFrame.grid(row=3, column=0, padx=5, pady=5, sticky="ew", columnspan=3)
        self.statusFrame.configure(fg_color="grey")

    def processConnection(self,master):
            """
            Handle the connection process and update the UI accordingly.
            """
            self.master.data.port = self.portVar.get()
            self.master.data.roomIdText = self.roomIdVar.get()
            self.master.data.trackerIdText = self.trackerIdVar.get()
            self.connectButton.configure(state="disabled")
            self.master.hintFrame.getNextRegionHintBtn.configure(state="disabled")
            self.master.hintFrame.playerSelectOptionsMenu.configure(state="disabled")
            self.master.hintFrame.playerScopeToggleSW.configure(state="disabled")
            self.master.gamePrepFrame.setupItemHintsBtn.configure(state="disabled")
            self.master.hintFrame.getRandomItemHintBtn.configure(state="disabled")

            self.statusFrame.statusLabel.configure(text="Connecting...")
            self.statusFrame.configure(fg_color="black")
            self.update()
            self.update_idletasks()
            try:
                self.master.data.connect()
                self.statusFrame.statusLabel.configure(text="Connected")
                self.connectButton.configure(state="normal")
                self.statusFrame.configure(fg_color="blue")
                self.master.hintFrame.getNextRegionHintBtn.configure(state="normal")
                self.master.gamePrepFrame.setupItemHintsBtn.configure(state="normal")
                self.master.hintFrame.playerSelectOptionsMenu.configure(state="normal", values=[players[0] for players in self.master.data.playerData])
                self.master.hintFrame.playerSelectOptionsMenu.set(self.master.data.playerData[0][0])
                self.master.hintFrame.playerScopeToggleSW.configure(state="normal")
                self.master.hintFrame.getRandomItemHintBtn.configure(state="normal")
                self.roomIdVar.set(self.master.data.roomIdText)
                self.trackerIdVar.set(self.master.data.trackerIdText)
                self.update_idletasks()
            except ValueError as e:
                print(e)
                self.connectButton.configure(state="normal")
                self.master.data.processConnectionError("Invalid Port Number")
            except Exception as e:
                print(e)
                self.connectButton.configure(state="normal")

class gamePrepFrame(ctk.CTkFrame):
    """
    settings required for hints to generate per seed.
    """
    def __init__(self, master):
        super().__init__(master)

        self.spoilerSelectBtn = ctk.CTkButton(self, text="Select Spoiler File", command=lambda: self.selectSpoilerFile())
        self.spoilerSelectBtn.grid(row=0, column=0, padx=5, pady=5)

        self.setupItemHintsBtn = ctk.CTkButton(self, text="Setup Item Hints", command=lambda: self.openIncludeItemGUI(), state="disabled")
        self.setupItemHintsBtn.grid(row=0, column=1, padx=5, pady=5)

    def selectSpoilerFile(self):
        spoilerFile = filedialog.askopenfilename()
        self.master.data.buildPlaythrough(spoilerFile)

    def openIncludeItemGUI(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Include Items")
        popup.geometry("500x500")
        popup.grab_set()  # Make popup modal
        popup.columnconfigure(0, weight=1)
        
        self.playerVar = ctk.StringVar(value=self.master.data.playerData[0][0]) 
        self.playerSelectOptionsMenu = ctk.CTkOptionMenu(popup, variable=self.playerVar, values=[players[0] for players in self.master.data.playerData], command=self.updatePlayerVar)
        self.playerSelectOptionsMenu.grid(row=0, column=0, padx=5, pady=5)
        self.gameLabel = ctk.CTkLabel(popup, text="Game: " + self.master.data.playerData[0][1])
        self.gameLabel.grid(row=0, column=1, padx=5, pady=5)

        self.excludeListFrame = ttk.Frame(popup)
        self.playerExcludeItemList = tk.Variable(value=[])
        self.excludeItemList = tk.Listbox(self.excludeListFrame, listvariable=self.playerExcludeItemList, selectmode=tk.MULTIPLE, width=50, height=10, 
                                          yscrollcommand=lambda *args: self.excludeScrollBar.set(*args))
        self.excludeScrollBar = tk.Scrollbar(self.excludeListFrame, orient=tk.VERTICAL, command=self.excludeItemList.yview)
        self.excludeItemList.grid(row=0, column=0, sticky="news")
        self.excludeScrollBar.grid(row=0, column=1, sticky="ns")
        self.excludeListFrame.grid_rowconfigure(0, weight=1)
        self.excludeListFrame.grid_columnconfigure(0, weight=1)
        
        self.includeListFrame = ttk.Frame(popup)
        self.playerIncludeItemList = tk.Variable(value=[])
        self.includeItemList = tk.Listbox(self.includeListFrame, listvariable=self.playerIncludeItemList, selectmode=tk.MULTIPLE, width=50, height=10, 
                                          yscrollcommand=lambda *args: self.includeScrollBar.set(*args))
        self.includeScrollBar = tk.Scrollbar(self.includeListFrame, orient=tk.VERTICAL, command=self.excludeItemList.yview)
        self.includeItemList.grid(row=0, column=0, sticky="news")
        self.includeScrollBar.grid(row=0, column=1, sticky="ns")
        self.includeListFrame.grid_rowconfigure(0, weight=1)
        self.includeListFrame.grid_columnconfigure(0, weight=1)

        self.excludeListFrame.grid(row=1, column=0, sticky="news", padx=10, pady=10)
        self.includeListFrame.grid(row=1, column=1, sticky="news", padx=10, pady=10)

        self.addItemsButton  = ctk.CTkButton(popup, text="Add", command=lambda: self.addSelected())
        self.addItemsButton.grid(row=2, column=0, padx=5, pady=5)
        self.removeItemsButton  = ctk.CTkButton(popup, text="Remove", command=lambda: self.removeSelected())
        self.removeItemsButton.grid(row=2, column=1, padx=5, pady=5)

        ctk.CTkButton(popup, text="Close", command=lambda: self.updateIncludedItems(popup)).grid(row=3, column=0, pady=10)

        self.updatePlayerVar()  # Trigger updatePlayerVar once on window load

    def updatePlayerVar(self, *args):
        self.playerInd = self.playerSelectOptionsMenu._values.index(self.playerVar.get())
        self.gameLabel.configure(text="Game: " + self.master.data.playerData[self.playerInd][1])
        self.initializeItemLists()
        self.excludeItemList.selection_clear(0, tk.END)
        self.includeItemList.selection_clear(0, tk.END)
        self.update_idletasks

    def updateLists(self, currentInclude, currentExclude):
        # Update the Listbox variables
        self.playerIncludeItemList.set(currentInclude)
        self.playerExcludeItemList.set(currentExclude)

        # Update the Listbox widgets
        self.excludeItemList.config(listvariable=self.playerExcludeItemList)
        self.includeItemList.config(listvariable=self.playerIncludeItemList)

        self.excludeItemList.selection_clear(0, tk.END)
        self.includeItemList.selection_clear(0, tk.END)

        self.update_idletasks()
        self.master.data.updateIncludeItems(self.master.data.playerData[self.playerInd],self.playerIncludeItemList.get())

    def initializeItemLists(self, *args):

        with open(os.path.join(self.master.data.companionDirectory, "include_items.json"), "r") as includedItemsData:
            includedItemsList = json.load(includedItemsData)

        # Update the include and exclude lists
        currentInclude = includedItemsList[self.master.data.playerData[self.playerInd][0]][self.master.data.playerData[self.playerInd][1]]["Include Items List"]
        currentExclude = list(self.master.data.allDatapackageData[self.playerInd]["item_name_to_id"].keys())
        
        # Update current exclude list
        currentExclude = [item for item in currentExclude if item not in currentInclude]

        self.updateLists(currentInclude, currentExclude)

    def addSelected(self):
        selected = self.excludeItemList.curselection()
        if not selected:  # Check if no items are selected
            return

        # Get selected items
        selectedItems = [self.excludeItemList.get(item) for item in selected]

        # Update the include and exclude lists
        currentInclude = list(self.playerIncludeItemList.get())
        currentExclude = list(self.playerExcludeItemList.get())

        # Add selected items to the include list
        currentInclude.extend(selectedItems)

        # Remove selected items from the exclude list
        currentExclude = [item for item in currentExclude if item not in selectedItems]

        self.updateLists(currentInclude, currentExclude)

    def removeSelected(self):
        selected = self.includeItemList.curselection()
        if not selected:  # Check if no items are selected
            return

        # Get selected items
        selectedItems = [self.includeItemList.get(item) for item in selected]

        # Update the include and exclude lists
        currentInclude = list(self.playerIncludeItemList.get())
        currentExclude = list(self.playerExcludeItemList.get())

        # Add selected items back to the exclude list
        currentExclude.extend(selectedItems)

        # Remove selected items from the include list
        currentInclude = [item for item in currentInclude if item not in selectedItems]

        self.updateLists(currentInclude, currentExclude)

    def updateIncludedItems(self,popup): 
        self.master.data.includedItems = self.master.data.getIncludeItems(self.master.data.playerData)
        popup.destroy()

class hintFrame(ctk.CTkFrame):
    """
    frame for hint options.
    """
    def __init__(self, master):
        super().__init__(master)
        
        self.playerScopeToggleVar = ctk.StringVar(value="off")
        self.playerScopeToggleSW = ctk.CTkSwitch(self, text="Hints for Specific Player", command=lambda: self.playerScopeToggle(), 
                                               variable=self.playerScopeToggleVar, onvalue="on", offvalue="off", state="disabled")
        self.playerScopeToggleSW.grid(row=0, column=0, padx=5, pady=5)
        self.playerVar = ctk.StringVar(value="None")
        self.playerSelectOptionsMenu = ctk.CTkOptionMenu(self, variable=self.playerVar, values=[players[0] for players in self.master.data.playerData], 
                                                         state="disabled", command=self.setPlayerInd)
        self.playerSelectOptionsMenu.grid(row=0, column=1, padx=5, pady=5)
        self.playerInd = 0
                                                         
        # Get Next Region Hint Button
        self.getNextRegionHintBtn = ctk.CTkButton(self, text="Get Next Region Hint", command=lambda: self.updateNextRegionHint(), state="disabled")
        self.getNextRegionHintBtn.grid(row=1, column=0, padx=5, pady=5)

        # Get Random Hint Button
        self.getRandomItemHintBtn = ctk.CTkButton(self, text="Get Random Item Hint", command=lambda: self.updateRandomItemHint(), state="disabled")
        self.getRandomItemHintBtn.grid(row=1, column=1, padx=5, pady=5)

        # Hint Label
        self.hintLabel = ctk.CTkLabel(self, text=self.master.data.hint)
        self.hintLabel.grid(row=2, column=0, padx=5, pady=5, columnspan=2, rowspan=2)

    def setPlayerInd(self, *args):
        self.playerInd = self.playerSelectOptionsMenu._values.index(self.playerVar.get())

    def playerScopeToggle(self):
        if self.playerScopeToggleVar.get() == "on":
            self.playerSelectOptionsMenu.configure(state="enabled", values=[players[0] for players in self.master.data.playerData])
            self.master.hintFrame.playerSelectOptionsMenu.set(self.master.data.playerData[0][0])
            self.update_idletasks()
        else:
            self.playerSelectOptionsMenu.configure(state="disabled")

    def updateNextRegionHint(self):
        """
        Update the hint label with the next region based hint.
        """
        try:
            self.master.data.getRegionBasedHint()
            self.hintLabel.configure(text=self.master.data.hint)
            self.hintLabel.configure(fg_color = "transparent")
        except Exception as e:
            self.hintLabel.configure(text=e, fg_color = "dark red")
    
    def updateRandomItemHint(self):
        """
        Update the hint label with the next random item hint.
        """
        try:
            self.master.data.getRandomItemHint()
            self.hintLabel.configure(text=self.master.data.hint)
            self.hintLabel.configure(fg_color = "transparent")
        except Exception as e:
            self.hintLabel.configure(text=e, fg_color = "dark red")

class HintCompanion(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Hint Companion")
        self.geometry("540x400")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1), weight=1)
        self.data = hintCompanionData()
        
        self.connectionFrame = connectionFrame(self)
        self.connectionFrame.grid(row=0, column=0, padx=5, pady=5, sticky="news")

        self.gamePrepFrame = gamePrepFrame(self)
        self.gamePrepFrame.grid(row=1, column=0, padx=5, pady=5, sticky="news")

        self.hintFrame = hintFrame(self)
        self.hintFrame.grid(row=2, column=0, padx=5, pady=5, sticky="news")

if __name__ == "__main__":

    app = HintCompanion()
    app.mainloop()










