"""Merge Beginner_Sign_Language_100_Words.docx vocabulary into the project catalog."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = ROOT / "models" / "motion-vocabulary.json"
OUT_PATH = ROOT / "models" / "beginner-100-words.json"
EVAL_PATH = Path(r"C:\Users\Squid\Desktop\capstone\hs-eval\daily-words\beginner-100-words.json")

WORDS = [
    (1, "Hello", "Greetings"),
    (2, "Goodbye", "Greetings"),
    (3, "Thank you", "Greetings"),
    (4, "Please", "Greetings"),
    (5, "Sorry", "Greetings"),
    (6, "Yes", "Responses"),
    (7, "No", "Responses"),
    (8, "Okay", "Responses"),
    (9, "Welcome", "Greetings"),
    (10, "Good morning", "Greetings"),
    (11, "Good afternoon", "Greetings"),
    (12, "Good night", "Greetings"),
    (13, "How", "Questions"),
    (14, "What", "Questions"),
    (15, "Who", "Questions"),
    (16, "Where", "Questions"),
    (17, "When", "Questions"),
    (18, "Why", "Questions"),
    (19, "Which", "Questions"),
    (20, "Name", "Questions"),
    (21, "I / Me", "Pronouns"),
    (22, "You", "Pronouns"),
    (23, "He / She", "Pronouns"),
    (24, "We", "Pronouns"),
    (25, "They", "Pronouns"),
    (26, "My / Mine", "Pronouns"),
    (27, "Your / Yours", "Pronouns"),
    (28, "This", "Pronouns"),
    (29, "That", "Pronouns"),
    (30, "Everyone", "Pronouns"),
    (31, "Mother", "Family"),
    (32, "Father", "Family"),
    (33, "Brother", "Family"),
    (34, "Sister", "Family"),
    (35, "Baby", "Family"),
    (36, "Child", "Family"),
    (37, "Friend", "People"),
    (38, "Teacher", "People"),
    (39, "Student", "People"),
    (40, "Family", "Family"),
    (41, "Eat", "Actions"),
    (42, "Drink", "Actions"),
    (43, "Sleep", "Actions"),
    (44, "Wake up", "Actions"),
    (45, "Walk", "Actions"),
    (46, "Run", "Actions"),
    (47, "Sit", "Actions"),
    (48, "Stand", "Actions"),
    (49, "Go", "Actions"),
    (50, "Come", "Actions"),
    (51, "Help", "Actions"),
    (52, "Stop", "Actions"),
    (53, "Wait", "Actions"),
    (54, "Give", "Actions"),
    (55, "Take", "Actions"),
    (56, "Want", "Actions"),
    (57, "Need", "Actions"),
    (58, "Like", "Actions"),
    (59, "Love", "Actions"),
    (60, "Know", "Actions"),
    (61, "Happy", "Emotions"),
    (62, "Sad", "Emotions"),
    (63, "Angry", "Emotions"),
    (64, "Scared", "Emotions"),
    (65, "Tired", "Emotions"),
    (66, "Sick", "Emotions"),
    (67, "Hungry", "Feelings"),
    (68, "Thirsty", "Feelings"),
    (69, "Good", "Descriptions"),
    (70, "Bad", "Descriptions"),
    (71, "Home", "Places"),
    (72, "School", "Places"),
    (73, "Hospital", "Places"),
    (74, "Store", "Places"),
    (75, "Bathroom", "Places"),
    (76, "Work", "Places"),
    (77, "Here", "Directions"),
    (78, "There", "Directions"),
    (79, "Inside", "Directions"),
    (80, "Outside", "Directions"),
    (81, "Today", "Time"),
    (82, "Tomorrow", "Time"),
    (83, "Yesterday", "Time"),
    (84, "Now", "Time"),
    (85, "Later", "Time"),
    (86, "Morning", "Time"),
    (87, "Night", "Time"),
    (88, "Time", "Time"),
    (89, "Before", "Time"),
    (90, "After", "Time"),
    (91, "Water", "Food / Drinks"),
    (92, "Food", "Food / Drinks"),
    (93, "Rice", "Food"),
    (94, "Milk", "Food / Drinks"),
    (95, "Bread", "Food"),
    (96, "Money", "Objects"),
    (97, "Phone", "Objects"),
    (98, "Book", "Objects"),
    (99, "Clothes", "Objects"),
    (100, "Bag", "Objects"),
]

CAT_MAP = {
    "Greetings": "greetings-communication",
    "Responses": "question-response-words",
    "Questions": "question-response-words",
    "Pronouns": "question-response-words",
    "Family": "family-people",
    "People": "family-people",
    "Actions": "actions",
    "Emotions": "feelings",
    "Feelings": "feelings",
    "Descriptions": "feelings",
    "Places": "places",
    "Directions": "places",
    "Time": "time",
    "Food / Drinks": "food",
    "Food": "food",
    "Objects": "common-objects",
}

RECOGNITION = {
    "HELLO": "default-preview",
    "THANK YOU": "default-preview",
    "PLEASE": "default-preview",
    "YES": "default-preview",
    "NO": "default-preview",
    "BABY": "default-preview",
    "DRINK": "existing-preview",
    "WATER": "existing-preview",
    "BOOK": "existing-preview",
    "FOOD": "existing-preview",
    "HUNGRY": "existing-preview",
    "LIKE": "existing-preview",
    "GO": "existing-preview",
    "NAME": "daily-preview",
    "HOME": "daily-preview",
    "HAVE": "daily-preview",
    "WANT": "daily-preview",
    "LOVE": "daily-preview",
}

LEARNING = {
    "HELLO": "https://www.lifeprint.com/asl101/pages-signs/h/hello.htm",
    "GOODBYE": "https://www.lifeprint.com/asl101/pages-signs/g/good-bye.htm",
    "THANK YOU": "https://www.lifeprint.com/asl101/pages-signs/t/thankyou.htm",
    "PLEASE": "https://www.lifeprint.com/asl101/pages-signs/p/please.htm",
    "SORRY": "https://www.lifeprint.com/asl101/pages-signs/s/sorry.htm",
    "YES": "https://www.lifeprint.com/asl101/pages-signs/y/yes.htm",
    "NO": "https://www.lifeprint.com/asl101/pages-signs/n/no.htm",
    "GOOD NIGHT": "https://www.lifeprint.com/asl101/pages-signs/g/goodnight.htm",
    "HOW": "https://www.lifeprint.com/asl101/pages-signs/h/how.htm",
    "WHAT": "https://www.lifeprint.com/asl101/pages-signs/w/what.htm",
    "WHO": "https://www.lifeprint.com/asl101/pages-signs/w/who.htm",
    "WHERE": "https://www.lifeprint.com/asl101/pages-signs/w/where.htm",
    "WHEN": "https://www.lifeprint.com/asl101/pages-signs/w/when.htm",
    "WHY": "https://www.lifeprint.com/asl101/pages-signs/w/why.htm",
    "YOU": "https://www.lifeprint.com/asl101/pages-signs/y/you.htm",
    "WE": "https://www.lifeprint.com/asl101/pages-signs/w/we.htm",
    "THEY": "https://www.lifeprint.com/asl101/pages-signs/t/they.htm",
    "THIS": "https://www.lifeprint.com/asl101/pages-signs/t/this.htm",
    "THAT": "https://www.lifeprint.com/asl101/pages-signs/t/that.htm",
    "MOTHER": "https://www.lifeprint.com/asl101/pages-signs/m/mother.htm",
    "FATHER": "https://www.lifeprint.com/asl101/pages-signs/f/father.htm",
    "FRIEND": "https://www.lifeprint.com/asl101/pages-signs/f/friend.htm",
    "TEACHER": "https://www.lifeprint.com/asl101/pages-signs/t/teacher.htm",
    "STUDENT": "https://www.lifeprint.com/asl101/pages-signs/s/student.htm",
    "FAMILY": "https://www.lifeprint.com/asl101/pages-signs/f/family.htm",
    "EAT": "https://www.lifeprint.com/asl101/pages-signs/e/eat.htm",
    "DRINK": "https://www.lifeprint.com/asl101/pages-signs/d/drink.htm",
    "SLEEP": "https://www.lifeprint.com/asl101/pages-signs/s/sleep.htm",
    "WAKE UP": "https://www.lifeprint.com/asl101/pages-signs/w/wakeup.htm",
    "SIT": "https://www.lifeprint.com/asl101/pages-signs/s/sit.htm",
    "STAND": "https://www.lifeprint.com/asl101/pages-signs/s/stand.htm",
    "GO": "https://www.lifeprint.com/asl101/pages-signs/g/go.htm",
    "COME": "https://www.lifeprint.com/asl101/pages-signs/c/come.htm",
    "HELP": "https://www.lifeprint.com/asl101/pages-signs/h/help.htm",
    "STOP": "https://www.lifeprint.com/asl101/pages-signs/s/stop.htm",
    "WAIT": "https://www.lifeprint.com/asl101/pages-signs/w/wait.htm",
    "HAPPY": "https://www.lifeprint.com/asl101/pages-signs/h/happy.htm",
    "SAD": "https://www.lifeprint.com/asl101/pages-signs/s/sad.htm",
    "ANGRY": "https://www.lifeprint.com/asl101/pages-signs/a/angry.htm",
    "SCARED": "https://www.lifeprint.com/asl101/pages-signs/s/scared.htm",
    "TIRED": "https://www.lifeprint.com/asl101/pages-signs/t/tired.htm",
    "GOOD": "https://www.lifeprint.com/asl101/pages-signs/g/good.htm",
    "BAD": "https://www.lifeprint.com/asl101/pages-signs/b/bad.htm",
    "BATHROOM": "https://www.lifeprint.com/asl101/pages-signs/b/bathroom.htm",
    "HERE": "https://www.lifeprint.com/asl101/pages-signs/h/here.htm",
    "THERE": "https://www.lifeprint.com/asl101/pages-signs/t/there.htm",
    "INSIDE": "https://www.lifeprint.com/asl101/pages-signs/i/in.htm",
    "OUTSIDE": "https://www.lifeprint.com/asl101/pages-signs/o/outside.htm",
    "TIME": "https://www.lifeprint.com/asl101/pages-signs/t/time.htm",
    "BEFORE": "https://www.lifeprint.com/asl101/pages-signs/b/before.htm",
    "AFTER": "https://www.lifeprint.com/asl101/pages-signs/a/after.htm",
    "WATER": "https://www.lifeprint.com/asl101/pages-signs/w/water.htm",
    "FOOD": "https://www.lifeprint.com/asl101/pages-signs/f/food.htm",
    "I / ME": "https://www.lifeprint.com/asl101/pages-signs/i/i.htm",
    "HE / SHE": "https://www.lifeprint.com/asl101/pages-signs/h/he.htm",
    "MY / MINE": "https://www.lifeprint.com/asl101/pages-signs/m/my.htm",
    "YOUR / YOURS": "https://www.lifeprint.com/asl101/pages-signs/y/your.htm",
    "EVERYONE": "https://www.lifeprint.com/asl101/pages-signs/e/everyone.htm",
}

MEDIA = {
    "HELLO": "media/signs/hello.mp4",
    "THANK YOU": "media/signs/thank-you.mp4",
    "PLEASE": "media/signs/please.mp4",
    "YES": "media/signs/yes.mp4",
    "NO": "media/signs/no.mp4",
    "DRINK": "media/signs/drink.mp4",
    "WATER": "media/signs/water.mp4",
    "FOOD": "media/signs/food.mp4",
    "GO": "media/signs/go.mp4",
    "EAT": "media/signs/eat.mp4",
}

BEGINNER_CAT = "beginner-100"
BEGINNER_CAT_NAME = "Beginner 100"


def slug(label: str) -> str:
    s = label.lower().replace("/", " ").replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def main() -> None:
    data = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))
    if not any(c["id"] == BEGINNER_CAT for c in data["categories"]):
        data["categories"].append({"id": BEGINNER_CAT, "name": BEGINNER_CAT_NAME})

    by_label = {item["label"].upper(): item for item in data["items"]}
    by_id = {item["id"]: item for item in data["items"]}
    added, tagged, beginner_index = [], [], []

    for num, word, doc_cat in WORDS:
        label = word.upper()
        item = by_label.get(label)
        cat_id = CAT_MAP[doc_cat]
        aliases = [p.strip().upper() for p in word.split(" / ")] if " / " in word else []

        if item is None:
            item_id = slug(label)
            base, n = item_id, 2
            while item_id in by_id:
                item_id = f"{base}-{n}"
                n += 1
            item = {
                "id": item_id,
                "label": label,
                "categories": [cat_id, BEGINNER_CAT],
                "sourceLabel": None,
                "sourceVersion": None,
                "recognition": RECOGNITION.get(label, "not-pretrained"),
                "note": "Beginner 100 vocabulary (dataset label). Signs may differ between FSL and ASL.",
                "video": MEDIA.get(label),
                "learningUrl": LEARNING.get(label),
                "cameraGroups": [],
            }
            if label in LEARNING:
                item["learningScope"] = label
            if aliases:
                item["searchAliases"] = aliases
            data["items"].append(item)
            by_label[label] = item
            by_id[item["id"]] = item
            added.append(label)
        else:
            cats = item.setdefault("categories", [])
            if BEGINNER_CAT not in cats:
                cats.append(BEGINNER_CAT)
                tagged.append(label)
            if aliases:
                existing = item.setdefault("searchAliases", [])
                for alias in aliases:
                    if alias not in existing and alias != item["label"]:
                        existing.append(alias)
            if label in RECOGNITION and item.get("recognition") == "not-pretrained":
                item["recognition"] = RECOGNITION[label]
            if label in MEDIA and not item.get("video"):
                item["video"] = MEDIA[label]
            if label in LEARNING and not item.get("learningUrl"):
                item["learningUrl"] = LEARNING[label]
                item["learningScope"] = label

        phase = 1 if num <= 30 else 2 if num <= 60 else 3 if num <= 80 else 4
        beginner_index.append(
            {
                "number": num,
                "id": item["id"],
                "label": item["label"],
                "docCategory": doc_cat,
                "catalogCategories": item["categories"],
                "phase": phase,
                "recognition": item.get("recognition"),
            }
        )

    VOCAB_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    beginner_doc = {
        "version": 1,
        "title": "Beginner Sign Language Vocabulary",
        "description": "100 everyday words and expressions for a beginner sign language recognition dataset.",
        "source": "Beginner_Sign_Language_100_Words.docx",
        "languageNote": (
            "These are vocabulary labels, not necessarily 100 distinct motions. "
            "Signs vary between Filipino Sign Language (FSL) and American Sign Language (ASL). "
            "Some expressions use multiple signs."
        ),
        "phases": [
            {"phase": 1, "range": "1-30", "focus": "Greetings, responses, questions, and pronouns"},
            {"phase": 2, "range": "31-60", "focus": "People, family, actions, and requests"},
            {"phase": 3, "range": "61-80", "focus": "Feelings, places, and directions"},
            {"phase": 4, "range": "81-100", "focus": "Time, food, and objects"},
        ],
        "categoryId": BEGINNER_CAT,
        "words": beginner_index,
    }
    text = json.dumps(beginner_doc, indent=2, ensure_ascii=False) + "\n"
    OUT_PATH.write_text(text, encoding="utf-8")
    if EVAL_PATH.parent.is_dir():
        EVAL_PATH.write_text(text, encoding="utf-8")

    print(f"added {len(added)}: {added}")
    print(f"tagged existing {len(tagged)}")
    print(f"total catalog items {len(data['items'])}")
    print(f"beginner words {len(beginner_index)}")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
