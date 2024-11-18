import os
import sys
import re
from pathlib import Path
import json
import requests
import hashlib
from pprint import pprint
from datetime import datetime, timedelta

DEBUG = False
ENGINES = {}
target_language = 'ru'
target_language_full = 'russian'
# texts = ["Hello, World", "Leper"]

phrases = [
    "Barkeep",
    "Barkeeps have some brawling experience from breaking up fights at the taverns they work in.",
    "the Bartender",
    "the Barkeep",
    "the Brewer",
    "the Burly",
    "the Tapmaster",
    "the Hopper",
    "the Beer Brewer",
    "{A lifetime in the tavern has shaped %name% the barkeep into a hardy, burly, muscular man. In troubled times, %name% often had had to 'resolve disagreements', 'escort patrons to the door', or 'ensure that customers paid fairly' on his own. Having heard his share of tales of heroic deeds, violent clashes, and exciting treasure hunts, %name% is more than ready to see the wide world for himself. He has a solid build; he might make a name for himself yet!",
]

def main():
    init()

    # phrases = ["Barkeep", "the Tapmaster", "Atilliator", "the Crossbow Crafter"]
    print(translate("claude35", phrases))
    # pprint(translate("yt", phrases))
    # pprint(translate("claude35", ["Hey, there Bastard!", "Atilliator", "the Crossbow Crafter"]))
    return

    # print(os.environ["YANDEX_IAM_TOKEN"])

    # print(translate(["hey", "there", "bastard!"]))
    # trans_set("there", "там")
    # print(trans_get_many(["hey", "there"]))

def init():
    load_dotenv()
    init_cache()

def exit(message, extra=None):
    text = red(message) + "\n" + extra if extra else red(message)
    print(text, file=sys.stderr)
    sys.exit(1)


def translate(engine, texts):
    if engine not in ENGINES:
        exit(f'Unknown translation engine "{engine}". Available options are: {", ".join(ENGINES)}')
    
    engine_func, conf = ENGINES[engine]
    conf_key = get_conf_key(conf)

    translated = [trans_get(engine, conf_key, t) for t in texts]
    todo = {inp: i for i, (inp, out) in enumerate(zip(texts, translated)) if out is None}
    if not todo:
        return translated

    todo_trans = engine_func(list(todo), conf)

    for inp, out, i in zip(todo, todo_trans, todo.values()):
        trans_set(engine, conf_key, inp, out)
        translated[i] = out

    return translated

def get_conf_key(conf):
    if not conf:
        return ""
    s = json.dumps(conf, sort_keys=True)
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def register_engine(engine, conf):
    def register(func):
        ENGINES[engine] = func, conf
        return func
    return register


@register_engine("yt", {})
def translate_yandex(texts, conf):
    if not os.environ.get("YANDEX_OAUTH_TOKEN") or not os.environ.get("YANDEX_FOLDER_ID"):
        exit("Please set up YANDEX_OAUTH_TOKEN and YANDEX_FOLDER_ID in .env file")

    yandex_iam = cache_get("yandex_iam")
    if not yandex_iam:
        res = requests.post("https://iam.api.cloud.yandex.net/iam/v1/tokens",
            json={"yandexPassportOauthToken": os.environ["YANDEX_OAUTH_TOKEN"]}).json()
        yandex_iam = res["iamToken"]
        cache_set("yandex_iam", yandex_iam, datetime.now() + timedelta(hours=12))

    print(f"Yandex translating {len(texts)} items...", file=sys.stderr);
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {0}".format(yandex_iam)
    }
    body = {
        "sourceLanguageCode": "en",
        "targetLanguageCode": target_language,
        "texts": texts,
        "folderId": os.environ["YANDEX_FOLDER_ID"],
    }
    response = requests.post('https://translate.api.cloud.yandex.net/translate/v2/translate',
        json = body,
        headers = headers
    )
    if 'translations' not in response.json():
        exit("Yandex translate failed with:", response.text)
    return [item['text'] for item in response.json()['translations']]


CONTEXT = "These are strings from Battle Brothers game, set in middle age Europe, it also has some fantasy elements like witches, weidegangers and greenskins."

CLAUDE35_PROMPT = """Please translate these phrases from english to {target_language_full}. Make the translation sound as natural as possible. Don't use any non-related phrases in result, answer with only translation text. Mind that phrases may contain special placeholders like %name% and control chars like "{{", "}}", "|" and "'", please leave these as is Please also do not convert single quotes ' into double quotes ". Prefer more fun and concise translation options.

Here's the general description of the work:
<work_description>
{context}
</work_description>
Please consider this context while translating.

The phrases to translate will go in the form of:

<phrase>phrase one</phrase>
<phrase>phrase two</phrase>

And so on. Please translate them and return in the same order and form, e.g.:

<phrase>фраза один</phrase>
<phrase>фраза два</phrase>

Here go the actual phrases:

"""
CLAUDE_CONF = {
    "prompt_template": CLAUDE35_PROMPT,
    "context": CONTEXT,
    "target_language_full": target_language_full
}

