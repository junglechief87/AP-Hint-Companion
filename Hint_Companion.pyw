import requests
import browser_cookie3
import os
import sys
import json
import customtkinter as ctk
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

# Globals
companion_directory = os.path.dirname(os.path.abspath(sys.argv[0]))
roomRegionsDict = {}
allDatapackageData = []
excludedItems = []
playthrough = []
trackerData = []
playerData = []
port = 0
portText = ""
trackerIdText = ""
roomIdText = ""
hint = ""
trackerId = ""

def connect(port, roomIdInput, trackerIdInput):
    """Initialize connection and acquire room data, game lists, and datapackage for all games."""
    global allDatapackageData, playerData, trackerId, roomIdText, trackerIdText

    allDatapackageData = []
    userData = []
    roomId = ""
    trackerId = ""

    if port != 0:
        userData = get_session(port)
        if userData["room_id"] == "":
            return {"failed": True, "error": "No session found"}
        elif userData["status"] != 200:
            return {"failed": True, "error": "Unable to connect"}
        roomId = userData["room_id"]
        trackerId = userData["tracker"]
    elif port == 0 and roomIdInput and trackerIdInput:
        roomId = roomIdInput
        trackerId = trackerIdInput

    roomIdText = roomId
    trackerIdText = trackerId

    roomData = get_data(ROOM_STATUS_API + roomId)
    if roomData["status"] != 200:
        return {"failed": True, "error": "Failed to get room data"}
    playerData = roomData["data"]["players"]

    checksumList = get_checksums(STATIC_TRACKER_API + trackerId)
    if checksumList["status"] != 200:
        return {"failed": True, "error": "Failed to get checksum list"}

    for checksum in checksumList["data"]:
        datapackageData = get_data(DATAPACKAGE_API + checksum)
        if datapackageData["status"] != 200:
            return {"failed": True, "error": "Failed to get datapackage"}
        allDatapackageData.append(datapackageData["data"])

    preLoadJson()
    return {"failed": False, "error": None}

def get_session(port):
    """Find user session by checking cookies from browsers and matching the port number."""
    cookiesJar = get_cookies([])
    for cookies in cookiesJar:
        response = requests.get(USER_ENDPOINT_API, cookies=cookies)
        if response.status_code == 200:
            userRoomData = response.json()
            for room in userRoomData:
                if room["last_port"] == port:
                    return {"room_id": room["room_id"], "tracker": room["tracker"], "status": response.status_code}
    return {"room_id": "", "tracker": "", "status": 404}

def get_cookies(cookiesJar):
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

def get_checksums(url):
    """Retrieve checksums needed to acquire data packages for games."""
    response = requests.get(url)
    if response.status_code != 200:
        return {"data": [], "status": response.status_code}
    data = response.json()
    checksumList = [package["checksum"] for game, package in data["datapackage"].items() if game != "Archipelago"]
    return {"data": checksumList, "status": response.status_code}

def preLoadJson():
    """Preload data from regions.json to reduce scanning time."""
    global roomRegionsDict, excludedItems
    with open(os.path.join(companion_directory, "regions.json"), "r") as regionData:
        regions = json.load(regionData)
    roomRegionsDict = {game[1]: regions[game[1]] for game in playerData}
    excludedItems = get_excluded_items(playerData)

def get_excluded_items(playerData):
    """Load excluded items from exclude_items.json."""
    excludedItems = []
    with open(os.path.join(companion_directory, "exclude_items.json"), "r") as excludedItemData:
        excludedItemList = json.load(excludedItemData)
        for player in playerData:
            items = excludedItemList[player[1]]["Exclude Items"]
            excludedItems.extend(
                [item + f" ({player[0]})" if len(playerData) > 1 else item for item in items]
            )
    return excludedItems

def get_regions(playerGame):
    """Retrieve regions for a specific game."""
    return roomRegionsDict[playerGame]["Region"]

def get_data(url):
    """Fetch data from an API endpoint."""
    response = requests.get(url)
    return {"data": response.json(), "status": response.status_code}

def build_playthrough():
    """Extract playthrough data from the spoiler file."""
    global playthrough
    playthrough = []
    file = get_spoiler()
    with open(os.path.join(companion_directory, file), "r") as spoilerData:
        spoiler = spoilerData.readlines()

    playthroughStart = next((i for i, line in enumerate(spoiler) if line.startswith("Playthrough:\n")), 0)
    playthroughEnd = next((i for i, line in enumerate(spoiler) if line.startswith("Paths:\n")), len(spoiler))
    playthrough = spoiler[playthroughStart + 1:playthroughEnd]

def get_spoiler():
    """Retrieve the spoiler file from the current directory."""
    return next((file for file in os.listdir(companion_directory) if file.endswith(".txt")), None)

def update_tracker():
    """Update tracker data."""
    global trackerData
    trackerData = get_data(TRACKER_API + trackerId)
    if trackerData["status"] != 200:
        return {"failed": True, "error": "Failed to get tracker data"}
    trackerData = trackerData["data"]

