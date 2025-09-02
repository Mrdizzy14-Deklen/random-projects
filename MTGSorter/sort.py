import cv2
import easyocr
import os
from datetime import datetime
import time
import requests
import hashlib
import json
from collections import Counter

# =========================
# util / hashing
# =========================

def norm(s):
    return ''.join(c.lower() for c in s if c.isalnum() or c.isspace()).strip()

def h32(s):
    return int(hashlib.blake2s(s.encode('utf-8'), digest_size=4).hexdigest(), 16)

def pile_index_oracle(oracle_id: str, K: int = 40, virtual_bins: int = 5120):
    if not oracle_id:
        raise ValueError("oracle_id is required")
    h = h32(f"oracle:{oracle_id.lower()}")
    vbin = h % virtual_bins
    return vbin % K

def is_basic_land(type_line: str):
    return "basic land" in norm(type_line)

# def is_commander(type_line: str, scry: scryfall):
#     return  

# =========================
# core models
# =========================

class card:
    __slots__ = ("__name", "__setCode", "__collectNum", "__colors", "__mValue",
                 "__type", "__pile", "__oracleID", "__amount")

    def __init__(self, name: str, setCode: str, collectNum: int, colors: str,
                 mValue: int, type: str, oracleID: str = "", amount: int = 1):
        self.__name = name
        self.__setCode = setCode
        self.__collectNum = collectNum
        self.__colors = colors
        self.__mValue = mValue
        self.__type = type
        self.__pile = -1
        self.__oracleID = oracleID
        self.__amount = amount

    def __eq__(self, other):
        if not isinstance(other, card):
            return NotImplemented
        return self.__oracleID == other.__oracleID

    def __hash__(self):
        return hash(self.__oracleID)

    def getName(self): return self.__name
    def getSetCode(self): return self.__setCode
    def getCollectNum(self): return self.__collectNum
    def getColors(self): return self.__colors
    def getMValue(self): return self.__mValue
    def getType(self): return self.__type
    def getPile(self): return self.__pile
    def getOracleID(self): return self.__oracleID
    def getAmount(self): return self.__amount

    def setPile(self, p: int): self.__pile = p
    def addAmount(self, n: int): self.__amount += n
    def subAmount(self, n: int): self.__amount = max(0, self.__amount - n)

class pile:
    __slots__ = ("__index", "__cards", "__name_counts", "__type_counts", "__color_counts")

    def __init__(self, index: int):
        self.__index = index
        self.__cards = []
        self.__name_counts = Counter()
        self.__type_counts = Counter()
        self.__color_counts = Counter()
        print("\nCreated Pile " + str(index + 1))

    def insert(self, c: card):
        # merge fungibly by oracleID
        for stored in self.__cards:
            if stored.getOracleID() == c.getOracleID():
                stored.addAmount(c.getAmount())
                self.__name_counts[stored.getName()] += c.getAmount()
                self.__type_counts[stored.getType()] += c.getAmount()
                self.__color_counts[stored.getColors()] += c.getAmount()
                return
        self.__cards.append(c)
        self.__name_counts[c.getName()] += c.getAmount()
        self.__type_counts[c.getType()] += c.getAmount()
        self.__color_counts[c.getColors()] += c.getAmount()

    def remove(self, c: card):
        for i, stored in enumerate(self.__cards):
            if stored.getOracleID() == c.getOracleID():
                delta = c.getAmount()
                if stored.getAmount() > delta:
                    stored.subAmount(delta)
                else:
                    delta = stored.getAmount()
                    self.__cards.pop(i)
                self.__name_counts[stored.getName()] -= delta
                if self.__name_counts[stored.getName()] == 0: del self.__name_counts[stored.getName()]
                self.__type_counts[stored.getType()] -= delta
                if self.__type_counts[stored.getType()] == 0: del self.__type_counts[stored.getType()]
                self.__color_counts[stored.getColors()] -= delta
                if self.__color_counts[stored.getColors()] == 0: del self.__color_counts[stored.getColors()]
                return True
        return False

    def size(self):
        return len(self.__cards)

    def getCardAmount(self, c: card):
        for stored in self.__cards:
            if stored.getOracleID() == c.getOracleID():
                return stored.getAmount()
        return 0

    def listCards(self):
        """Return a list of (name, amount) for all cards in this pile."""
        return [(c.getName(), c.getAmount()) for c in self.__cards]

    # internal accessor used by serializer (keeps your style)
    def _cards(self):
        return self.__cards