@register_engine("claude35", CLAUDE_CONF)
def translate_claude35(texts, conf):
    print(f"Claude3.5 translating {len(texts)} items...", file=sys.stderr);

    prompt = conf["prompt_template"].format(**conf)
    for phrase in texts:
        prompt += f"<phrase>{phrase}</phrase>\n"

    if DEBUG:
        print("+" * 80)
        print(prompt)

    data = anthropic(prompt)
    response_text = data["content"][0]["text"]

#     response_text = """
#     <phrase>Трактирщики имеют опыт в драках — им часто приходится разнимать потасовки в тавернах.</phrase>
# <phrase>Бармен</phrase>
# <phrase>Трактирщик</phrase>
# <phrase>Пивовар</phrase>
# <phrase>Здоровяк</phrase>
# <phrase>Хмелевар</phrase>
# <phrase>Пивовар</phrase>
# <phrase>{Годы работы в таверне превратили трактирщика %name% в крепкого, коренастого мужика. В неспокойные времена ему частенько приходилось «улаживать разногласия», «провожать гостей до двери» и «обеспечивать честную оплату». Наслушавшись историй о подвигах, жестоких битвах и поисках сокровищ, %name% готов сам повидать мир. С такой богатырской статью он точно сможет себя проявить!</phrase>
# """

    parts = re.split(r"</?phrase>", response_text)
    junk = parts[::2]
    translations = parts[1::2]
    if not all(not s or s.isspace() for s in junk):
        exit("Extra junk in the answer:", response_text)
    if len(translations) != len(texts):
        exit("Wrong number of translations:", response_text)
    return translations


def anthropic(prompt):
    if not os.environ.get("ANTHROPIC_URL") or not os.environ.get("ANTHROPIC_TOKEN"):
        exit("Please set up ANTHROPIC_URL and ANTHROPIC_TOKEN in .env file")

    url = os.environ["ANTHROPIC_URL"]
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {0}".format(os.environ["ANTHROPIC_TOKEN"]),
        "Anthropic-Version": "2023-06-01",
    }
    body = {
        "model": "claude-3-5-sonnet-20241022",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024
    }
    response = requests.post(url, json=body, headers=headers)

    if DEBUG:
        print("=" * 80)
        pprint(response.json())
        print("-" * 80)

    return response.json()


def load_dotenv():
    with Path(__file__).with_name(".env").open() as fd:
        for line in fd:
            var, val = line.strip().split('=', 1)
            os.environ[var] = val


# Cache
import sqlite3

sqlite3.register_adapter(datetime, str)
con = sqlite3.connect(Path(__file__).with_name("translations.db"), autocommit=True)


def init_cache():
    create_sql = '''
    CREATE TABLE IF NOT EXISTS translations_cache_ru (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        engine TEXT NOT null,
        conf TEXT NOT null,
        input TEXT NOT null,
        output TEXT NOT null
    );
    CREATE UNIQUE INDEX IF NOT EXISTS translations_cache_ru_idx
    ON translations_cache_ru (engine, conf, input);

    CREATE TABLE IF NOT EXISTS cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        expires TIMESTAMP NOT null,
        ckey TEXT NOT null UNIQUE,
        cval TEXT NOT null
    );
    '''
    con.cursor().executescript(create_sql)

def trans_set(engine, conf_key, input, output):
    sql = f"REPLACE INTO translations_cache_ru (engine, conf, input, output) VALUES (?, ?, ?, ?)"
    _do_sql(sql, (engine, conf_key, input, output))

def trans_get(engine, conf_key, text):
    sql = f"SELECT output FROM translations_cache_ru WHERE engine = ? AND conf = ? AND input = ?"
    return fetch_val(sql, engine, conf_key, text)

def cache_set(key, value, expires):
    sql = f"REPLACE INTO cache (ckey, cval, expires) VALUES (?, ?, ?)"
    _do_sql(sql, (key, value, expires))

def cache_get(key):
    sql = f"SELECT cval FROM cache WHERE ckey = ? and expires < ?"
    return fetch_val(sql, key, datetime.now())

def fetch_val(sql, *params):
    res = _do_sql(sql, params)
    return res[0] if res else None

def _do_sql(sql, params):
    cur = con.cursor()
    cur.execute(sql, params)
    return cur.fetchone()

# Coloring works on all systems but Windows
if os.name == 'nt':
    red = green = yellow = lambda text: text
else:
    red = lambda text: "\033[31m" + text + "\033[0m"
    green = lambda text: "\033[32m" + text + "\033[0m"
    yellow = lambda text: "\033[33m" + text + "\033[0m"


if __name__ == "__main__":
    main()