def get_hint():
    """
    Generate a hint for the next location to check based on the playthrough and tracker data.
    """
    global hint, playerData, playthrough
    firstNewLocationToEndOfSphereList = []
    allCheckLocations = []
    uncheckedLocation = []
    newRegionHint = ""
    playerLocation = ""  # Player and game who the check belongs to
    foundLocation = False

    update_tracker()

    # Gather all checked locations
    playerChecks = trackerData["player_checks_done"]
    for playerInd, playerNum in enumerate(playerChecks):
        allCheckLocations.extend(playerNum["locations"])
        locationMapping = allDatapackageData[playerInd]["location_name_to_id"]
        for location, locationID in locationMapping.items():
            if locationID not in allCheckLocations:
                uncheckedLocation.append(location)

    # Find the first unchecked location in the playthrough
    for line in playthrough:
        if line.startswith(END_OF_SPHERE_MARKER) and foundLocation:
            break
        for location in uncheckedLocation:
            if location in line:
                for player in playerData:
                    formattedPlayer = ""
                    if len(playerData) > 1:
                        formattedPlayer = START_OF_PLAYER_LOCATION_MARKER + player[0] + END_OF_LOCATION_MARKER
                        item = line[line.find(formattedPlayer) + len(formattedPlayer):line.find("\n")]
                    else:
                        item = line[line.find(SOLO_END_OF_LOCATION_MARKER) + len(SOLO_END_OF_LOCATION_MARKER):line.find("\n")]
                    formattedLocation = location + formattedPlayer

                    if formattedLocation in line and item not in excludedItems:
                        firstNewLocationToEndOfSphereList.append([location, player])
                        foundLocation = True

    # Randomly choose a location to avoid bias
    chosenLocation = random.choice(firstNewLocationToEndOfSphereList)
    playerLocation = chosenLocation[1]
    nextLocation = chosenLocation[0].lstrip()  # Remove leading spaces from spoiler formatting

    # Determine the region for the chosen location
    regionList = get_regions(playerLocation[1])
    for region in regionList:
        try:
            regionListKeys = list(region.keys())
            if regionListKeys:
                regionAlias = region[regionListKeys[0]]
                for alias in regionAlias:
                    if nextLocation.startswith(alias):
                        newRegionHint = f"{playerLocation[0]}: {regionListKeys[0]}"
                        break
            if newRegionHint:
                break
        except Exception:
            regionAlias = region
            if nextLocation.startswith(regionAlias):
                newRegionHint = f"{playerLocation[0]}: {region}"
                break

    hint = f"Have you tried searching here?\n {newRegionHint}"
    return {"failed": False, "error": None}

class HintCompanion(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.port_var = ctk.StringVar()
        self.roomId_var = ctk.StringVar()
        self.trackerId_var = ctk.StringVar()

        self.title("Hint Companion")
        self.geometry("540x300")

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
        self.connectButton = ctk.CTkButton(self, text="Connect", command=lambda: self.processConnection())
        self.connectButton.grid(row=0, column=2, padx=5, pady=5)

        # Status Label
        self.status_label = ctk.CTkLabel(self, text="Awaiting Connection", **FRAME_TITLE_STYLE)
        self.status_label.grid(row=3, column=0, padx=5, pady=5, columnspan=3)

        # Get Hint Button
        self.getHint = ctk.CTkButton(self, text="Get Hint", command=lambda: self.update_hint(), state="disabled")
        self.getHint.grid(row=4, column=0, padx=5, pady=5)

        # Hint Label
        self.hint_label = ctk.CTkLabel(self, text=hint)
        self.hint_label.grid(row=4, column=1, padx=5, pady=5, columnspan=2, rowspan=2)

    def update_hint(self):
        """
        Update the hint label with the next hint.
        """
        status = get_hint()
        if status["failed"]:
            self.status_label.configure(text=status["error"])
        else:
            self.hint_label.configure(text=hint)

    def processConnection(self):
        """
        Handle the connection process and update the UI accordingly.
        """
        self.connectButton.configure(state="disabled")
        self.getHint.configure(state="disabled")
        self.status_label.configure(text="Connecting...")
        self.update_idletasks()
        try:
            if self.portEntry.get() == "":
                status = connect(0, self.roomEntry.get(), self.trackerEntry.get())
            else:
                status = connect(int(self.portEntry.get()), self.roomEntry.get(), self.trackerEntry.get())

            if status["failed"]:
                self.status_label.configure(text=status["error"])
                self.connectButton.configure(state="normal")
            else:
                self.status_label.configure(text="Connected")
                self.connectButton.configure(state="normal")
                self.getHint.configure(state="normal")
                self.roomId_var.set(roomIdText)
                self.trackerId_var.set(trackerIdText)

        except Exception as e:
            print(e)
            self.status_label.configure(text="Invalid Port Number")
            self.connectButton.configure(state="normal")


if __name__ == "__main__":
    build_playthrough()

    app = HintCompanion()
    app.mainloop()
    




        