# =========================
# catalog (uses piles; land pile is the last index)
# =========================

class catalog:

    def __init__(self, pileNum = 40, vBins = 5120):
        self.__pileNum = pileNum              # number of hashed (non-land) piles
        self.__vBins = vBins
        # allocate hashed piles [0..pileNum-1] PLUS a final land pile at index = pileNum
        self.__piles = [pile(i) for i in range(pileNum)] + [pile(pileNum)] + [pile(pileNum + 1)]
        self.__land_index = pileNum
        self.__commander_index = pileNum + 1

    def insert(self, c: card):
        if is_basic_land(c.getType()):
            p = self.__land_index
        else:
            p = pile_index_oracle(c.getOracleID(), self.__pileNum, self.__vBins)
        c.setPile(p)
        self.__piles[p].insert(c)

    def retrieve(self, c: card):
        if is_basic_land(c.getType()):
            p = self.__land_index
        else:
            p = pile_index_oracle(c.getOracleID(), self.__pileNum, self.__vBins)
        amt = self.__piles[p].getCardAmount(c)
        return amt, ("land" if p == self.__land_index else p)

    def remove(self, c: card):
        if is_basic_land(c.getType()):
            p = self.__land_index
        else:
            p = pile_index_oracle(c.getOracleID(), self.__pileNum, self.__vBins)
        return self.__piles[p].remove(c)

    def print_pile(self, pile_index):
        # allow "land" or numeric index
        if pile_index == "land":
            p = self.__piles[self.__land_index]
            out = "\n== Land Pile ==\n"
        else:
            i = int(pile_index)
            if i == self.__land_index:
                p = self.__piles[self.__land_index]
                out = "\n== Land Pile ==\n"
            else:
                p = self.getPileAt(i)
                out = f"\n== Pile {i + 1} ==\n"
        print(out)
        cards = p.listCards()
        if not cards:
            print(" (empty)")
        else:
            for name, amount in cards:
                print(f" {amount}x {name}")
        print("\n=============\n")

    def print_all_cards_by_pile(self):
        for i in range(self.__pileNum):  # hashed piles
            self.print_pile(i)
        self.print_pile("land")          # land pile last

    def getPileNum(self): return self.__pileNum
    def getPileAt(self, i): return self.__piles[i]
    def getBins(self): return self.__vBins
    def getLandIndex(self): return self.__land_index

# =========================
# scryfall client
# =========================

class scryfall:
    SCRY_NAMED_URL = "https://api.scryfall.com/cards/named"
    _HTTP_TIMEOUT = 15

    def _canonical_colors(self, j):
        colors = j.get("color_identity") or j.get("colors") or []
        return "".join(sorted(colors)) if colors else "C"

    def _safe_int(self, x, default=0):
        try:
            return int(x)
        except Exception:
            return default

    def fetch_card_by_name(self, name: str) -> card:
        r = requests.get(self.SCRY_NAMED_URL, params={"fuzzy": name}, timeout=self._HTTP_TIMEOUT)
        if r.status_code != 200:
            raise RuntimeError(f"Scryfall error {r.status_code}: {r.text}")
        data = r.json()
        if data.get("object") == "error":
            raise RuntimeError(data.get("details", "Unknown Scryfall error"))

        name_out = data.get("name", name)
        set_code = data.get("set", "") or ""
        collect_num = data.get("collector_number", "")
        collect_num_int = self._safe_int(collect_num)
        colors_str = self._canonical_colors(data)
        mv = data.get("cmc", data.get("mana_value"))
        mv_int = self._safe_int(mv)
        type_line = data.get("type_line", "") or ""
        oracle_id = data.get("oracle_id", "") or ""

        return card(name_out, set_code, collect_num_int, colors_str, mv_int, type_line, oracle_id, 1)

# =========================
# storage (save / load)
# =========================

def _card_to_dict(c: card) -> dict:
    return {
        "name": c.getName(),
        "setCode": c.getSetCode(),
        "collectNum": c.getCollectNum(),
        "colors": c.getColors(),
        "mValue": c.getMValue(),
        "type": c.getType(),
        "oracleID": c.getOracleID(),
        "amount": c.getAmount(),
    }

