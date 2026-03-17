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
        self.companion_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.roomRegionsDict = {}
        self.allDatapackageData = []
        self.includedItems = []
        self.playthrough = []
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
            userData = self.get_session(self.port)
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
        roomData = self.get_data(ROOM_STATUS_API + roomId)
        self.playerData = roomData["data"]["players"]

        checksumList = self.get_checksums(STATIC_TRACKER_API + self.trackerId)
        self.allDatapackageData = [self.get_data(DATAPACKAGE_API + checksum)["data"] for checksum in checksumList["data"]]

        self.preLoadJson()

    def get_session(self, port):
        """Find user session by checking cookies from browsers and matching the port number."""
        cookiesJar = self.get_cookies([])
        for cookies in cookiesJar:
            response = requests.get(USER_ENDPOINT_API, cookies=cookies)
            if response.status_code == 200:
                userRoomData = response.json()
                for room in userRoomData:
                    if room["last_port"] == port:
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
        return cookiesJar

    def get_checksums(self, url):
        """Retrieve checksums needed to acquire data packages for games."""
        response = requests.get(url)
        if response.status_code != 200:
            return {"data": [], "status": response.status_code}
        data = response.json()
        return {"data": [data["datapackage"][player["game"]]["checksum"] for player in data["player_game"]], "status": response.status_code}

    def preLoadJson(self):
        """Preload data from regions.json to reduce scanning time."""
        with open(os.path.join(self.companion_directory, "regions.json"), "r") as regionData:
            regions = json.load(regionData)
        self.roomRegionsDict = {game[1]: regions[game[1]] for game in self.playerData}
        self.includedItems = self.get_includeItems(self.playerData)

    def get_includeItems(self, playerData):
        """Load included items from include_items.json."""
        includedItems = []
        updated = False
        with open(os.path.join(self.companion_directory, "include_items.json"), "r") as includedItemsData:
            includedItemsList = json.load(includedItemsData)
            for currentPlayer in playerData:
                if currentPlayer[0] not in includedItemsList:
                    includedItemsList[currentPlayer[0]] = {currentPlayer[1]: {"Include Items List": []}}
                    updated = True

            for player in playerData:
                items = includedItemsList[player[0]][player[1]]["Include Items List"]
                includedItems.extend(
                    [item + f" ({player[0]})" if len(playerData) > 1 else item for item in items]
                )

        if updated:
            with open(os.path.join(self.companion_directory, "include_items.json"), "w") as includedItemsData:
                json.dump(includedItemsList, includedItemsData)

        return includedItems

    def update_includeItems(self, player, itemList):
        """Update the include items list for a specific player."""
        with open(os.path.join(self.companion_directory, "include_items.json"), "r") as includedItemsData:
            includedItemsList = json.load(includedItemsData)

        includedItemsList.setdefault(player[0], {}).setdefault(player[1], {"Include Items List": []})
        includedItemsList[player[0]][player[1]]["Include Items List"] = itemList

        with open(os.path.join(self.companion_directory, "include_items.json"), "w") as includedItemsData:
            json.dump(includedItemsList, includedItemsData)

    def get_regions(self, playerGame):
        """Retrieve regions for a specific game."""
        return self.roomRegionsDict[playerGame]["Region"]

    def get_data(self, url):
        """Fetch data from an API endpoint."""
        response = requests.get(url)
        if response.status_code != 200:
            self.processConnectionError("Failed to connect to endpoint:" + url)
        try:
            return {"data": response.json(), "status": response.status_code}
        except json.JSONDecodeError:
            self.processConnectionError("Invalid or empty JSON response")

    def update_tracker(self):
        """Update tracker data."""
        global trackerData
        trackerData = self.get_data(TRACKER_API + self.trackerId)
        if trackerData["status"] != 200:
            self.processConnectionError("Failed to get tracker data")
        trackerData = trackerData["data"]

    def get_hint(self):
        """
        Generate a hint for the next location to check based on the playthrough and tracker data.
        """
        firstNewLocationToEndOfSphereList = []
        allCheckLocations = []
        uncheckedLocation = []
        newRegionHint = ""
        playerLocation = ""  # Player and game who the check belongs to
        foundLocation = False

        self.update_tracker()

        # Gather all checked locations
        playerChecks = trackerData["player_checks_done"]
        for playerInd, playerNum in enumerate(playerChecks):
            allCheckLocations = playerNum["locations"]
            locationMapping = self.allDatapackageData[playerInd]["location_name_to_id"]
            for location, locationID in locationMapping.items():
                if locationID not in allCheckLocations:
                    if len(self.playerData) > 1:
                        uncheckedLocation.append({"player": self.playerData[playerInd][0], "location": location + START_OF_PLAYER_LOCATION_MARKER + self.playerData[playerInd][0] + END_OF_LOCATION_MARKER})
                    else: 
                        uncheckedLocation.append(location + SOLO_END_OF_LOCATION_MARKER) 

        # Find the first unchecked location in the playthrough
        for line in self.playthrough:
            line = line.lstrip()
            if line.startswith(END_OF_SPHERE_MARKER) and foundLocation:
                break
            for location in uncheckedLocation:
                if line.startswith(location["location"]) and [line.find(item) for item in self.includedItems]:
                    firstNewLocationToEndOfSphereList.append(location)
                    foundLocation = True

        # Randomly choose a location to avoid bias
        chosenLocation = random.choice(firstNewLocationToEndOfSphereList)

        # Determine the region for the chosen location
        regionList = self.get_regions(playerLocation[1])
        for region in regionList:
            try:
                regionListKeys = list(region.keys())
                if regionListKeys:
                    regionAlias = region[regionListKeys[0]]
                    for alias in regionAlias:
                        if chosenLocation["location"].startswith(alias):
                            newRegionHint = f"{playerLocation[0]}: {regionListKeys[0]}"
                            break
                if newRegionHint:
                    break
            except Exception:
                regionAlias = region
                if chosenLocation["location"].startswith(regionAlias):
                    newRegionHint = f"{chosenLocation["player"]}: {region}"
                    break

        hint = f"Have you tried searching here?\n {newRegionHint}"

    def build_playthrough(self, spoilerFile):
        """Extract playthrough data from the spoiler file."""
        self.playthrough = []
        with open(spoilerFile, "r") as spoilerData:
            spoiler = spoilerData.readlines()

        playthroughStart = next((i for i, line in enumerate(spoiler) if line.startswith("Playthrough:\n")), 0)
        playthroughEnd = next((i for i, line in enumerate(spoiler) if line.startswith("Paths:\n")), len(spoiler))
        self.playthrough = spoiler[playthroughStart + 1:playthroughEnd]

        spoilerData.close()

    def processConnectionError(self, error):
        """Handle connection errors."""
        app.connectionFrame.statusFrame.status_label.configure(text=error)
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
                self.status_label = ctk.CTkLabel(self, text="Awaiting Connection", **FRAME_TITLE_STYLE)
                self.status_label.grid(row=0, column=0, padx=5, pady=5)

class connectionFrame(ctk.CTkFrame):
    """
    frame for connection stings and status
    """

    def __init__(self, master):
        super().__init__(master)
        self.port_var = ctk.StringVar()
        self.roomId_var = ctk.StringVar()
        self.trackerId_var = ctk.StringVar()
        self.grid_columnconfigure(0, weight=1)
                
        # Port Number
        self.portLabel = ctk.CTkLabel(self, text="Port Number", **FRAME_TITLE_STYLE)
        self.portLabel.grid(row=0, column=0, padx=5, pady=5)

        self.portEntry = ctk.CTkEntry(self, textvariable=self.port_var, width=200)
        self.portEntry.grid(row=0, column=1, padx=5, pady=5)

        # Room ID
        self.roomLabel = ctk.CTkLabel(self, text="Room ID", **FRAME_TITLE_STYLE)
        self.roomLabel.grid(row=1, column=0, padx=5, pady=5)

        self.roomEntry = ctk.CTkEntry(self, textvariable=self.roomId_var, width=200)
        self.roomEntry.grid(row=1, column=1, padx=5, pady=5)

        # Connection Instructions
        self.roomLabel = ctk.CTkLabel(self, text="Connect with Port\nor Room and Tracker ID")
        self.roomLabel.grid(row=1, column=2, padx=5, pady=5, rowspan=2)

        # Tracker ID
        self.trackerLabel = ctk.CTkLabel(self, text="Tracker ID", **FRAME_TITLE_STYLE)
        self.trackerLabel.grid(row=2, column=0, padx=5, pady=5)

        self.trackerEntry = ctk.CTkEntry(self, textvariable=self.trackerId_var, width=200)
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
            self.master.data.port = self.port_var.get()
            self.master.data.roomIdText = self.roomId_var.get()
            self.master.data.trackerIdText = self.trackerId_var.get()
            self.connectButton.configure(state="disabled")
            self.master.hintFrame.getHint.configure(state="disabled")
            self.master.gamePrepFrame.setupItemHints.configure(state="disabled")

            self.statusFrame.status_label.configure(text="Connecting...")
            self.statusFrame.configure(fg_color="black")
            self.update()
            self.update_idletasks()
            try:
                self.master.data.connect()
                self.statusFrame.status_label.configure(text="Connected")
                self.connectButton.configure(state="normal")
                self.statusFrame.configure(fg_color="blue")
                self.master.hintFrame.getHint.configure(state="normal")
                self.master.gamePrepFrame.setupItemHints.configure(state="normal")
                self.roomId_var.set(self.master.data.roomIdText)
                self.trackerId_var.set(self.master.data.trackerIdText)

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

        self.setupItemHints = ctk.CTkButton(self, text="Setup Item Hints", command=lambda: self.openIncludeItemGUI(), state="disabled")
        self.setupItemHints.grid(row=0, column=1, padx=5, pady=5)

    def selectSpoilerFile(self):
        spoilerFile = filedialog.askopenfilename()
        self.master.data.build_playthrough(spoilerFile)

    def openIncludeItemGUI(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Include Items")
        popup.geometry("500x500")
        popup.grab_set()  # Make popup modal
        popup.columnconfigure(0, weight=1)
        
        self.player_var = ctk.StringVar(value=self.master.data.playerData[0][0]) 
        self.playerSelectOptionsMenu = ctk.CTkOptionMenu(popup, variable=self.player_var, values=[players[0] for players in self.master.data.playerData], command=self.updatePlayerVar)
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

        ctk.CTkButton(popup, text="Close", command=popup.destroy).grid(row=3, column=0, pady=10)

        self.updatePlayerVar()  # Trigger updatePlayerVar once on window load

    def updatePlayerVar(self, *args):
        self.playerIndex = self.playerSelectOptionsMenu._values.index(self.player_var.get())
        self.gameLabel.configure(text="Game: " + self.master.data.playerData[self.playerIndex][1])
        self.initializeItemLists()
        self.excludeItemList.selection_clear(0, tk.END)
        self.includeItemList.selection_clear(0, tk.END)
        self.update_idletasks

    def updateLists(self, current_include, current_exclude):
        # Update the Listbox variables
        self.playerIncludeItemList.set(current_include)
        self.playerExcludeItemList.set(current_exclude)

        # Update the Listbox widgets
        self.excludeItemList.config(listvariable=self.playerExcludeItemList)
        self.includeItemList.config(listvariable=self.playerIncludeItemList)

        self.update_idletasks()
        self.master.data.update_includeItems(self.master.data.playerData[self.playerIndex],self.playerIncludeItemList.get())

    def initializeItemLists(self, *args):

        with open(os.path.join(self.master.data.companion_directory, "include_items.json"), "r") as includedItemsData:
            includedItemsList = json.load(includedItemsData)

        # Update the include and exclude lists
        current_include = includedItemsList[self.master.data.playerData[self.playerIndex][0]][self.master.data.playerData[self.playerIndex][1]]["Include Items List"]
        current_exclude = list(self.master.data.allDatapackageData[self.playerIndex]["item_name_to_id"].keys())
        
        # Update current exclude list
        current_exclude = [item for item in current_exclude if item not in current_include]

        self.updateLists(current_include, current_exclude)

    def addSelected(self):
        selected = self.excludeItemList.curselection()
        if not selected:  # Check if no items are selected
            return

        # Get selected items
        selected_items = [self.excludeItemList.get(item) for item in selected]

        # Update the include and exclude lists
        current_include = list(self.playerIncludeItemList.get())
        current_exclude = list(self.playerExcludeItemList.get())

        # Add selected items to the include list
        current_include.extend(selected_items)

        # Remove selected items from the exclude list
        current_exclude = [item for item in current_exclude if item not in selected_items]

        self.updateLists(current_include, current_exclude)

    def removeSelected(self):
        selected = self.includeItemList.curselection()
        if not selected:  # Check if no items are selected
            return

        # Get selected items
        selected_items = [self.includeItemList.get(item) for item in selected]

        # Update the include and exclude lists
        current_include = list(self.playerIncludeItemList.get())
        current_exclude = list(self.playerExcludeItemList.get())

        # Add selected items back to the exclude list
        current_exclude.extend(selected_items)

        # Remove selected items from the include list
        current_include = [item for item in current_include if item not in selected_items]

        self.updateLists(current_include, current_exclude)

class hintFrame(ctk.CTkFrame):
    """
    frame for hint options.
    """
    def __init__(self, master):
        super().__init__(master)
        
        # Get Hint Button
        self.getHint = ctk.CTkButton(self, text="Get Hint", command=lambda: self.update_hint(), state="disabled")
        self.getHint.grid(row=4, column=0, padx=5, pady=5)

        # Hint Label
        self.hint_label = ctk.CTkLabel(self, text=self.master.data.hint)
        self.hint_label.grid(row=4, column=1, padx=5, pady=5, columnspan=2, rowspan=2)

    def update_hint(self,master):
        """
        Update the hint label with the next hint.
        """
        try:
            self.master.data.get_hint()
            self.hint_label.configure(text=self.master.data.hint)
        except Exception as e:
            self.hint_label.configure(text=e, fg_color = "dark red")

class HintCompanion(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Hint Companion")
        self.geometry("540x300")
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