def _serialize_catalog(cat: catalog) -> dict:
    data = {
        "pileNum": cat.getPileNum(),
        "vBins": cat.getBins(),
        "cards": [],
        "landCards": [],
    }
    # hashed piles only
    for i in range(cat.getPileNum()):
        p = cat.getPileAt(i)
        for c in p._cards():
            data["cards"].append(_card_to_dict(c))
    # land pile = last pile
    land_pile = cat.getPileAt(cat.getLandIndex())
    for c in land_pile._cards():
        data["landCards"].append(_card_to_dict(c))
    return data

def save(cat: catalog, path: str = "catalog.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_serialize_catalog(cat), f, indent=2, ensure_ascii=False)

def load(path: str = "catalog.json", pileNum: int = 40, vBins: int = 5120) -> catalog:
    if not os.path.exists(path):
        print("\nMAKING NEW FILE")
        cat = catalog(pileNum, vBins)
        save(cat, path)
        return cat

    print("\nFILE FOUND")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Always rebuild using the requested pileNum/vBins (ignore persisted ones)
    cat = catalog(pileNum, vBins)

    sf = scryfall()

    def build_card(d: dict) -> card:
        oracle = d.get("oracleID", "") or ""
        if not oracle:
            try:
                fetched = sf.fetch_card_by_name(d["name"])
                oracle = fetched.getOracleID()
                if not oracle:
                    return None
            except Exception:
                return None
        return card(
            d["name"],
            d.get("setCode", ""),
            int(d.get("collectNum", 0)),
            d.get("colors", "C"),
            int(d.get("mValue", 0)),
            d.get("type", ""),
            oracle,
            int(d.get("amount", 1)),
        )

    # regular hashed piles
    for d in data.get("cards", []):
        c = build_card(d)
        if c is not None:
            cat.insert(c)

    # land pile (explicitly add to last pile to preserve JSON split)
    for d in data.get("landCards", []):
        c = build_card(d)
        if c is not None:
            cat.getPileAt(cat.getLandIndex()).insert(c)

    return cat

# =========================
# OCR camera (kept modular)
# =========================

class OCRCamera:
    def __init__(self, camera_index: int = -1):
        if camera_index == -1:
            print(self.list_available_cameras())
            self.camera_index = int(input("Which camera?"))
        else:
            self.camera_index = camera_index

    def startUp(self):
        self.reader = easyocr.Reader(['en'])
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise RuntimeError(f"\nCould not open camera index {self.camera_index}")
        time.sleep(2)
        for _ in range(5):
            self.cap.read()

    def list_available_cameras(self, max_index: int = 5):
        available = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available

    def capture(self):
        if not self.cap or not self.cap.isOpened():
            raise RuntimeError("\nCamera not available")
        ok, frame = self.cap.read()
        if not ok:
            raise RuntimeError("\nFailed to capture frame from camera")
        return frame

    def capture_text(self, save: bool = False, save_dir: str = "captures", pad: int = 6):
        frame = self.capture()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.reader.readtext(
            rgb, detail=1, paragraph=False,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-' "
        )
        if not results:
            return "", None, None
        best_box, best_text, best_conf = max(results, key=lambda x: x[2])
        xs = [int(p[0]) for p in best_box]
        ys = [int(p[1]) for p in best_box]
        x0, x1 = max(min(xs) - pad, 0), min(max(xs) + pad, frame.shape[1])
        y0, y1 = max(min(ys) - pad, 0), min(max(ys) + pad, frame.shape[0])
        crop = frame[y0:y1, x0:x1].copy()
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        r2 = self.reader.readtext(
            crop_rgb, detail=1, paragraph=False,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-' "
        )
        if r2:
            best_text = max(r2, key=lambda x: x[2])[1]
        text = norm(" ".join(best_text.split()).strip("-'\".,;:()[]{}"))
        saved_path = None
        if save:
            os.makedirs(save_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            saved_path = os.path.join(save_dir, f"crop_{ts}.png")
            cv2.imwrite(saved_path, crop)
            saved_path = os.path.join(save_dir, f"full_{ts}.png")
            cv2.imwrite(saved_path, frame)
        return text, crop, saved_path

    def camLoop(self, cat, scry):
        self.startUp()
        loop = -1
        while(loop != "3"):
            print("\n= Scan Card =\n")
            print("1) Scan\n")
            print("2) Scan (Save)\n")
            print("3) Exit\n")
            print("=============\n")
            loop = input("")
            os.system('cls' if os.name == 'nt' else 'clear')
            match loop :
                case "1":
                    text, img, path = self.capture_text(False)
                    print("\n" + str(text))
                    cat.insert(scry.fetch_card_by_name(text))
                    save(cat)
                case "2":
                    text, img, path = self.capture_text(True)
                    print("\n" + str(text))
                    cat.insert(scry.fetch_card_by_name(text))
                    save(cat)
                case _:
                    continue
        self.release()

    #meow moeow meow meow meow meow 
    # /^--^\     /
    #( o .o )
    # -----/
    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None

# =========================
# simple CLI UI (thin)
# =========================

def addCard(cat: catalog, scry: scryfall):
    loop = -1
    while(loop != "2"):
        print("\n= Type Card =\n")
        print("1) Enter Card\n")
        print("2) Exit\n")
        print("=============\n")
        loop = input("")
        os.system('cls' if os.name == 'nt' else 'clear')
        if loop == "1":
            name = input("Card Name: ")
            amt_in = input("\nAmount: ")
            try:
                n = int(amt_in)
            except:
                n = 1
            fetched = scry.fetch_card_by_name(name)
            c = card(
                fetched.getName(),
                fetched.getSetCode(),
                fetched.getCollectNum(),
                fetched.getColors(),
                fetched.getMValue(),
                fetched.getType(),
                fetched.getOracleID(),
                n
            )
            print("\nAdding card: " + name + " x" + str(n))
            cat.insert(c)
            save(cat)


def userInput(cam, scry, cat):
    running = True
    while(running):
        print("\n=== MTG Sorter ===\n")
        print("1) Upload Card")
        print("2) Remove Card")
        print("3) Retrieve")
        print("4) Exit")
        print("\n==================\n")
        choice = input("")
        os.system('cls' if os.name == 'nt' else 'clear')
        match(choice):
            case "1":
                print("\n== Upload Card ==\n")
                print("1) Scan Card")
                print("2) Type Card")
                print("3) Exit")
                print("\n=================\n")
                choice = input("")
                os.system('cls' if os.name == 'nt' else 'clear')
                match(choice):
                    case "1":
                        cam.camLoop(cat, scry)
                    case "2":
                        addCard(cat, scry)
                    case _:
                        continue
            case "2":
                loop = -1
                while loop != "2":
                    print("\n== Remove Card ==\n")
                    print("1) Enter Card")
                    print("2) Exit")
                    print("\n=================\n")
                    loop = input("")
                    os.system('cls' if os.name == 'nt' else 'clear')
                    match loop:
                        case "1":
                            name = input("\nCard Name: ")
                            n = int(input("\nAmount: "))
                            c = scry.fetch_card_by_name(name)
                            # remove N copies in one call
                            c = card(c.getName(), c.getSetCode(), c.getCollectNum(), c.getColors(),
                                     c.getMValue(), c.getType(), c.getOracleID(), n)
                            ok = cat.remove(c)
                            save(cat)
                            if not ok:
                                print("\nCard not found.")
                        case _:
                            continue
            case "3":
                loop = -1
                while loop != "4":
                    print("\n== Retrieve ==\n")
                    print("1) Enter Card")
                    print("2) Enter Pile")
                    print("3) All Cards")
                    print("4) Exit")
                    print("\n==============\n")
                    loop = input("")
                    os.system('cls' if os.name == 'nt' else 'clear')
                    match loop:
                        case "1":
                            name = input("\nCard Name: ")
                            c = scry.fetch_card_by_name(name)
                            amount, pile_idx = cat.retrieve(c)
                            pile_str = "Land Pile" if pile_idx == "land" else ("Pile " + str(pile_idx + 1))
                            if amount == 1:
                                print("\nYou have " + str(amount) + " " + str(c.getName()) + " in " + pile_str)
                            else:
                                print("\nYou have " + str(amount) + " " + str(c.getName()) + "s in " + pile_str)
                        case "2":
                            pile_in = input("\nPile Number (or 'land'): ")
                            if pile_in.strip().lower() == "land":
                                cat.print_pile("land")
                            else:
                                cat.print_pile(int(pile_in) - 1)
                        case "3":
                            cat.print_all_cards_by_pile()
                        case _:
                            continue

            case "4":
                break
            case _:
                continue

# =========================
# bootstrap
# =========================

if __name__ == "__main__":

    cam = OCRCamera(0)
    scry = scryfall()
    cat = load(pileNum=40, vBins=5120)

    userInput(cam, scry, cat)
    save(cat)
